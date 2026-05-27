"""Constants for the Prana Integration."""
import logging
from enum import Enum

DOMAIN = "prana"
LOGGER = logging.getLogger(__package__)

DEFAULT_PASSWORD = "0000"

UUID_PRANA_SERVICE = "0000baba-0000-1000-8000-00805f9b34fb"
UUID_RWN_CHARACTERISTIC = "0000cccc-0000-1000-8000-00805f9b34fb"
UUID_PRANA_WRITE = UUID_RWN_CHARACTERISTIC
UUID_PRANA_READ = UUID_RWN_CHARACTERISTIC

# V2 Action Commands
PRANA_CMD_POWER_OFF = 0x01
PRANA_CMD_POWER_ON = 0x0A
PRANA_CMD_BRIGHTNESS = 0x02
PRANA_CMD_HEATING = 0x05
PRANA_CMD_FAN_LOCK = 0x09
PRANA_CMD_WINTER_MODE = 0x16
PRANA_CMD_AUTO_MODE = 0x18
PRANA_CMD_DISPLAY_LEFT = 0x19
PRANA_CMD_DISPLAY_RIGHT = 0x1A

PRANA_CMD_AUTH = 0x01
PRANA_CMD_GET_STATE = 0x01

PRANA_RESP_START_BYTE1 = 0xBE
PRANA_RESP_START_BYTE2 = 0xEF

class PranaMode(Enum):
    MANUAL = 0
    AUTO = 1
    AUTO_PLUS = 2

# Display Enums matching C++ memory
class PranaDisplayMode(Enum):
    FAN = 0
    TEMP_IN = 1
    TEMP_OUT = 2
    CO2 = 3
    VOC = 4
    HUMIDITY = 5
    AIR_QUALITY = 6
    PRESSURE = 7
    UNUSED = 8
    DATE = 9
    TIME = 10

DISPLAY_MODE_MAP = {
    PranaDisplayMode.FAN: "Fan State",
    PranaDisplayMode.TEMP_IN: "Temp Inside",
    PranaDisplayMode.TEMP_OUT: "Temp Outside",
    PranaDisplayMode.CO2: "CO2",
    PranaDisplayMode.VOC: "VOC",
    PranaDisplayMode.HUMIDITY: "Humidity",
    PranaDisplayMode.AIR_QUALITY: "Efficiency", 
    PranaDisplayMode.PRESSURE: "Pressure",
    PranaDisplayMode.DATE: "Date",
    PranaDisplayMode.TIME: "Time",
}
DISPLAY_MODE_LIST = list(DISPLAY_MODE_MAP.values())
DISPLAY_MODE_LIST.remove("Date")
DISPLAY_MODE_LIST.remove("Time")

CONF_PASSWORD = "password"
CONF_MODEL = "model"

MODEL_STANDARD = "Standard"
MODEL_PREMIUM = "Premium"
MODEL_PREMIUM_PLUS = "Premium Plus"
MODEL_CHOICES = [MODEL_STANDARD, MODEL_PREMIUM, MODEL_PREMIUM_PLUS]

UPDATE_INTERVAL_SECONDS = 60