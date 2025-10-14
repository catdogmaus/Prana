"""API for Prana BLE integration."""
import asyncio
import logging
from typing import Any, Callable, Dict, Optional

from bleak import BleakClient, BleakError
from bleak.backends.device import BLEDevice
from bleak.backends.characteristic import BleakGATTCharacteristic

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    SERVICE_UUID,
    CMD_AUTO_MODE,
    CMD_BRIGHTNESS,
    CMD_HEATING,
    CMD_NIGHT_MODE,
    CMD_POWER,
    CMD_PREFIX_BUTTON,
    CMD_WINTER_MODE,
    CMD_FANS_SPEED_UP,
    CMD_FANS_SPEED_DOWN,
    CMD_FAN_IN_ON,
    CMD_FAN_IN_OFF,
    CMD_FAN_OUT_ON,
    CMD_FAN_OUT_OFF,
    CMD_FAN_LOCK,
    UPDATE_SIGNAL,
)

_LOGGER = logging.getLogger(__name__)

CHARACTERISTIC_UUID_CTL: str = "0000cccc-0000-1000-8000-00805f9b34fb"
AUTH_CMD_1: bytes = bytes.fromhex("beef0c013213020d0a19")
POLL_CMD: bytes = bytes.fromhex("beef0502000000005a")
PACKET_HEADER = b"\xBE\xEF"


class PranaApi:
    """API for interacting with the Prana device."""

    def __init__(self, hass: HomeAssistant, ble_device: BLEDevice, name: str) -> None:
        self.hass = hass
        self.ble_device = ble_device
        self.address = ble_device.address
        self.name = name
        self._client: BleakClient | None = None
        self._is_connected: bool = False
        self._parsed_status: Dict[str, Any] = {}
        self._write_lock = asyncio.Lock()
        self._control_char: BleakGATTCharacteristic | None = None
        self._first_data_event = asyncio.Event()
        _LOGGER.info("PranaApi initialized for %s (%s)", self.name, self.address)

    @callback
    def handle_disconnect(self, client: BleakClient) -> None:
        if not self._is_connected: return
        _LOGGER.warning("%s: Disconnected from device.", self.name)
        self._is_connected = False
        self._client = None
        self._control_char = None
        self._first_data_event.clear()
        instance_specific_signal = f"{UPDATE_SIGNAL}_{self.name}"
        async_dispatcher_send(self.hass, instance_specific_signal, None)

    @callback
    def _notification_callback(self, characteristic: BleakGATTCharacteristic, data: bytearray) -> None:
        _LOGGER.debug("%s: Received notification: %s", self.name, data.hex())
        if data.startswith(PACKET_HEADER + b'\x05\x02'):
            self._parsed_status = self._parse_status_data(bytes(data))
            if self._parsed_status:
                self._first_data_event.set()
                instance_specific_signal = f"{UPDATE_SIGNAL}_{self.name}"
                async_dispatcher_send(self.hass, instance_specific_signal, self._parsed_status)
        else:
            _LOGGER.debug("%s: Received unknown notification: %s", self.name, data.hex())

    async def update_after_connect(self, client: BleakClient) -> dict:
        self._client = client
        self._is_connected = True
        self._first_data_event.clear()
        try:
            _LOGGER.debug("%s: Starting service discovery...", self.name)
            svcs = self._client.services
            if not svcs or not svcs.services: raise BleakError("Failed to discover services")
            
            prana_service = svcs.get_service(SERVICE_UUID)
            if not prana_service: raise BleakError(f"Prana service {SERVICE_UUID} not found.")

            self._control_char = prana_service.get_characteristic(CHARACTERISTIC_UUID_CTL)
            if not self._control_char: raise BleakError(f"Prana control characteristic {CHARACTERISTIC_UUID_CTL} not found.")

            _LOGGER.info("%s: Found Prana control characteristic.", self.name)

            await self._client.start_notify(self._control_char, self._notification_callback)
            _LOGGER.info("%s: Subscribed to notifications.", self.name)

            _LOGGER.info("%s: Performing authorization handshake...", self.name)
            await self._async_send_command_payload(AUTH_CMD_1)
            await asyncio.sleep(0.2)
            await self._async_send_command_payload(POLL_CMD)
            _LOGGER.info("%s: Handshake complete. Waiting for initial status notification...", self.name)

            await asyncio.wait_for(self._first_data_event.wait(), timeout=15)
            
            _LOGGER.info("%s: Initial status received successfully.", self.name)
            return self._parsed_status
            
        except asyncio.TimeoutError:
            _LOGGER.error("%s: Timed out waiting for data notification after handshake.", self.name)
            await self.disconnect()
            raise BleakError("Did not receive data after handshake")
        except Exception:
            await self.disconnect()
            raise

    async def async_get_status(self) -> dict:
        if not self.is_connected(): raise BleakError("Not connected for polling")
        self._parsed_status.clear()
        self._first_data_event.clear()
        await self._async_send_command_payload(POLL_CMD)
        await asyncio.wait_for(self._first_data_event.wait(), timeout=10)
        return self._parsed_status

    async def _async_send_command_payload(self, payload: bytes) -> None:
        if not self.is_connected() or not self._client or not self._control_char:
             raise BleakError("Cannot send command, not connected.")
        async with self._write_lock:
            _LOGGER.debug("%s: Sending command: %s", self.name, payload.hex())
            await self._client.write_gatt_char(self._control_char, payload, response=True)

    def is_connected(self) -> bool:
        return self._is_connected and self._client is not None and self._client.is_connected

    async def disconnect(self) -> None:
        _LOGGER.info("%s: Disconnecting...", self.name)
        client = self._client
        self._is_connected = False
        self._client = None
        self._control_char = None
        if client and client.is_connected:
            await client.disconnect()

    def _parse_status_data(self, raw: bytes) -> dict:
        """Parse the raw status data based on decoder script results."""
        def s16(data: bytes) -> int:
            return int.from_bytes(data, 'little', signed=True)
        try:
            data = {
                "power": bool(raw[9] & 0x01),
                "heating": bool(raw[11] & 0x01),
                "winter_mode": bool(raw[15] & 0x01),
                "fan_lock": bool(raw[17] & 0x01),
                
                "inlet_speed": raw[41],
                "outlet_speed": raw[43],
                "current_speed": raw[41],
                
                "brightness": raw[29],
                "display_mode": raw[31],
                "fan_mode": raw[33],
                
                "humidity": raw[52],
                
                "temp_inlet_before": None,  # T1 - Unknown offset
                "temp_outlet_before": None, # T2 - Unknown offset
                "temp_inlet_after": s16(raw[55:57]) / 10.0,   # T3 - Strong match from decoder
                "temp_outlet_after": s16(raw[8:10]) / 10.0,    # T4 - Weak match from decoder
                
                "co2": int.from_bytes(raw[19:21], 'little'), # Strong match from decoder
                "voc": int.from_bytes(raw[1:3], 'little'), # Strong match from decoder
                
                "pressure": None, # Unknown offset
            }
            _LOGGER.info("Parsed data: %s", data)
            return data
        except (IndexError, Exception) as e:
            _LOGGER.error("%s: Error parsing status data: %s. Data len: %d. Data: %s", self.name, e, len(raw), raw.hex())
            return {}

    async def _async_send_button_command(self, command_byte: int, value_byte: Optional[int] = None) -> None:
        payload_core_list = [CMD_PREFIX_BUTTON, command_byte]
        if value_byte is not None: payload_core_list.append(value_byte)
        payload = PACKET_HEADER + bytes(payload_core_list)
        await self._async_send_command_payload(payload)

    async def async_set_power(self, state: bool) -> None: await self._async_send_button_command(CMD_POWER)
    async def async_set_heating(self, state: bool) -> None: await self._async_send_button_command(CMD_HEATING)
    async def async_set_winter_mode(self, state: bool) -> None: await self._async_send_button_command(CMD_WINTER_MODE)
    async def async_set_fan_lock(self, state: bool) -> None: await self._async_send_button_command(CMD_FAN_LOCK)
    
    async def async_set_brightness(self, brightness: int) -> None:
        target_brightness = max(0, min(10, int(brightness)))
        current_brightness = self._parsed_status.get("brightness", 0)
        if current_brightness == target_brightness: return
        num_presses = (current_brightness - target_brightness) if current_brightness > target_brightness else (10 - current_brightness + target_brightness)
        num_presses %= 10
        if num_presses == 0 and current_brightness != target_brightness: num_presses = 10
        for _ in range(num_presses):
            await self._async_send_button_command(CMD_BRIGHTNESS)
            await asyncio.sleep(0.25)
            
    async def async_set_fan_speed(self, speed: int) -> None:
        target_speed = max(0, min(10, int(speed)))
        current_speed = self._parsed_status.get("current_speed", 0)
        if current_speed == target_speed: return
        if target_speed == 0:
            await self.async_turn_fan_on_off(False); return
        if not self._parsed_status.get("power", False):
            await self.async_set_power(True); await asyncio.sleep(0.5)
        command = CMD_FANS_SPEED_UP if target_speed > current_speed else CMD_FANS_SPEED_DOWN
        for _ in range(abs(target_speed - current_speed)):
            await self._async_send_button_command(command)
            await asyncio.sleep(0.25)
            
    async def async_turn_fan_on_off(self, turn_on: bool) -> None:
        power = self._parsed_status.get("power", False)
        speed = self._parsed_status.get("current_speed", 0)
        is_on = power and speed > 0
        if turn_on == is_on: return
        if turn_on:
            if not power: await self.async_set_power(True); await asyncio.sleep(0.5)
            await self._async_send_button_command(CMD_FAN_IN_ON); await asyncio.sleep(0.1)
            await self._async_send_button_command(CMD_FAN_OUT_ON)
        else:
            await self._async_send_button_command(CMD_FAN_IN_OFF); await asyncio.sleep(0.1)
            await self._async_send_button_command(CMD_FAN_OUT_OFF)

    async def async_set_select_option(self, entity_type: str, option_index: int) -> None:
        if entity_type == "display_mode":
            payload = bytes([0xBE, 0xEF, 0x0B, 0x01, option_index])
        elif entity_type == "fan_mode":
            payload = bytes([0xBE, 0xEF, 0x0B, 0x02, option_index])
        else:
            _LOGGER.error("Unknown select entity type: %s", entity_type)
            return
        await self._async_send_command_payload(payload)

    def get_parsed_status(self) -> Dict[str, Any]:
        return self._parsed_status.copy()