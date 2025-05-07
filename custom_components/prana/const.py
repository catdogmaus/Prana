# custom_components/prana/const.py

"""Constants for the Prana Integration."""
import logging
from enum import Enum
# Consider adding Final if using Python 3.8+ for better type hinting
# from typing import Final

DOMAIN = "prana"
LOGGER = logging.getLogger(__package__)

# Default password
DEFAULT_PASSWORD = "0000"

# --- Define UUIDs based on user feedback (0xBABA service, 0xCCCC characteristic) ---

# Used for expanding 16-bit and 32-bit UUIDs (Helper, not strictly needed if full UUIDs known)
# BASE_UUID: Final = "0000{}-0000-1000-8000-00805f9b34fb"

# Service UUID reported by the device
UUID_PRANA_SERVICE = "0000baba-0000-1000-8000-00805f9b34fb" # Based on 0xBABA

# Characteristic UUID reported by the device (used for Read, Write, Notify)
UUID_RWN_CHARACTERISTIC = "0000cccc-0000-1000-8000-00805f9b34fb" # Based on 0xCCCC

# Point both Read and Write constants to the same characteristic UUID
UUID_PRANA_WRITE = UUID_RWN_CHARACTERISTIC
UUID_PRANA_READ = UUID_RWN_CHARACTERISTIC # Also used for notifications

# --- End of updated UUIDs ---


# Commands (from esphome_prana_ble/components/prana_ble/prana_ble_hub.h - assuming these are still valid)
PRANA_CMD_AUTH = 0x01
PRANA_CMD_SET_SPEED = 0x02
PRANA_CMD_SET_MODE = 0x03
PRANA_CMD_SET_POWER = 0x04
PRANA_CMD_GET_STATE = 0x05
PRANA_CMD_SET_TIMER = 0x06
PRANA_CMD_RESET_FILTER = 0x07
PRANA_CMD_SET_BRIGHTNESS = 0x08

# Response structure start bytes (assuming these are still valid)
PRANA_RESP_START_BYTE1 = 0x55
PRANA_RESP_START_BYTE2 = 0xAA

# Maximum command length
PRANA_CMD_MAX_LEN = 20

# Prana Modes (derived from prana_ble_hub.h)
class PranaMode(Enum):
    """Prana operating modes."""
    AUTO = 0
    WINTER = 1
    SUMMER = 2
    VENTILATION = 3
    SUPPLY = 4
    EXHAUST = 5

# Map modes to user-friendly names
MODE_MAP = {
    PranaMode.AUTO: "Auto",
    PranaMode.WINTER: "Winter",
    PranaMode.SUMMER: "Summer",
    PranaMode.VENTILATION: "Ventilation",
    PranaMode.SUPPLY: "Supply Only",
    PranaMode.EXHAUST: "Exhaust Only",
}
MODE_LIST = list(MODE_MAP.values())

# Configuration keys
CONF_PASSWORD = "password"

# DataUpdateCoordinator update interval (seconds)
UPDATE_INTERVAL_SECONDS = 60

# Max Brightness
MAX_BRIGHTNESS = 100