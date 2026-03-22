from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
import asyncio
import contextlib
import os
import subprocess
import sys

from .config import settings
from .jellyfin_client import JellyfinClient
from .mpv_controller import MpvController, PlaybackState
from .policies import load_policies, get_policy, UserPolicy
from .mqtt_client import MqttClient
from .admin import router as admin_router

# --- Lifecycle Management ---
@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"✅ HMC v2.1 Starting...")
    load_policies()
    await jellyfin.start()

    if player.audio_device != "mock":
        await player.start()
        await asyncio.sleep(1)

    mqtt.on_command = _handle_mqtt_command
    await mqtt.start()

    _state_task = asyncio.create_task(_state_push_loop())

    yield

    print(f"🛑 HMC v2.1 Stopping...")
    _state_task.cancel()
    await mqtt.stop()
    await player.stop()
    await jellyfin.close()


app = FastAPI(title="HMC v2.1", version="2.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(admin_router)

# --- Static Files ---
frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.exists(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

# --- Clients ---
jellyfin = JellyfinClient()
mqtt     = MqttClient()

audio_device = settings.AUDIO_DEVICE
if sys.platform == "win32":
    audio_device = "mock"
    print("⚠️  Windows detected: Using Mock Player (no audio)")

player = MpvController(audio_device=audio_device, max_volume=60)


# --- Models ---
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
    overview: Optional[str] = None
    image: Optional[str] = None

class QueueAction(BaseModel):
    track_id: str
    album_id: Optional[str] = None


# ==========================================
# 🔁 MQTT Helpers
# ==========================================

async def _push_state():
    state = await player.get_state()
    vol   = await player.get_volume()
    state["volume"] = vol
    await mqtt.publish_state(state)

async def _state_push_loop():
    while True:
        try:
            await _push_state()
        except Exception:
            pass
        await asyncio.sleep(5)

async def _handle_mqtt_command(command: str):
    cmd = command.strip().lower()
    try:
        if cmd == "pause":
            await player.pause()
        elif cmd in ("resume", "play"):
            await player.resume()
            _screen_on()
        elif cmd == "stop":
            await player.stop_playback()
        elif cmd == "play_pause":
            state = await player.get_state()
            if state["state"] == "playing":
                await player.pause()
            else:
                await player.resume()
                _screen_on()
        elif cmd == "next":
            await player.next_track()
        elif cmd == "previous":
            await player.previous_track()
        else:
            print(f"⚠️  Unbekanntes MQTT Kommando: {cmd}")
            return
        await _push_state()
    except Exception as e:
        print(f"❌ MQTT command handler Fehler: {e}")


# ==========================================
# 💡 Bildschirm-Steuerung (xset DPMS)
# ==========================================

def _xset(cmd: str):
    """Führt xset aus — funktioniert nur auf dem Pi (X11), nicht auf Windows."""
    if sys.platform == "win32":
        return
    try:
        subprocess.run(
            ["xset"] + cmd.split(),
            env={**os.environ, "DISPLAY": ":0"},
            timeout=2,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as e:
        print(f"xset Fehler: {e}")

def _screen_off():
    _xset("dpms force off")

def _screen_on():
    _xset("dpms force on")


# ==========================================
# 📡 REST Endpoints
# ==========================================

@app.get("/health")
def health():
    return {
        "name":    "HMC v2.1",
        "backend": "jellyfin",
        "version": "2.1.0",
        "status":  "online",
        "mqtt":    settings.MQTT_DEVICE_ID,
    }

@app.get("/")
async def root():
    return FileResponse(os.path.join(frontend_dir, "index.html"))

@app.get("/libraries", response_model=List[Library])
async def get_libraries(user_id: Optional[str] = None):
    policy   = get_policy(user_id)
    all_libs = await jellyfin.get_libraries()
    return [
        Library(id=lib["Id"], name=lib["Name"])
        for lib in all_libs
        if lib["Id"] in policy.allowed_libraries
    ]

@app.get("/library/{library_id}/artists", response_model=List[Artist])
async def get_artists(library_id: str, user_id: Optional[str] = None):
    policy = get_policy(user_id)
    if library_id not in policy.allowed_libraries:
        raise HTTPException(403, "Access denied to this library")
    artists = await jellyfin.get_artists(library_id)
    return [
        Artist(
            id=artist["Id"],
            name=artist["Name"],
            image=jellyfin.get_image_url(artist["Id"]) if artist.get("ImageTags", {}).get("Primary") else None
        )
        for artist in artists
    ]

@app.get("/artist/{artist_id}/albums", response_model=List[Album])
async def get_albums(artist_id: str):
    albums = await jellyfin.get_albums(artist_id)
    return [
        Album(
            id=album["Id"],
            name=album["Name"],
            year=album.get("ProductionYear"),
            image=jellyfin.get_image_url(album["Id"]) if album.get("ImageTags", {}).get("Primary") else None
        )
        for album in albums
    ]

@app.get("/album/{album_id}/tracks", response_model=List[Track])
async def get_tracks(album_id: str):
    tracks = await jellyfin.get_tracks(album_id)
    return [
        Track(id=t["id"], name=t["name"], duration=t["duration"],
              overview=t.get("overview"), image=t.get("image"))
        for t in tracks
    ]

@app.post("/play/album/{album_id}")
async def play_album(album_id: str, start_track_id: Optional[str] = None):
    tracks = await jellyfin.get_tracks(album_id)
    if not tracks:
        raise HTTPException(404, "Album not found or empty")
    start_index = 0
    if start_track_id:
        try:
            start_index = next(i for i, t in enumerate(tracks) if t["id"] == start_track_id)
        except StopIteration:
            pass
    try:
        result = await player.play_album(tracks, start_index=start_index)
        _screen_on()
        await _push_state()
        return result
    except Exception as e:
        raise HTTPException(500, f"Playback failed: {e}")


# ==========================================
# 💡 Bildschirm-Endpoints (vom Frontend gerufen)
# ==========================================

@app.post("/screen/off")
async def screen_off():
    """Frontend ruft dies wenn der Bildschirmschoner aktiviert werden soll."""
    _screen_off()
    return {"status": "off"}

@app.post("/screen/on")
async def screen_on():
    """Frontend ruft dies bei Touch-Interaktion wenn der Screen aus war."""
    _screen_on()
    return {"status": "on"}


# ==========================================
# 🎵 PLAYBACK QUEUE API
# ==========================================

@app.get("/queue")
async def get_queue():
    return {
        "queue":           player.get_queue(),
        "current_index":   player.current_track_index,
        "current_track":   player.get_current_track(),
        "upcoming_tracks": player.get_upcoming_tracks(),
        "total_tracks":    len(player.playback_queue),
    }

@app.post("/queue/play-now")
async def queue_play_now(action: QueueAction):
    track = await _get_track_by_id(action.track_id, action.album_id)
    if not track: raise HTTPException(404, "Track not found")
    try:
        result = await player.play_now(track)
        _screen_on()
        await _push_state()
        return result
    except Exception as e:
        raise HTTPException(500, f"Play now failed: {e}")

@app.post("/queue/play-next")
async def queue_play_next(action: QueueAction):
    track = await _get_track_by_id(action.track_id, action.album_id)
    if not track: raise HTTPException(404, "Track not found")
    try:
        result = await player.play_next(track)
        await _push_state()
        return result
    except Exception as e:
        raise HTTPException(500, f"Play next failed: {e}")

@app.post("/queue/add")
async def queue_add(action: QueueAction):
    track = await _get_track_by_id(action.track_id, action.album_id)
    if not track: raise HTTPException(404, "Track not found")
    try:
        result = await player.add_to_queue(track)
        await _push_state()
        return result
    except Exception as e:
        raise HTTPException(500, f"Add to queue failed: {e}")

@app.delete("/queue/{index}")
async def queue_remove(index: int):
    if index < 0 or index >= len(player.playback_queue):
        raise HTTPException(404, "Index out of range")
    try:
        if await player.remove_from_queue(index):
            await _push_state()
            return {"status": "removed", "index": index, "queue_length": len(player.playback_queue)}
        raise HTTPException(500, "Remove failed")
    except Exception as e:
        raise HTTPException(500, f"Remove failed: {e}")

@app.post("/queue/jump/{index}")
async def queue_jump(index: int):
    if index < 0 or index >= len(player.playback_queue):
        raise HTTPException(404, "Index out of range")
    try:
        result = await player.jump_to_track(index)
        await _push_state()
        return result
    except Exception as e:
        raise HTTPException(500, f"Jump failed: {e}")

@app.post("/queue/clear")
async def queue_clear():
    try:
        await player.stop_playback()
        await _push_state()
        return {"status": "cleared", "queue_length": 0}
    except Exception as e:
        raise HTTPException(500, f"Clear failed: {e}")


# ==========================================
# 🎵 PLAYBACK CONTROL
# ==========================================

@app.post("/player/pause")
async def pause():
    await player.pause()
    await _push_state()
    return await player.get_state()

@app.post("/player/resume")
async def resume():
    await player.resume()
    _screen_on()
    await _push_state()
    return await player.get_state()

@app.post("/player/stop")
async def stop():
    await player.stop_playback()
    await _push_state()
    return await player.get_state()

@app.post("/player/next")
async def next_track():
    await player.next_track()
    await _push_state()
    return await player.get_state()

@app.post("/player/previous")
async def previous_track():
    await player.previous_track()
    await _push_state()
    return await player.get_state()

@app.post("/player/seek")
async def seek(state: dict):
    position = state.get("position")
    if position is None: raise HTTPException(400, "Position required")
    await player.seek(position)
    await _push_state()
    return await player.get_state()

@app.post("/player/volume")
async def set_volume(state: dict):
    volume = state.get("volume")
    if volume is None: raise HTTPException(400, "Volume required")
    clamped = min(volume, get_policy().max_volume)
    await player.set_volume(clamped)
    await _push_state()
    return {"volume": clamped}

@app.get("/player/volume")
async def get_volume():
    return {"volume": await player.get_volume()}

@app.get("/player/state")
async def get_state():
    return await player.get_state()


# ==========================================
# 🔧 HELPER
# ==========================================

async def _get_track_by_id(track_id: str, album_id: Optional[str] = None) -> Optional[dict]:
    if album_id:
        for track in await jellyfin.get_tracks(album_id):
            if track["id"] == track_id:
                return track
        return None
    raise HTTPException(400, "album_id required for track lookup")
