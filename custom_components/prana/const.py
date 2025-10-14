"""Constants for the Prana HASS integration."""
from typing import Final

DOMAIN: Final = "prana"
PLATFORMS: Final = ["sensor", "switch", "fan", "number", "select"]

# BLE UUIDs
SERVICE_UUID: Final = "0000baba-0000-1000-8000-00805f9b34fb"
CHARACTERISTIC_UUID_COMMAND: Final = "0000beef-0000-1000-8000-00805f9b34fb" # Write
CHARACTERISTIC_UUID_STATUS: Final = "0000c0de-0000-1000-8000-00805f9b34fb" # Notify

# Dispatcher signal for updates
UPDATE_SIGNAL: Final = f"{DOMAIN}_update"

# Configuration constants
CONF_SCAN_INTERVAL: Final = "scan_interval"
DEFAULT_SCAN_INTERVAL: Final = 60  # seconds

# Prana Commands (derived from ESPHome component)
# Simple "button" commands are prefixed with 0x04 then the command byte
CMD_PREFIX_BUTTON: Final = 0x04

CMD_POWER: Final = 0x01
CMD_BRIGHTNESS: Final = 0x02 # Also used as a button press to cycle/decrement
CMD_AUTO_MODE: Final = 0x03
CMD_NIGHT_MODE: Final = 0x04 # Not directly used, Auto/Manual seems preferred
CMD_HEATING: Final = 0x05
CMD_FAN_LOCK: Final = 0x06 # Fan speed lock
# CMD_TIMER ... up to 0x0A
CMD_FANS_SPEED_UP: Final = 0x0B
CMD_FANS_SPEED_DOWN: Final = 0x0C
CMD_FAN_IN_OFF: Final = 0x0D
CMD_FAN_IN_ON: Final = 0x0E # Or simply setting speed? ESPHome sets speed.
CMD_FAN_OUT_OFF: Final = 0x10
CMD_FAN_OUT_ON: Final = 0x11 # Or simply setting speed?
CMD_WINTER_MODE: Final = 0x16
CMD_DEFROST_MODE: Final = 0x17 # (Winter mode extended)

# Status request command
CMD_GET_STATUS_PAYLOAD: Final = b"\x05\x01\x00\x00\x00\x00\x5A"

# Byte offsets in the status packet (128 bytes total)
# Based on prana_ble.cpp from voed/esphome_prana_ble
# struct PranaStatus {
#   uint8_t head[9]; // Includes \xBE\xEF\x05\x01\x00\x00\x00\x00\x5A
#   uint8_t inlet_speed_current; // byte 9 (0-indexed)
#   uint8_t unknown10;
#   uint8_t outlet_speed_current; // byte 11
#   uint8_t unknown12;
#   uint8_t display_brightness; // byte 13
#   uint8_t unknown14[5];
#   uint8_t display_mode; // byte 19 (0: Fan, 1: Temp In, 2: Temp Out, 3: Humidity, 4: CO2, 5: VOC, 6: Pressure)
#   uint8_t unknown20;
#   uint8_t fan_mode; // byte 21 (0: Ventilation, 1: Recuperation, 2: Auto+, 3: Auto++)
#   uint8_t unknown22[3];
#   uint8_t power_state; // byte 25 (0: OFF, 1: ON)
#   uint8_t unknown26;
#   uint8_t heating_state; // byte 27 (0: OFF, 1: ON)
#   uint8_t unknown28[3];
#   uint8_t winter_mode_state; // byte 31 (0: OFF, 1: ON)
#   uint8_t unknown32[9];
#   uint8_t temp_inlet_before;   // signed byte 41 / 2.0
#   uint8_t unknown42;
#   uint8_t temp_outlet_before;  // signed byte 43 / 2.0
#   uint8_t unknown44;
#   uint8_t temp_inlet_after;    // signed byte 45 / 2.0
#   uint8_t unknown46;
#   uint8_t temp_outlet_after;   // signed byte 47 / 2.0
#   uint8_t unknown48;
#   uint8_t humidity; // byte 49 (Relative humidity %)
#   uint8_t unknown50[3];
#   uint16_t voc_ppb; // bytes 53,54 (little-endian)
#   uint8_t unknown55[3];
#   uint16_t co2_ppm; // bytes 58,59 (little-endian)
#   uint8_t unknown60;
#   uint8_t pressure_mmhg; // byte 61
#   // ... rest are unknown or not used by ESPHome component
# };

STATUS_OFFSET_INLET_SPEED = 9
STATUS_OFFSET_OUTLET_SPEED = 11
STATUS_OFFSET_BRIGHTNESS = 13
STATUS_OFFSET_DISPLAY_MODE = 19
STATUS_OFFSET_FAN_MODE = 21
STATUS_OFFSET_POWER_STATE = 25
STATUS_OFFSET_HEATING_STATE = 27
STATUS_OFFSET_WINTER_MODE_STATE = 31
STATUS_OFFSET_FAN_LOCK_STATE = 33 # ESPHome has this, need to verify exact byte. Assuming based on command list.
                                 # voed/esphome_prana_ble prana_ble.h line 206 -> status->raw[33] & 0x01
STATUS_OFFSET_TEMP_INLET_BEFORE = 41
STATUS_OFFSET_TEMP_OUTLET_BEFORE = 43
STATUS_OFFSET_TEMP_INLET_AFTER = 45
STATUS_OFFSET_TEMP_OUTLET_AFTER = 47
STATUS_OFFSET_HUMIDITY = 49
STATUS_OFFSET_VOC_PPB_L = 53
STATUS_OFFSET_VOC_PPB_H = 54
STATUS_OFFSET_CO2_PPM_L = 58
STATUS_OFFSET_CO2_PPM_H = 59
STATUS_OFFSET_PRESSURE_MMHG = 61

# Fan speed counts
FAN_SPEED_COUNT = 10

# Display Mode Options for Select Entity
DISPLAY_MODE_OPTIONS = ["Fan Speed", "Temp In", "Temp Out", "Humidity", "CO2", "VOC", "Pressure"]
# Fan Mode Options for Select Entity
FAN_MODE_OPTIONS = ["Ventilation", "Recuperation", "Auto+", "Auto++"]

# Model identifier for unique ID
MODEL_NAME = "Prana Recuperator"