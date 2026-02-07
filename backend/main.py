from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
import asyncio
import contextlib
import os
import sys

from .config import settings
from .jellyfin_client import JellyfinClient
from .mpv_controller import MpvController, PlaybackState
from .policies import load_policies, get_policy, UserPolicy

# --- Lifecycle Management ---
@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print(f"✅ HMC v2.1 Starting...")
    load_policies()
    await jellyfin.start()
    
    if player.audio_device != "mock":
        await player.start()
        await asyncio.sleep(1)
        
    yield
    # Shutdown
    print(f"🛑 HMC v2.1 Stopping...")
    await player.stop()
    await jellyfin.close()

app = FastAPI(title="HMC v2.1", version="2.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Static Files ---
frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.exists(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

# --- Clients ---
jellyfin = JellyfinClient()

audio_device = settings.AUDIO_DEVICE
if sys.platform == "win32":
    audio_device = "mock"
    print("⚠️  Windows detected: Using Mock Player (no audio)")

player = MpvController(
    audio_device=audio_device,
    max_volume=60
)

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
    album_id: Optional[str] = None  # Optional: for fetching track details

# --- Endpoints ---

@app.get("/health")
def health():
    return {
        "name": "HMC v2.1", 
        "backend": "jellyfin", 
        "version": "2.1.0",
        "status": "online"
    }

@app.get("/")
async def root():
    return FileResponse(os.path.join(frontend_dir, "index.html"))

@app.get("/libraries", response_model=List[Library])
async def get_libraries(user_id: Optional[str] = None):
    policy = get_policy(user_id)
    all_libs = await jellyfin.get_libraries()
    
    allowed = [
        Library(id=lib["Id"], name=lib["Name"])
        for lib in all_libs
        if lib["Id"] in policy.allowed_libraries
    ]
    return allowed

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
        Track(
            id=t["id"], 
            name=t["name"], 
            duration=t["duration"],
            overview=t.get("overview"),
            image=t.get("image")
        )
        for t in tracks
    ]

@app.post("/play/album/{album_id}")
async def play_album(album_id: str, start_track_id: Optional[str] = None):
    """Legacy endpoint - plays entire album"""
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
        return result
    except Exception as e:
        raise HTTPException(500, f"Playback failed: {e}")

# ==========================================
# 🎵 PLAYBACK QUEUE API
# ==========================================

@app.get("/queue")
async def get_queue():
    """Get current playback queue with current track highlighted."""
    queue = player.get_queue()
    current_index = player.current_track_index
    
    return {
        "queue": queue,
        "current_index": current_index,
        "current_track": player.get_current_track(),
        "upcoming_tracks": player.get_upcoming_tracks(),
        "total_tracks": len(queue)
    }

@app.post("/queue/play-now")
async def queue_play_now(action: QueueAction):
    """
    Play track immediately.
    Stops current playback, clears queue, starts new track.
    """
    # Fetch track details
    track = await _get_track_by_id(action.track_id, action.album_id)
    if not track:
        raise HTTPException(404, "Track not found")
    
    try:
        result = await player.play_now(track)
        return result
    except Exception as e:
        raise HTTPException(500, f"Play now failed: {e}")

@app.post("/queue/play-next")
async def queue_play_next(action: QueueAction):
    """
    Add track to play next (after current track).
    Does not interrupt current playback.
    """
    track = await _get_track_by_id(action.track_id, action.album_id)
    if not track:
        raise HTTPException(404, "Track not found")
    
    try:
        result = await player.play_next(track)
        return result
    except Exception as e:
        raise HTTPException(500, f"Play next failed: {e}")

@app.post("/queue/add")
async def queue_add(action: QueueAction):
    """
    Add track to end of queue.
    Does not interrupt current playback.
    """
    track = await _get_track_by_id(action.track_id, action.album_id)
    if not track:
        raise HTTPException(404, "Track not found")
    
    try:
        result = await player.add_to_queue(track)
        return result
    except Exception as e:
        raise HTTPException(500, f"Add to queue failed: {e}")

@app.delete("/queue/{index}")
async def queue_remove(index: int):
    """Remove track at index from queue."""
    if index < 0 or index >= len(player.playback_queue):
        raise HTTPException(404, "Index out of range")
    
    try:
        success = await player.remove_from_queue(index)
        if success:
            return {
                "status": "removed",
                "index": index,
                "queue_length": len(player.playback_queue)
            }
        else:
            raise HTTPException(500, "Remove failed")
    except Exception as e:
        raise HTTPException(500, f"Remove failed: {e}")

@app.post("/queue/jump/{index}")
async def queue_jump(index: int):
    """Jump to specific track in queue."""
    if index < 0 or index >= len(player.playback_queue):
        raise HTTPException(404, "Index out of range")
    
    try:
        result = await player.jump_to_track(index)
        return result
    except Exception as e:
        raise HTTPException(500, f"Jump failed: {e}")

@app.post("/queue/clear")
async def queue_clear():
    """Clear entire queue and stop playback."""
    try:
        await player.stop_playback()
        return {
            "status": "cleared",
            "queue_length": 0
        }
    except Exception as e:
        raise HTTPException(500, f"Clear failed: {e}")

# ==========================================
# 🎵 PLAYBACK CONTROL (Existing + Updated)
# ==========================================

@app.post("/player/pause")
async def pause():
    await player.pause()
    return await player.get_state()

@app.post("/player/resume")
async def resume():
    await player.resume()
    return await player.get_state()

@app.post("/player/stop")
async def stop():
    """Stop playback and clear queue."""
    await player.stop_playback()
    return await player.get_state()

@app.post("/player/next")
async def next_track():
    await player.next_track()
    return await player.get_state()

@app.post("/player/previous")
async def previous_track():
    await player.previous_track()
    return await player.get_state()

@app.post("/player/seek")
async def seek(state: dict):
    position = state.get("position")
    if position is None:
        raise HTTPException(400, "Position required")
    await player.seek(position)
    return await player.get_state()

@app.post("/player/volume")
async def set_volume(state: dict):
    volume = state.get("volume")
    if volume is None:
         raise HTTPException(400, "Volume required")
    
    policy = get_policy()
    clamped = min(volume, policy.max_volume)
    await player.set_volume(clamped)
    return {"volume": clamped}

@app.get("/player/volume")
async def get_volume():
    vol = await player.get_volume()
    return {"volume": vol}

@app.get("/player/state")
async def get_state():
    return await player.get_state()

# ==========================================
# 🔧 HELPER FUNCTIONS
# ==========================================

async def _get_track_by_id(track_id: str, album_id: Optional[str] = None) -> Optional[dict]:
    """
    Helper to fetch track details by ID.
    If album_id is provided, fetch from that album.
    Otherwise, try to find track directly.
    """
    if album_id:
        # Fetch all tracks from album
        tracks = await jellyfin.get_tracks(album_id)
        # Find matching track
        for track in tracks:
            if track["id"] == track_id:
                return track
        return None
    else:
        # Try to fetch track directly (might not work for all Jellyfin setups)
        # For now, we require album_id
        raise HTTPException(400, "album_id required for track lookup")