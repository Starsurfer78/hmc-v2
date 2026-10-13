"""HMC media_player entity, driven by HMC's existing MQTT state/command topics."""

from __future__ import annotations

import json
import logging
from typing import Any

from homeassistant.components import media_source, mqtt
from homeassistant.components.media_player import (
    ATTR_MEDIA_ANNOUNCE,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
    async_process_play_media_url,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_DEVICE_ID, DOMAIN, availability_topic, command_topic, state_topic

_LOGGER = logging.getLogger(__name__)

# HMC PlaybackState -> HA MediaPlayerState. HA has no "stopped" state; a
# stopped/idle/errored HMC player is simply IDLE from HA's point of view.
_STATE_MAP = {
    "playing": MediaPlayerState.PLAYING,
    "paused": MediaPlayerState.PAUSED,
    "loading": MediaPlayerState.BUFFERING,
    "idle": MediaPlayerState.IDLE,
    "stopped": MediaPlayerState.IDLE,
    "error": MediaPlayerState.IDLE,
}

_SUPPORTED_FEATURES = (
    MediaPlayerEntityFeature.PLAY
    | MediaPlayerEntityFeature.PAUSE
    | MediaPlayerEntityFeature.STOP
    | MediaPlayerEntityFeature.NEXT_TRACK
    | MediaPlayerEntityFeature.PREVIOUS_TRACK
    | MediaPlayerEntityFeature.VOLUME_SET
    | MediaPlayerEntityFeature.SEEK
    | MediaPlayerEntityFeature.PLAY_MEDIA
    | MediaPlayerEntityFeature.MEDIA_ANNOUNCE
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([HmcMediaPlayer(entry)])


class HmcMediaPlayer(MediaPlayerEntity):
    _attr_supported_features = _SUPPORTED_FEATURES
    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry) -> None:
        self._device_id = entry.data[CONF_DEVICE_ID]
        self._attr_unique_id = self._device_id
        self._attr_name = entry.data["name"]
        self._attr_available = False
        self._attr_state = MediaPlayerState.IDLE
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=entry.data["name"],
            manufacturer="DIY",
            model="HMC",
        )

    async def async_added_to_hass(self) -> None:
        self._state_unsub = await mqtt.async_subscribe(
            self.hass, state_topic(self._device_id), self._on_state_message
        )
        self._availability_unsub = await mqtt.async_subscribe(
            self.hass, availability_topic(self._device_id), self._on_availability_message
        )

    async def async_will_remove_from_hass(self) -> None:
        self._state_unsub()
        self._availability_unsub()

    @callback
    def _on_availability_message(self, msg) -> None:
        self._attr_available = msg.payload == "online"
        self.async_write_ha_state()

    @callback
    def _on_state_message(self, msg) -> None:
        try:
            data = json.loads(msg.payload)
        except (TypeError, ValueError):
            _LOGGER.warning("Invalid HMC state payload: %s", msg.payload)
            return

        self._attr_state = _STATE_MAP.get(data.get("state"), MediaPlayerState.IDLE)
        self._attr_media_title = data.get("title") or None
        self._attr_media_duration = data.get("duration") or None
        self._attr_media_position = data.get("position") or None
        self._attr_media_image_url = data.get("media_image_url") or None
        self._attr_volume_level = data.get("volume_level")
        self.async_write_ha_state()

    async def _publish(self, payload: str) -> None:
        await mqtt.async_publish(self.hass, command_topic(self._device_id), payload)

    async def async_media_play(self) -> None:
        await self._publish("resume")

    async def async_media_pause(self) -> None:
        await self._publish("pause")

    async def async_media_stop(self) -> None:
        await self._publish("stop")

    async def async_media_next_track(self) -> None:
        await self._publish("next")

    async def async_media_previous_track(self) -> None:
        await self._publish("previous")

    async def async_set_volume_level(self, volume: float) -> None:
        await self._publish(f"volume:{round(volume * 100)}")

    async def async_media_seek(self, position: float) -> None:
        await self._publish(f"seek:{position}")

    async def async_play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        # tts.speak liefert eine media-source-ID (und announce=True), keine URL
        if media_source.is_media_source_id(media_id):
            play_item = await media_source.async_resolve_media(
                self.hass, media_id, self.entity_id
            )
            media_id = play_item.url
        # Relative HA-Pfade (z.B. /api/tts_proxy/...) in eine für HMC
        # erreichbare absolute URL umwandeln
        url = async_process_play_media_url(self.hass, media_id)

        # announce: HMC unterbricht kurz und setzt danach die vorherige
        # Wiedergabe fort; sonst ersetzt die URL die Warteschlange
        command = "announce" if kwargs.get(ATTR_MEDIA_ANNOUNCE) else "play_url"
        await self._publish(f"{command}:{url}")
