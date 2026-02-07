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
    event handling, and playback queue management.
    """
    def __init__(self, audio_device: str = "hw:1,0", max_volume: int = 60):
        self.audio_device = audio_device
        self.max_volume = max_volume
        self.socket_path = "/tmp/hmc-mpv.sock"
        
        self.process: Optional[subprocess.Popen] = None
        self._shutdown_event = asyncio.Event()
        self._ipc_task: Optional[asyncio.Task] = None
        self._monitor_task: Optional[asyncio.Task] = None
        
        # State
        self.state = PlaybackState.IDLE
        
        # ==========================================
        # 🎵 PLAYBACK QUEUE (Wiedergabeliste)
        # ==========================================
        self.playback_queue: List[dict] = []  # Ordered list of tracks
        self.current_track_index = 0  # Index in playback_queue
        
        self.duration = 0.0
        self.position = 0.0
        
        # Callbacks for state changes (optional)
        self.on_state_change: Optional[Callable[[PlaybackState], None]] = None
        self.on_track_change: Optional[Callable[[dict], None]] = None

    async def start(self):
        """Starts the MPV process and the IPC listener task."""
        if self.process:
            return # Already running

        self._shutdown_event.clear()
        
        # 1. Start MPV Process
        if self.audio_device == "mock":
            print("MOCK PLAYER: Starting mock process")
            self.state = PlaybackState.IDLE
            return

        cmd = [
            "mpv",
            f"--audio-device=alsa/{self.audio_device}",
            f"--volume={self.max_volume}",
            "--no-video",
            "--input-ipc-server=" + self.socket_path,
            "--idle=yes",
            "--keep-open=no"  # Changed: Auto-advance to next track
        ]

        print(f"Starting MPV: {' '.join(cmd)}")
        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        # 2. Wait for socket to appear
        for _ in range(50): 
            if Path(self.socket_path).exists():
                await asyncio.sleep(0.5)
                break
            await asyncio.sleep(0.1)
        else:
            print("❌ MPV Socket not found after start!")
            self.state = PlaybackState.ERROR
            return

        # 3. Start IPC Listener & Monitor
        self._ipc_task = asyncio.create_task(self._ipc_loop())
        self._monitor_task = asyncio.create_task(self._monitor_process())
        self.state = PlaybackState.IDLE

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

        if self._monitor_task:
            try:
                self._monitor_task.cancel()
                await self._monitor_task
            except asyncio.CancelledError:
                pass
            self._monitor_task = None

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
        self.clear_queue()

    # ==========================================
    # 🎵 PLAYBACK QUEUE MANAGEMENT
    # ==========================================
    
    def clear_queue(self):
        """Clear the entire playback queue."""
        self.playback_queue = []
        self.current_track_index = 0
        self.duration = 0.0
        self.position = 0.0
    
    def get_queue(self) -> List[dict]:
        """Get the current playback queue."""
        return self.playback_queue.copy()
    
    def get_upcoming_tracks(self) -> List[dict]:
        """Get only upcoming tracks (not including current)."""
        if self.current_track_index < len(self.playback_queue) - 1:
            return self.playback_queue[self.current_track_index + 1:]
        return []
    
    def get_current_track(self) -> Optional[dict]:
        """Get the currently playing track."""
        if 0 <= self.current_track_index < len(self.playback_queue):
            return self.playback_queue[self.current_track_index]
        return None
    
    async def play_now(self, track: dict):
        """
        Play a single track immediately.
        Stops current playback, clears queue, adds track, starts playback.
        """
        # Clear queue and add single track
        self.clear_queue()
        self.playback_queue = [track]
        self.current_track_index = 0
        
        # Start playback
        await self._play_current_track()
        return {
            "status": "playing",
            "action": "play_now",
            "track": track,
            "queue_length": 1
        }
    
    async def play_next(self, track: dict):
        """
        Insert track to play next (after current track).
        Does not interrupt current playback.
        """
        if not self.playback_queue:
            # Queue is empty, treat as play_now
            return await self.play_now(track)
        
        # Insert after current index
        insert_position = self.current_track_index + 1
        self.playback_queue.insert(insert_position, track)
        
        return {
            "status": "queued",
            "action": "play_next",
            "track": track,
            "position": insert_position,
            "queue_length": len(self.playback_queue)
        }
    
    async def add_to_queue(self, track: dict):
        """
        Add track to the end of the queue.
        Does not interrupt current playback.
        """
        if not self.playback_queue:
            # Queue is empty, treat as play_now
            return await self.play_now(track)
        
        self.playback_queue.append(track)
        
        return {
            "status": "queued",
            "action": "add_to_queue",
            "track": track,
            "position": len(self.playback_queue) - 1,
            "queue_length": len(self.playback_queue)
        }
    
    async def remove_from_queue(self, index: int) -> bool:
        """
        Remove track at index from queue.
        Special handling if removing currently playing track.
        """
        if index < 0 or index >= len(self.playback_queue):
            return False
        
        # Special case: Removing currently playing track
        if index == self.current_track_index:
            # If it's the last track, stop playback (which clears queue)
            if index == len(self.playback_queue) - 1:
                await self.stop_playback()
                return True

            # Skip to next track (or stop if last)
            await self.next_track()
            # Adjust index after next_track incremented it
            self.playback_queue.pop(index)
            if self.current_track_index > 0:
                self.current_track_index -= 1
        else:
            # Simple remove
            self.playback_queue.pop(index)
            # Adjust current index if we removed something before it
            if index < self.current_track_index:
                self.current_track_index -= 1
        
        return True
    
    async def jump_to_track(self, index: int):
        """
        Jump to specific track in queue and start playing.
        """
        if index < 0 or index >= len(self.playback_queue):
            raise ValueError(f"Index {index} out of range")
        
        self.current_track_index = index
        await self._play_current_track()
        
        return {
            "status": "playing",
            "action": "jump_to_track",
            "track": self.get_current_track(),
            "index": index
        }

    # ==========================================
    # 🎵 PLAYBACK CONTROL (Updated for Queue)
    # ==========================================
    
    async def play_album(self, tracks: List[dict], start_index: int = 0):
        """
        Play an album (replaces queue with all tracks).
        This is the legacy method - now uses queue system.
        """
        if not tracks:
            raise ValueError("No tracks provided")

        # Check idempotency
        if (self.state == PlaybackState.PLAYING and 
            self.playback_queue and 
            len(tracks) == len(self.playback_queue) and 
            tracks[0]['url'] == self.playback_queue[0]['url'] and
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
        
        # Replace queue with album
        self.playback_queue = tracks
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

        # Play current track
        await self._play_current_track()
        
        return {
            "status": "playing",
            "tracks": len(tracks),
            "current": tracks[start_index]
        }

    async def _play_current_track(self):
        """Internal: Play the track at current_track_index."""
        current_track = self.get_current_track()
        if not current_track:
            print("No track to play at current index")
            self.state = PlaybackState.IDLE
            return
        
        if self.audio_device == "mock":
            print(f"MOCK PLAYER: Playing track {self.current_track_index}: {current_track['name']}")
            self.state = PlaybackState.PLAYING
            return
        
        # Load track in MPV
        url = current_track['url']
        await self._send_command(["loadfile", url, "replace"])
        await self._send_command(["set_property", "pause", False])
        
        self.state = PlaybackState.PLAYING
        
        # Trigger callback if set
        if self.on_track_change:
            self.on_track_change(current_track)

    async def next_track(self):
        """Skip to next track in queue."""
        if self.audio_device == "mock":
            self.current_track_index = min(len(self.playback_queue) - 1, self.current_track_index + 1)
            return
        
        # Check if there is a next track
        if self.current_track_index < len(self.playback_queue) - 1:
            self.current_track_index += 1
            await self._play_current_track()
        else:
            # No more tracks, stop playback
            print("End of queue reached")
            await self.stop_playback()

    async def previous_track(self):
        """
        Go to previous track.
        If position > 3s, restart current track.
        Otherwise, go to actual previous track.
        """
        if self.audio_device == "mock":
            self.current_track_index = max(0, self.current_track_index - 1)
            return
        
        # If more than 3 seconds into track, restart it
        if self.position > 3.0:
            await self.seek(0)
        else:
            # Go to previous track if available
            if self.current_track_index > 0:
                self.current_track_index -= 1
                await self._play_current_track()
            else:
                # Already at first track, just restart it
                await self.seek(0)

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

    async def stop_playback(self):
        """
        Stop playback and clear queue.
        Different from stop() which kills the process.
        """
        if self.audio_device == "mock":
            self.state = PlaybackState.STOPPED
            self.clear_queue()
            return
        
        await self._send_command(["stop"])
        self.state = PlaybackState.STOPPED
        self.clear_queue()

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
            "current_track": self.get_current_track(),
            "total_tracks": len(self.playback_queue),
            "queue": self.get_queue(),
            "upcoming_tracks": self.get_upcoming_tracks()
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
                
                # Attempt restart with current queue
                if self.playback_queue:
                    await asyncio.sleep(2)
                    try:
                        await self._play_current_track()
                    except Exception as e:
                        print(f"❌ Restart failed: {e}")
            
            await asyncio.sleep(1)

    async def _ipc_loop(self):
        """Continuous loop to read events from MPV socket."""
        # Wait for socket to appear initially
        for _ in range(30):
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
                    '{"command": ["observe_property", 5, "idle-active"]}\n',
                    '{"command": ["observe_property", 6, "eof-reached"]}\n'
                ]
                for obs in observers:
                    writer.write(obs.encode())
                await writer.drain()

                # Stay connected to receive events
                while not self._shutdown_event.is_set():
                    line = await reader.readline()
                    if not line:
                        break
                    
                    try:
                        data = json.loads(line)
                        if "event" in data:
                            await self._handle_event(data)
                    except json.JSONDecodeError:
                        pass
                
                writer.close()
                await writer.wait_closed()
            
            except (ConnectionRefusedError, FileNotFoundError):
                if not self._shutdown_event.is_set():
                    print("⚠️ Lost connection to MPV, retrying...")
                    await asyncio.sleep(1)
            except Exception as e:
                print(f"IPC Loop Error: {e}")
                await asyncio.sleep(1)

    async def _handle_event(self, event: dict):
        """Handle MPV events - Updated for queue auto-advance."""
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
                # MPV's internal playlist position changed
                pass
            elif name == "idle-active":
                if value is True:
                    self.state = PlaybackState.IDLE
            elif name == "eof-reached":
                if value is True:
                    # ⭐ Track ended - auto-advance to next
                    print(f"Track {self.current_track_index} ended")
                    await self.next_track()

        elif evt_name == "end-file":
            reason = event.get("reason")
            if reason == "error":
                self.state = PlaybackState.ERROR
            elif reason == "eof":
                # End of file reached, next_track will be called via eof-reached
                pass