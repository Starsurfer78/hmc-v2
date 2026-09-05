import asyncio
import json
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
    def __init__(self, audio_device: str = "hw:1,0", max_volume: int = 60):
        self.audio_device = audio_device
        self.max_volume = max_volume
        self.socket_path = "/tmp/hmc-mpv.sock"

        self.process: Optional[subprocess.Popen] = None
        self._shutdown_event = asyncio.Event()
        self._ipc_task: Optional[asyncio.Task] = None
        self._monitor_task: Optional[asyncio.Task] = None

        self.state = PlaybackState.IDLE

        self.playback_queue: List[dict] = []
        self.current_track_index = 0

        self.duration = 0.0
        self.position = 0.0

        self.on_state_change: Optional[Callable[[PlaybackState], None]] = None
        self.on_track_change: Optional[Callable[[dict], None]] = None

    async def start(self):
        if self.process:
            return

        self._shutdown_event.clear()

        if self.audio_device == "mock":
            self.state = PlaybackState.IDLE
            return

        cmd = [
            "mpv",
            f"--audio-device=alsa/{self.audio_device}",
            f"--volume={self.max_volume}",
            "--no-video",
            "--input-ipc-server=" + self.socket_path,
            "--idle=yes",
            "--keep-open=no",
        ]

        self.process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        for _ in range(50):
            if Path(self.socket_path).exists():
                await asyncio.sleep(0.5)
                break
            await asyncio.sleep(0.1)
        else:
            self.state = PlaybackState.ERROR
            return

        self._ipc_task = asyncio.create_task(self._ipc_loop())
        self._monitor_task = asyncio.create_task(self._monitor_process())
        self.state = PlaybackState.IDLE

    async def stop(self):
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

    def clear_queue(self):
        self.playback_queue = []
        self.current_track_index = 0
        self.duration = 0.0
        self.position = 0.0

    def get_queue(self) -> List[dict]:
        return self.playback_queue.copy()

    def get_upcoming_tracks(self) -> List[dict]:
        if self.current_track_index < len(self.playback_queue) - 1:
            return self.playback_queue[self.current_track_index + 1 :]
        return []

    def get_current_track(self) -> Optional[dict]:
        if 0 <= self.current_track_index < len(self.playback_queue):
            return self.playback_queue[self.current_track_index]
        return None

    async def play_now(self, track: dict):
        self.clear_queue()
        self.playback_queue = [track]
        self.current_track_index = 0
        await self._play_current_track()
        return {"status": "playing", "action": "play_now", "track": track, "queue_length": 1}

    async def play_next(self, track: dict):
        if not self.playback_queue:
            return await self.play_now(track)
        insert_position = self.current_track_index + 1
        self.playback_queue.insert(insert_position, track)
        return {
            "status": "queued",
            "action": "play_next",
            "track": track,
            "position": insert_position,
            "queue_length": len(self.playback_queue),
        }

    async def add_to_queue(self, track: dict):
        if not self.playback_queue:
            return await self.play_now(track)
        self.playback_queue.append(track)
        return {
            "status": "queued",
            "action": "add_to_queue",
            "track": track,
            "position": len(self.playback_queue) - 1,
            "queue_length": len(self.playback_queue),
        }

    async def remove_from_queue(self, index: int) -> bool:
        if index < 0 or index >= len(self.playback_queue):
            return False

        if index == self.current_track_index:
            if index == len(self.playback_queue) - 1:
                await self.stop_playback()
                return True

            await self.next_track()
            self.playback_queue.pop(index)
            if self.current_track_index > 0:
                self.current_track_index -= 1
        else:
            self.playback_queue.pop(index)
            if index < self.current_track_index:
                self.current_track_index -= 1

        return True

    async def jump_to_track(self, index: int):
        if index < 0 or index >= len(self.playback_queue):
            raise ValueError(f"Index {index} out of range")
        self.current_track_index = index
        await self._play_current_track()
        return {"status": "playing", "action": "jump_to_track", "track": self.get_current_track(), "index": index}

    async def play_album(self, tracks: List[dict], start_index: int = 0):
        if not tracks:
            raise ValueError("No tracks provided")

        if (
            self.state == PlaybackState.PLAYING
            and self.playback_queue
            and len(tracks) == len(self.playback_queue)
            and tracks[0].get("url") == self.playback_queue[0].get("url")
            and self.current_track_index == start_index
        ):
            return {"status": "playing", "tracks": len(tracks), "current": tracks[start_index]}

        if not self.process and self.audio_device != "mock":
            await self.start()

        self.playback_queue = tracks
        self.current_track_index = start_index
        self.state = PlaybackState.LOADING

        if self.audio_device == "mock":
            self.state = PlaybackState.PLAYING
            return {"status": "playing", "tracks": len(tracks), "current": tracks[start_index]}

        await self._play_current_track()
        return {"status": "playing", "tracks": len(tracks), "current": tracks[start_index]}

    async def _play_current_track(self):
        current_track = self.get_current_track()
        if not current_track:
            self.state = PlaybackState.IDLE
            return

        if self.audio_device == "mock":
            self.state = PlaybackState.PLAYING
            return

        url = current_track.get("url") or ""
        await self._send_command(["loadfile", url, "replace"])
        await self._send_command(["set_property", "pause", False])
        self.state = PlaybackState.PLAYING

        if self.on_track_change:
            self.on_track_change(current_track)

    async def next_track(self):
        if self.audio_device == "mock":
            self.current_track_index = min(len(self.playback_queue) - 1, self.current_track_index + 1)
            return

        if self.current_track_index < len(self.playback_queue) - 1:
            self.current_track_index += 1
            await self._play_current_track()
        else:
            await self.stop_playback()

    async def previous_track(self):
        if self.audio_device == "mock":
            self.current_track_index = max(0, self.current_track_index - 1)
            return

        if self.position > 3.0:
            await self.seek(0)
        else:
            if self.current_track_index > 0:
                self.current_track_index -= 1
                await self._play_current_track()
            else:
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
        if self.audio_device == "mock":
            self.state = PlaybackState.STOPPED
            self.clear_queue()
            return
        await self._send_command(["stop"])
        self.state = PlaybackState.STOPPED
        self.clear_queue()

    async def seek(self, position: float):
        if self.audio_device == "mock":
            self.position = position
            return
        await self._send_command(["seek", str(position), "absolute"])

    async def set_volume(self, volume: int):
        if self.audio_device == "mock":
            return
        await self._send_command(["set_property", "volume", volume])

    async def get_volume(self) -> int:
        if self.audio_device == "mock":
            return self.max_volume
        result = await self._send_command(["get_property", "volume"])
        return int(result.get("data", self.max_volume)) if result else self.max_volume

    async def get_state(self) -> dict:
        return {
            "state": self.state,
            "position": self.position,
            "duration": self.duration,
            "current_track_index": self.current_track_index,
            "current_track": self.get_current_track(),
            "total_tracks": len(self.playback_queue),
            "queue": self.get_queue(),
            "upcoming_tracks": self.get_upcoming_tracks(),
        }

    async def _send_command(self, command: List[Any]) -> Optional[Dict]:
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
        except Exception:
            return None
        return None

    async def _monitor_process(self):
        while not self._shutdown_event.is_set():
            if self.process and self.process.poll() is not None:
                self.state = PlaybackState.ERROR
                self.process = None
                if self.playback_queue:
                    await asyncio.sleep(2)
                    try:
                        await self._play_current_track()
                    except Exception:
                        pass
            await asyncio.sleep(1)

    async def _ipc_loop(self):
        for _ in range(30):
            if Path(self.socket_path).exists():
                break
            await asyncio.sleep(0.1)

        while not self._shutdown_event.is_set():
            try:
                reader, writer = await asyncio.open_unix_connection(self.socket_path)

                observers = [
                    '{"command": ["observe_property", 1, "pause"]}\n',
                    '{"command": ["observe_property", 2, "time-pos"]}\n',
                    '{"command": ["observe_property", 3, "duration"]}\n',
                    '{"command": ["observe_property", 4, "idle-active"]}\n',
                    '{"command": ["observe_property", 5, "eof-reached"]}\n',
                ]
                for obs in observers:
                    writer.write(obs.encode())
                await writer.drain()

                while not self._shutdown_event.is_set():
                    line = await reader.readline()
                    if not line:
                        break
                    try:
                        data = json.loads(line)
                        if data.get("event") == "property-change":
                            await self._handle_property_change(data)
                    except json.JSONDecodeError:
                        pass

                writer.close()
                await writer.wait_closed()

            except (ConnectionRefusedError, FileNotFoundError):
                if not self._shutdown_event.is_set():
                    await asyncio.sleep(1)
            except Exception:
                await asyncio.sleep(1)

    async def _handle_property_change(self, event: dict):
        name = event.get("name")
        value = event.get("data")

        if name == "pause":
            self.state = PlaybackState.PAUSED if value else PlaybackState.PLAYING
        elif name == "time-pos" and value is not None:
            try:
                self.position = float(value)
            except (TypeError, ValueError):
                pass
        elif name == "duration" and value is not None:
            try:
                self.duration = float(value)
            except (TypeError, ValueError):
                pass
        elif name == "idle-active":
            if value is True:
                self.state = PlaybackState.IDLE
        elif name == "eof-reached":
            if value is True:
                await self.next_track()
