"""
HMC MQTT State/Command Client
==============================
Veröffentlicht den Player-State und nimmt Kommandos entgegen. Die eigentliche
Home-Assistant-Entität wird durch die Custom Component `hmc_media_player`
bereitgestellt (siehe custom_components/hmc_media_player/) — HAs native
MQTT-Integration kennt kein `media_player`-Discovery-Schema, ein Publish auf
`homeassistant/media_player/.../config` wird von HA schlicht ignoriert.

Topics die genutzt werden:
  State:        hmc/{device_id}/state          (retained)
  Command:      hmc/{device_id}/command        (subscribed)
  Availability: hmc/{device_id}/availability   (retained, LWT)

Jede HMC-Instanz bekommt eine eindeutige device_id aus MQTT_DEVICE_ID (.env).
Damit können mehrere Player im selben Netz koexistieren.
"""

import asyncio
import json
import logging
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
        self.state_topic      = f"hmc/{self.device_id}/state"
        self.command_topic    = f"hmc/{self.device_id}/command"
        self.availability_topic = f"hmc/{self.device_id}/availability"

        # Callback: wird von main.py gesetzt
        self.on_command: Optional[Callable[[str], None]] = None

        self._client: Optional[aiomqtt.Client] = None
        self._task: Optional[asyncio.Task] = None
        self._connected = asyncio.Event()
        self._shutdown = asyncio.Event()

    @property
    def is_connected(self) -> bool:
        return self._connected.is_set()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def start(self):
        """Verbindet zum Broker und startet den Listener-Task."""
        self._shutdown.clear()
        self._task = asyncio.create_task(self._run())
        # Kurz warten bis die Verbindung zum Broker steht
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
                "state":        state.get("state", "idle"),
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
            # Republish "online" bei jedem State-Push: ein Last-Will "offline"
            # einer vorherigen, unsauber beendeten Verbindung kann erst mit
            # Verzoegerung (Broker-Keepalive-Timeout) eintreffen und dabei ein
            # bereits gesetztes "online" ueberschreiben. So korrigiert sich
            # das innerhalb von maximal einem Push-Intervall von selbst.
            await self._client.publish(
                self.availability_topic, "online", retain=True
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
# Hilfsfunktionen
# ------------------------------------------------------------------

async def _safe_call(fn: Callable, *args):
    """Führt einen Callback aus und fängt Exceptions ab."""
    try:
        result = fn(*args)
        if asyncio.iscoroutine(result):
            await result
    except Exception as e:
        logger.error(f"MQTT command callback Fehler: {e}")
