"""Constants for the HMC Media Player integration."""

DOMAIN = "hmc_media_player"

CONF_DEVICE_ID = "device_id"

PLATFORMS = ["media_player"]


def state_topic(device_id: str) -> str:
    return f"hmc/{device_id}/state"


def command_topic(device_id: str) -> str:
    return f"hmc/{device_id}/command"


def availability_topic(device_id: str) -> str:
    return f"hmc/{device_id}/availability"
