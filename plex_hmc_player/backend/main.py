import asyncio
import contextlib
import os
import sys
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .admin import get_runtime_settings, router as admin_router
from .config import settings
from .mpv_controller import MpvController
from .plex_client import PlexClient


runtime_settings = get_runtime_settings()
_reconfigure_lock = asyncio.Lock()


def _runtime() -> dict:
    return runtime_settings.get_all()


def _effective_audio_device(audio_device: str) -> str:
    return "mock" if sys.platform == "win32" else audio_device


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    await _apply_runtime_settings(force=True)

    yield

    await plex.close()
    await player.stop()


app = FastAPI(title="Plex HMC Player", version="0.1.0", lifespan=lifespan)
app.include_router(admin_router)

frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.exists(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

initial_runtime = _runtime()
player = MpvController(
    audio_device=_effective_audio_device(initial_runtime.get("audio_device", settings.AUDIO_DEVICE)),
    max_volume=int(initial_runtime.get("max_volume", settings.MAX_VOLUME)),
)
plex = PlexClient(
    initial_runtime.get("plex_url", settings.PLEX_URL),
    initial_runtime.get("plex_token", settings.PLEX_TOKEN),
)
_applied_runtime = {
    "plex_url": initial_runtime.get("plex_url", settings.PLEX_URL),
    "plex_token": initial_runtime.get("plex_token", settings.PLEX_TOKEN),
    "audio_device": _effective_audio_device(initial_runtime.get("audio_device", settings.AUDIO_DEVICE)),
    "max_volume": int(initial_runtime.get("max_volume", settings.MAX_VOLUME)),
}


class Library(BaseModel):
    id: str
    name: str


class Artist(BaseModel):
    id: str
    name: str
    image: Optional[str] = None


class Album(BaseModel):
    id: str
    name: str
    year: Optional[int] = None
    image: Optional[str] = None


class Track(BaseModel):
    id: str
    name: str
    duration: float
    image: Optional[str] = None


class QueueAction(BaseModel):
    track_id: str
    album_id: str


async def _apply_runtime_settings(force: bool = False) -> None:
    global _applied_runtime

    current = _runtime()
    desired = {
        "plex_url": current.get("plex_url", settings.PLEX_URL).rstrip("/"),
        "plex_token": current.get("plex_token", settings.PLEX_TOKEN),
        "audio_device": _effective_audio_device(current.get("audio_device", settings.AUDIO_DEVICE)),
        "max_volume": max(0, min(100, int(current.get("max_volume", settings.MAX_VOLUME)))),
    }

    async with _reconfigure_lock:
        if force or desired["plex_url"] != _applied_runtime["plex_url"] or desired["plex_token"] != _applied_runtime["plex_token"]:
            await plex.close()
            plex.base_url = desired["plex_url"]
            plex.token = desired["plex_token"]
            await plex.start()

        if force or desired["audio_device"] != _applied_runtime["audio_device"]:
            await player.stop()
            player.audio_device = desired["audio_device"]
            player.max_volume = desired["max_volume"]
            if player.audio_device != "mock":
                await player.start()
                await asyncio.sleep(1)
        else:
            player.max_volume = desired["max_volume"]

        await player.set_volume(desired["max_volume"])
        _applied_runtime = desired


async def _ensure_runtime_ready() -> None:
    await _apply_runtime_settings()


def _allowed_sections() -> List[str]:
    return [x.strip() for x in _runtime().get("allowed_sections", []) if x.strip()]


@app.get("/health")
async def health():
    await _ensure_runtime_ready()
    current = _runtime()
    allowed = _allowed_sections()
    return {
        "name": current.get("device_name", "Plex HMC Player"),
        "version": "0.1.0",
        "status": "online",
        "plex_url": current.get("plex_url", ""),
        "allowed_sections_count": len(allowed),
        "audio_device": player.audio_device,
    }


@app.get("/")
async def root():
    return FileResponse(os.path.join(frontend_dir, "index.html"))


@app.get("/libraries", response_model=List[Library])
async def get_libraries():
    await _ensure_runtime_ready()
    allowed = set(_allowed_sections())
    if not allowed:
        return []
    sections = await plex.get_sections()
    return [Library(id=s["id"], name=s["name"]) for s in sections if s.get("id") in allowed]


@app.get("/library/{library_id}/artists", response_model=List[Artist])
async def get_artists(library_id: str):
    await _ensure_runtime_ready()
    allowed = set(_allowed_sections())
    if library_id not in allowed:
        raise HTTPException(403, "Access denied to this library")
    artists = await plex.get_artists(library_id)
    return [Artist(id=a["id"], name=a["name"], image=a.get("image")) for a in artists]


@app.get("/artist/{artist_id}/albums", response_model=List[Album])
async def get_albums(artist_id: str):
    await _ensure_runtime_ready()
    albums = await plex.get_albums(artist_id)
    return [Album(id=a["id"], name=a["name"], year=a.get("year"), image=a.get("image")) for a in albums]


@app.get("/album/{album_id}/tracks", response_model=List[Track])
async def get_tracks(album_id: str):
    await _ensure_runtime_ready()
    tracks = await plex.get_tracks(album_id)
    return [Track(id=t["id"], name=t["name"], duration=float(t.get("duration", 0.0)), image=t.get("image")) for t in tracks]


@app.post("/play/album/{album_id}")
async def play_album(album_id: str, start_track_id: Optional[str] = None):
    await _ensure_runtime_ready()
    tracks = await plex.get_tracks(album_id)
    if not tracks:
        raise HTTPException(404, "Album not found or empty")
    start_index = 0
    if start_track_id:
        for i, t in enumerate(tracks):
            if t.get("id") == start_track_id:
                start_index = i
                break
    result = await player.play_album(tracks, start_index=start_index)
    return result


@app.get("/queue")
async def get_queue():
    await _ensure_runtime_ready()
    return {
        "queue": player.get_queue(),
        "current_index": player.current_track_index,
        "current_track": player.get_current_track(),
        "upcoming_tracks": player.get_upcoming_tracks(),
        "total_tracks": len(player.playback_queue),
    }


@app.post("/queue/play-now")
async def queue_play_now(action: QueueAction):
    await _ensure_runtime_ready()
    track = await _get_track_by_id(action.album_id, action.track_id)
    if not track:
        raise HTTPException(404, "Track not found")
    return await player.play_now(track)


@app.post("/queue/play-next")
async def queue_play_next(action: QueueAction):
    await _ensure_runtime_ready()
    track = await _get_track_by_id(action.album_id, action.track_id)
    if not track:
        raise HTTPException(404, "Track not found")
    return await player.play_next(track)


@app.post("/queue/add")
async def queue_add(action: QueueAction):
    await _ensure_runtime_ready()
    track = await _get_track_by_id(action.album_id, action.track_id)
    if not track:
        raise HTTPException(404, "Track not found")
    return await player.add_to_queue(track)


@app.delete("/queue/{index}")
async def queue_remove(index: int):
    await _ensure_runtime_ready()
    if index < 0 or index >= len(player.playback_queue):
        raise HTTPException(404, "Index out of range")
    if await player.remove_from_queue(index):
        return {"status": "removed", "index": index, "queue_length": len(player.playback_queue)}
    raise HTTPException(500, "Remove failed")


@app.post("/queue/jump/{index}")
async def queue_jump(index: int):
    await _ensure_runtime_ready()
    if index < 0 or index >= len(player.playback_queue):
        raise HTTPException(404, "Index out of range")
    return await player.jump_to_track(index)


@app.post("/queue/clear")
async def queue_clear():
    await _ensure_runtime_ready()
    await player.stop_playback()
    return {"status": "cleared", "queue_length": 0}


@app.post("/player/pause")
async def pause():
    await _ensure_runtime_ready()
    await player.pause()
    return await player.get_state()


@app.post("/player/resume")
async def resume():
    await _ensure_runtime_ready()
    await player.resume()
    return await player.get_state()


@app.post("/player/stop")
async def stop():
    await _ensure_runtime_ready()
    await player.stop_playback()
    return await player.get_state()


@app.post("/player/next")
async def next_track():
    await _ensure_runtime_ready()
    await player.next_track()
    return await player.get_state()


@app.post("/player/previous")
async def previous_track():
    await _ensure_runtime_ready()
    await player.previous_track()
    return await player.get_state()


@app.post("/player/seek")
async def seek(state: dict):
    await _ensure_runtime_ready()
    position = state.get("position")
    if position is None:
        raise HTTPException(400, "Position required")
    await player.seek(float(position))
    return await player.get_state()


@app.post("/player/volume")
async def set_volume(state: dict):
    await _ensure_runtime_ready()
    volume = state.get("volume")
    if volume is None:
        raise HTTPException(400, "Volume required")
    max_vol = max(0, min(100, int(_runtime().get("max_volume", settings.MAX_VOLUME))))
    clamped = min(int(volume), max_vol)
    await player.set_volume(clamped)
    return {"volume": clamped}


@app.get("/player/volume")
async def get_volume():
    await _ensure_runtime_ready()
    return {"volume": await player.get_volume()}


@app.get("/player/state")
async def get_state():
    await _ensure_runtime_ready()
    return await player.get_state()


async def _get_track_by_id(album_id: str, track_id: str) -> Optional[dict]:
    await _ensure_runtime_ready()
    tracks = await plex.get_tracks(album_id)
    for t in tracks:
        if t.get("id") == track_id:
            return t
    return None
