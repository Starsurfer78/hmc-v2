import json
import socket
import subprocess
import asyncio
from typing import Optional, List
from pathlib import Path

class MPVPlayer:
    """MPV Player mit IPC Socket Control"""
    
    def __init__(self, audio_device: str = "hw:1,0", max_volume: int = 60):
        self.audio_device = audio_device
        self.max_volume = max_volume
        self.socket_path = "/tmp/hmc-mpv.sock"
        self.process: Optional[subprocess.Popen] = None
        self.current_playlist: List[dict] = []
        self.current_index = 0
    
    async def play_album(self, tracks: List[dict], start_index: int = 0):
        """Spiele komplettes Album ab (alle Tracks), optional ab start_index"""
        await self.stop()
        
        if not tracks:
            raise ValueError("No tracks provided")
        
        # Starte MPV mit IPC (nur wenn nicht Windows/Mock)
        if self.audio_device == "mock":
             print(f"MOCK PLAYER: Playing {len(tracks)} tracks, starting at {start_index}")
             self.current_playlist = tracks
             self.current_index = start_index
             return {
                "status": "playing",
                "tracks": len(tracks),
                "current": tracks[start_index] if tracks and len(tracks) > start_index else None
            }

        # Erstelle M3U Playlist
        playlist_path = "/tmp/hmc-playlist.m3u"
        with open(playlist_path, 'w') as f:
            for track in tracks:
                f.write(f"{track['url']}\n")

        cmd = [
            "mpv",
            f"--audio-device=alsa/{self.audio_device}",
            f"--volume={self.max_volume}",
            "--no-video",
            "--input-ipc-server=" + self.socket_path,
            "--idle=yes",  # Bleibt nach Playlist aktiv
            f"--playlist-start={start_index}",
            playlist_path
        ]
        
        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        
        self.current_playlist = tracks
        self.current_index = start_index
        
        # Warte bis Socket bereit ist
        await asyncio.sleep(0.5)
        
        return {
            "status": "playing",
            "tracks": len(tracks),
            "current": tracks[start_index] if tracks and len(tracks) > start_index else None
        }
    
    async def _send_command(self, command: dict) -> dict:
        """Sende IPC Command an MPV"""
        if self.audio_device == "mock":
            return {"data": None, "error": None}

        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect(self.socket_path)
            
            # Command senden
            sock.sendall((json.dumps(command) + "\n").encode())
            
            # Antwort lesen
            response = sock.recv(4096).decode()
            sock.close()
            
            return json.loads(response)
        except Exception as e:
            print(f"IPC Error: {e}")
            return {"error": str(e)}
    
    async def pause(self):
        """Pause"""
        return await self._send_command({"command": ["set_property", "pause", True]})
    
    async def resume(self):
        """Resume"""
        return await self._send_command({"command": ["set_property", "pause", False]})
    
    async def stop(self):
        """Stoppe komplett"""
        if self.audio_device == "mock":
            self.current_playlist = []
            return

        if self.process:
            await self._send_command({"command": ["quit"]})
            self.process.wait(timeout=2)
            self.process = None
            self.current_playlist = []
            
        # Cleanup Socket
        if Path(self.socket_path).exists():
            Path(self.socket_path).unlink()
    
    async def next_track(self):
        """Nächster Track"""
        return await self._send_command({"command": ["playlist-next"]})
    
    async def previous_track(self):
        """Vorheriger Track"""
        return await self._send_command({"command": ["playlist-prev"]})
    
    async def get_state(self) -> dict:
        """Hole aktuellen Status"""
        if not self.process or self.process.poll() is not None:
            return {"state": "stopped", "playlist": []}
        
        # Hole Properties via IPC
        paused = await self._send_command({"command": ["get_property", "pause"]})
        position = await self._send_command({"command": ["get_property", "time-pos"]})
        duration = await self._send_command({"command": ["get_property", "duration"]})
        playlist_pos = await self._send_command({"command": ["get_property", "playlist-pos"]})
        
        state = "paused" if paused.get("data") else "playing"
        
        return {
            "state": state,
            "position": position.get("data", 0),
            "duration": duration.get("data", 0),
            "current_track": playlist_pos.get("data", 0),
            "total_tracks": len(self.current_playlist)
        }