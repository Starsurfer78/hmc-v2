"""
HMC MQTT Discovery Client
=========================
Registriert den HMC-Player automatisch in Home Assistant via MQTT Discovery.

Topics die genutzt werden:
  Discovery:   homeassistant/media_player/{device_id}/config   (retained)
  State:       hmc/{device_id}/state                            (retained)
  Command:     hmc/{device_id}/command                          (subscribed)

Jede HMC-Instanz bekommt eine eindeutige device_id aus MQTT_DEVICE_ID (.env).
Damit können mehrere Player im selben Netz koexistieren.
"""

import asyncio
import json
import logging
import socket
from typing import Optional, Callable

import aiomqtt

from .config import settings

logger = logging.getLogger(__name__)


class MqttClient:
    def __init__(self):
        self.device_id: str = settings.MQTT_DEVICE_ID
        self.device_name: str = settings.MQTT_DEVICE_NAME
        self.broker: str = settings.MQTT_BROKER
        self.port: int = settings.MQTT_PORT
        self.username: Optional[str] = settings.MQTT_USER or None
        self.password: Optional[str] = settings.MQTT_PASSWORD or None

        # Topics
        self.discovery_topic = f"homeassistant/media_player/{self.device_id}/config"
        self.state_topic      = f"hmc/{self.device_id}/state"
        self.command_topic    = f"hmc/{self.device_id}/command"
        self.availability_topic = f"hmc/{self.device_id}/availability"

        # Callback: wird von main.py gesetzt
        self.on_command: Optional[Callable[[str], None]] = None

        self._client: Optional[aiomqtt.Client] = None
        self._task: Optional[asyncio.Task] = None
        self._connected = asyncio.Event()
        self._shutdown = asyncio.Event()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def start(self):
        """Verbindet zum Broker und startet den Listener-Task."""
        self._shutdown.clear()
        self._task = asyncio.create_task(self._run())
        # Kurz warten bis Discovery veröffentlicht wurde
        try:
            await asyncio.wait_for(self._connected.wait(), timeout=10)
        except asyncio.TimeoutError:
            logger.warning("MQTT: Verbindungsaufbau dauert länger als erwartet")

    async def stop(self):
        """Trennt sauber vom Broker (offline-Nachricht + Shutdown)."""
        self._shutdown.set()
        if self._client:
            try:
                await self._client.publish(
                    self.availability_topic, "offline", retain=True
                )
            except Exception:
                pass
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def publish_state(self, state: dict):
        """Veröffentlicht den aktuellen Player-State als JSON."""
        if not self._client:
            return
        try:
            track = state.get("current_track") or {}
            payload = {
                "state":        _ha_state(state.get("state", "idle")),
                "title":        track.get("name", ""),
                "artist":       "",          # Jellyfin liefert keinen Artist auf Track-Ebene
                "album":        "",
                "duration":     int(state.get("duration", 0)),
                "position":     int(state.get("position", 0)),
                "volume_level": round(state.get("volume", 60) / 100, 2),
                "media_image_url": track.get("image", ""),
                "queue_size":   state.get("total_tracks", 0),
            }
            await self._client.publish(
                self.state_topic,
                json.dumps(payload),
                retain=True,
            )
        except Exception as e:
            logger.warning(f"MQTT publish_state Fehler: {e}")

    # ------------------------------------------------------------------
    # Interner Loop
    # ------------------------------------------------------------------

    async def _run(self):
        """Verbindungsloop mit automatischem Reconnect."""
        while not self._shutdown.is_set():
            try:
                kwargs = dict(
                    hostname=self.broker,
                    port=self.port,
                    will=aiomqtt.Will(
                        topic=self.availability_topic,
                        payload="offline",
                        retain=True,
                    ),
                )
                if self.username:
                    kwargs["username"] = self.username
                if self.password:
                    kwargs["password"] = self.password

                async with aiomqtt.Client(**kwargs) as client:
                    self._client = client

                    # Discovery + Availability publizieren
                    await client.publish(
                        self.discovery_topic,
                        json.dumps(self._discovery_payload()),
                        retain=True,
                    )
                    await client.publish(
                        self.availability_topic, "online", retain=True
                    )

                    # Command-Topic abonnieren
                    await client.subscribe(self.command_topic)
                    logger.info(
                        f"MQTT: Verbunden mit {self.broker}, "
                        f"Device-ID: {self.device_id}"
                    )
                    self._connected.set()

                    # Nachrichten empfangen
                    async for message in client.messages:
                        if self._shutdown.is_set():
                            break
                        payload = message.payload.decode("utf-8", errors="replace")
                        logger.debug(f"MQTT command: {payload}")
                        if self.on_command:
                            asyncio.create_task(
                                _safe_call(self.on_command, payload)
                            )

            except aiomqtt.MqttError as e:
                logger.warning(f"MQTT Verbindungsfehler: {e} – Reconnect in 5 s")
                self._connected.clear()
                self._client = None
                await asyncio.sleep(5)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"MQTT unerwarteter Fehler: {e}")
                await asyncio.sleep(5)

    # ------------------------------------------------------------------
    # Discovery Payload
    # ------------------------------------------------------------------

    def _discovery_payload(self) -> dict:
        """
        Erzeugt den HA MQTT Discovery Payload für einen media_player.
        Dokumentation: https://www.home-assistant.io/integrations/media_player.mqtt/
        """
        return {
            # Eindeutige Identität
            "unique_id": self.device_id,
            "name":      self.device_name,

            # Topics
            "state_topic":        self.state_topic,
            "command_topic":      self.command_topic,
            "availability_topic": self.availability_topic,

            # State-Mapping: HMC-Werte → HA-Werte
            "state_playing":  "playing",
            "state_paused":   "paused",
            "state_stopped":  "stopped",
            "state_idle":     "idle",

            # Welche Felder aus dem JSON-State gelesen werden
            "value_template":         "{{ value_json.state }}",
            "volume_template":        "{{ value_json.volume_level }}",
            "media_title_template":   "{{ value_json.title }}",
            "media_duration_template":"{{ value_json.duration }}",
            "media_position_template":"{{ value_json.position }}",
            "media_image_url_template":"{{ value_json.media_image_url }}",

            # Unterstützte Features in HA
            "supported_features": [
                "pause", "stop",
                "next_track", "previous_track",
                "volume_set",
            ],

            # Kommandos die HA sendet → werden in on_command verarbeitet
            "payload_play":           "play",
            "payload_pause":          "pause",
            "payload_stop":           "stop",
            "payload_media_play_pause": "play_pause",

            # Gerät-Gruppierung in HA (alle HMC-Instanzen unter einem Gerät)
            "device": {
                "identifiers":    [self.device_id],
                "name":           self.device_name,
                "model":          "HMC v2.1",
                "manufacturer":   "DIY",
                "sw_version":     "2.1.0",
            },

            # Availability
            "payload_available":     "online",
            "payload_not_available": "offline",
        }


# ------------------------------------------------------------------
# Hilfsfunktionen
# ------------------------------------------------------------------

def _ha_state(hmc_state: str) -> str:
    """Übersetzt HMC PlaybackState in HA media_player state."""
    mapping = {
        "playing":  "playing",
        "paused":   "paused",
        "stopped":  "stopped",
        "idle":     "idle",
        "loading":  "idle",
        "error":    "idle",
    }
    return mapping.get(hmc_state, "idle")


async def _safe_call(fn: Callable, *args):
    """Führt einen Callback aus und fängt Exceptions ab."""
    try:
        result = fn(*args)
        if asyncio.iscoroutine(result):
            await result
    except Exception as e:
        logger.error(f"MQTT command callback Fehler: {e}")
