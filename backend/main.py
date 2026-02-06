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
    
    # Start Player if not mock (Mock starts on demand/lazily for now, but good practice to explicit start)
    if player.audio_device != "mock":
        await player.start()
        # Wait for IPC to be ready
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
# Ensure directory exists to avoid startup error if missing
if os.path.exists(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

# --- Clients ---
jellyfin = JellyfinClient()

# Initialize Player (MPV)
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
    # 1. Get tracks
    tracks = await jellyfin.get_tracks(album_id)
    if not tracks:
        raise HTTPException(404, "Album not found or empty")
    
    # 2. Find start index if start_track_id provided
    start_index = 0
    if start_track_id:
        try:
            start_index = next(i for i, t in enumerate(tracks) if t["id"] == start_track_id)
        except StopIteration:
            # Track not found in this album, ignore or error? 
            # Ignoring is safer, just play from start
            pass

    # 3. Start Player
    try:
        result = await player.play_album(tracks, start_index=start_index)
        return result
    except Exception as e:
        raise HTTPException(500, f"Playback failed: {e}")

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
    await player.stop()
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
    """Seek to position in seconds. Expects JSON: {"position": float}"""
    position = state.get("position")
    if position is None:
        raise HTTPException(400, "Position required")
    await player.seek(position)
    return await player.get_state()

@app.post("/player/volume")
async def set_volume(state: dict):
    """Set volume (0-max_volume). Expects JSON: {"volume": int}"""
    volume = state.get("volume")
    if volume is None:
         raise HTTPException(400, "Volume required")
    
    policy = get_policy()
    clamped = min(volume, policy.max_volume)
    await player.set_volume(clamped)
    return {"volume": clamped}

@app.get("/player/volume")
async def get_volume():
    """Get current volume"""
    vol = await player.get_volume()
    return {"volume": vol}

@app.get("/player/state")
async def get_state():
    return await player.get_state()
