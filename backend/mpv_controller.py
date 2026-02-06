import asyncio
import json
import socket
import subprocess
import sys
from enum import Enum
from pathlib import Path
from typing import Optional, List, Callable, Dict, Any

class PlaybackState(str, Enum):
    IDLE = "idle"
    LOADING = "loading"
    PLAYING = "playing"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"

class MpvController:
    """
    Robust MPV Controller with state management, process monitoring,
    and event handling.
    """
    def __init__(self, audio_device: str = "hw:1,0", max_volume: int = 60):
        self.audio_device = audio_device
        self.max_volume = max_volume
        self.socket_path = "/tmp/hmc-mpv.sock"
        
        self.process: Optional[subprocess.Popen] = None
        self._shutdown_event = asyncio.Event()
        self._ipc_task: Optional[asyncio.Task] = None
        
        # State
        self.state = PlaybackState.IDLE
        self.current_playlist: List[dict] = []
        self.current_track_index = 0
        self.duration = 0.0
        self.position = 0.0
        
        # Callbacks for state changes (optional)
        self.on_state_change: Optional[Callable[[PlaybackState], None]] = None

    async def start(self):
        """Starts the MPV process and the IPC listener task."""
        if self.process:
            return # Already running

        self._shutdown_event.clear()
        
        # 1. Start MPV Process
        if self.audio_device == "mock":
            print("MOCK PLAYER: Starting mock process")
            # For mock, we don't actually start a process, but we simulate state
            self.state = PlaybackState.IDLE
            return

        cmd = [
            "mpv",
            f"--audio-device=alsa/{self.audio_device}",
            f"--volume={self.max_volume}",
            "--no-video",
            "--input-ipc-server=" + self.socket_path,
            "--idle=yes",  # Keep process alive
            "--keep-open=yes" # Do not terminate after file end
        ]

        print(f"Starting MPV: {' '.join(cmd)}")
        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        # 2. Wait for socket to appear
        # Increased timeout to 5 seconds for slower Pis
        for _ in range(50): 
            if Path(self.socket_path).exists():
                # Give MPV a moment to actually bind to the socket
                await asyncio.sleep(0.5)
                break
            await asyncio.sleep(0.1)
        else:
            print("❌ MPV Socket not found after start!")
            self.state = PlaybackState.ERROR
            return

        # 3. Start IPC Listener
        self._ipc_task = asyncio.create_task(self._ipc_loop())
        self._monitor_task = asyncio.create_task(self._monitor_process())
        self.state = PlaybackState.IDLE
        
        # 4. Observe properties
        # Moved to _ipc_loop to ensure they are registered on the listening connection
        pass

    async def stop(self):
        """Stops the MPV process and cleans up."""
        self._shutdown_event.set()
        
        if self._ipc_task:
            try:
                self._ipc_task.cancel()
                await self._ipc_task
            except asyncio.CancelledError:
                pass
            self._ipc_task = None

        if self.process:
            if self.audio_device != "mock":
                self.process.terminate()
                try:
                    self.process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self.process.kill()
            self.process = None

        if Path(self.socket_path).exists():
            try:
                Path(self.socket_path).unlink()
            except OSError:
                pass
        
        self.state = PlaybackState.STOPPED
        self.current_playlist = []
        self.current_track_index = 0

    async def play_album(self, tracks: List[dict], start_index: int = 0):
        """Plays a list of tracks."""
        if not tracks:
            raise ValueError("No tracks provided")

        # Idempotency check: If playing same playlist and same start index, do nothing (or just resume)
        # We compare the first track URL as a simple signature
        if (self.state == PlaybackState.PLAYING and 
            self.current_playlist and 
            len(tracks) == len(self.current_playlist) and 
            tracks[0]['url'] == self.current_playlist[0]['url'] and
            self.current_track_index == start_index):
            
            print("Ignoring request to restart currently playing album/track.")
            return {
                "status": "playing",
                "tracks": len(tracks),
                "current": tracks[start_index]
            }

        # Ensure MPV is running
        if not self.process and self.audio_device != "mock":
            await self.start()
        
        self.current_playlist = tracks
        self.current_track_index = start_index
        self.state = PlaybackState.LOADING

        if self.audio_device == "mock":
            print(f"MOCK PLAYER: Playing {len(tracks)} tracks from index {start_index}")
            self.state = PlaybackState.PLAYING
            return {
                "status": "playing",
                "tracks": len(tracks),
                "current": tracks[start_index]
            }

        # Create Playlist File
        playlist_path = "/tmp/hmc-playlist.m3u"
        with open(playlist_path, 'w') as f:
            for track in tracks:
                f.write(f"{track['url']}\n")

        # Load Playlist
        await self._send_command(["loadlist", playlist_path, "replace"])
        
        # Jump to start index if needed
        if start_index > 0:
             await self._send_command(["playlist-play-index", str(start_index)])
        
        # Ensure playback starts
        await self._send_command(["set_property", "pause", False])
        
        return {
            "status": "playing",
            "tracks": len(tracks),
            "current": tracks[start_index] if start_index < len(tracks) else None
        }

    async def pause(self):
        if self.audio_device == "mock":
            self.state = PlaybackState.PAUSED
            return
        await self._send_command(["set_property", "pause", True])

    async def resume(self):
        if self.audio_device == "mock":
            self.state = PlaybackState.PLAYING
            return
        await self._send_command(["set_property", "pause", False])
    
    async def next_track(self):
        if self.audio_device == "mock":
            self.current_track_index = min(len(self.current_playlist) - 1, self.current_track_index + 1)
            return
        await self._send_command(["playlist-next"])

    async def previous_track(self):
        if self.audio_device == "mock":
             self.current_track_index = max(0, self.current_track_index - 1)
             return
        await self._send_command(["playlist-prev"])

    async def seek(self, position: float):
        """Seek to absolute position"""
        if self.audio_device == "mock":
            self.position = position
            return
        await self._send_command(["seek", str(position), "absolute"])

    async def set_volume(self, volume: int):
        if self.audio_device == "mock":
            return
        await self._send_command(["set_property", "volume", volume])

    async def get_volume(self) -> int:
        """Get current volume"""
        if self.audio_device == "mock":
            return 60
        
        result = await self._send_command(["get_property", "volume"])
        return int(result.get("data", 60)) if result else 60

    async def get_state(self) -> dict:
        return {
            "state": self.state,
            "position": self.position,
            "duration": self.duration,
            "current_track_index": self.current_track_index,
            "current_track": self.current_playlist[self.current_track_index] if 0 <= self.current_track_index < len(self.current_playlist) else None,
            "total_tracks": len(self.current_playlist)
        }

    async def _send_command(self, command: List[Any]) -> Optional[Dict]:
        """Sends a JSON IPC command."""
        if self.audio_device == "mock":
            return None

        try:
            reader, writer = await asyncio.open_unix_connection(self.socket_path)
            cmd_str = json.dumps({"command": command}) + "\n"
            writer.write(cmd_str.encode())
            await writer.drain()
            
            line = await reader.readline()
            writer.close()
            await writer.wait_closed()
            
            if line:
                return json.loads(line)
        except Exception as e:
            print(f"IPC Send Error: {e}")
            return None
        return None

    async def _monitor_process(self):
        """Monitor MPV process and restart if crashed"""
        while not self._shutdown_event.is_set():
            if self.process and self.process.poll() is not None:
                # Process died
                print("⚠️ MPV Process died, restarting...")
                self.state = PlaybackState.ERROR
                self.process = None
                
                # Attempt restart with current playlist
                if self.current_playlist:
                    await asyncio.sleep(2)
                    try:
                        await self.play_album(self.current_playlist, self.current_track_index)
                    except Exception as e:
                        print(f"❌ Restart failed: {e}")
            
            await asyncio.sleep(1)

    async def _ipc_loop(self):
        """Continuous loop to read events from MPV socket."""
        # Wait for socket to appear initially
        for _ in range(30):  # 3 seconds
            if Path(self.socket_path).exists():
                break
            await asyncio.sleep(0.1)

        while not self._shutdown_event.is_set():
            try:
                reader, writer = await asyncio.open_unix_connection(self.socket_path)
                
                # Register observers on THIS persistent connection
                observers = [
                    '{"command": ["observe_property", 1, "pause"]}\n',
                    '{"command": ["observe_property", 2, "time-pos"]}\n',
                    '{"command": ["observe_property", 3, "duration"]}\n',
                    '{"command": ["observe_property", 4, "playlist-pos"]}\n',
                    '{"command": ["observe_property", 5, "idle-active"]}\n'
                ]
                for obs in observers:
                    writer.write(obs.encode())
                await writer.drain()

                # We stay connected to receive events
                while not self._shutdown_event.is_set():
                    line = await reader.readline()
                    if not line:
                        break # Connection closed
                    
                    try:
                        data = json.loads(line)
                        if "event" in data:
                            self._handle_event(data)
                    except json.JSONDecodeError:
                        pass
                
                writer.close()
                await writer.wait_closed()
            
            except (ConnectionRefusedError, FileNotFoundError):
                # Socket not ready or MPV died
                if not self._shutdown_event.is_set():
                    print("⚠️ Lost connection to MPV, retrying...")
                    await asyncio.sleep(1)
            except Exception as e:
                print(f"IPC Loop Error: {e}")
                await asyncio.sleep(1)

    def _handle_event(self, event: dict):
        evt_name = event.get("event")
        
        if evt_name == "property-change":
            name = event.get("name")
            value = event.get("data")
            
            if name == "pause":
                self.state = PlaybackState.PAUSED if value else PlaybackState.PLAYING
            elif name == "time-pos" and value is not None:
                self.position = float(value)
            elif name == "duration" and value is not None:
                self.duration = float(value)
            elif name == "playlist-pos" and value is not None:
                self.current_track_index = int(value)
            elif name == "idle-active":
                 if value is True:
                     self.state = PlaybackState.IDLE

        elif evt_name == "end-file":
            reason = event.get("reason")
            if reason == "error":
                self.state = PlaybackState.ERROR
            elif reason == "eof":
                # Check if playlist ended? 
                # Usually MPV handles playlist navigation internally
                pass

