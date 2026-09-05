"""HMC Media Player integration.

Bridges a HMC (Home Media Console) instance into Home Assistant as a real
media_player entity, fed over the MQTT state/command protocol HMC already
publishes (hmc/{device_id}/state, hmc/{device_id}/command,
hmc/{device_id}/availability). Home Assistant's own MQTT integration has no
media_player discovery schema, so this integration exists to provide the
Home-Assistant-side entity instead of relying on (non-existent) MQTT
discovery for this domain.
"""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import PLATFORMS


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
