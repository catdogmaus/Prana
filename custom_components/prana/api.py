"""API for interacting with Prana BLE devices."""
import asyncio
import logging
import struct
import math
from datetime import datetime
from typing import Any, Optional, Callable, Dict

from bleak import BleakClient, BleakError
from bleak.backends.device import BLEDevice
from homeassistant.components import bluetooth
from bleak_retry_connector import establish_connection

from .const import (
    LOGGER, UUID_RWN_CHARACTERISTIC, PRANA_RESP_START_BYTE1, PRANA_RESP_START_BYTE2,
    PRANA_CMD_AUTH, PRANA_CMD_GET_STATE, PRANA_CMD_POWER_ON, PRANA_CMD_POWER_OFF,
    PRANA_CMD_AUTO_MODE, PRANA_CMD_BRIGHTNESS, PRANA_CMD_HEATING, 
    PRANA_CMD_WINTER_MODE, PRANA_CMD_FAN_LOCK, 
    PRANA_CMD_DISPLAY_LEFT, PRANA_CMD_DISPLAY_RIGHT, PranaMode, PranaDisplayMode, DISPLAY_MODE_MAP
)

BLE_TIMEOUT = 30

def _build_state_request_frame() -> bytearray:
    return bytearray([0xBE, 0xEF, 0x05, 0x01, 0x00, 0x00, 0x00, 0x00, 0x5A])

def _build_action_frame(command: int) -> bytearray:
    return bytearray([0xBE, 0xEF, 0x04, command])

def _build_time_sync_frame() -> bytearray:
    now = datetime.now()
    frame = bytearray(10)
    frame[0] = PRANA_RESP_START_BYTE1
    frame[1] = PRANA_RESP_START_BYTE2
    frame[2] = 0x0C 
    frame[3] = 0x01 
    frame[4] = now.second
    frame[5] = now.year % 100 
    frame[6] = now.month
    frame[7] = now.day
    frame[8] = now.hour
    frame[9] = now.minute
    return frame

class PranaBLEApiException(Exception):
    pass

class PranaBLEDevice:
    def __init__(self, device: BLEDevice, password: str, hass: Any = None,
                 disconnected_callback: Optional[Callable[[], None]] = None,
                 data_update_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
                 initial_display_mode: int = 0,
                 save_display_mode_callback: Optional[Callable[[int], None]] = None):
        self._device = device
        self._hass = hass
        self._password = password if password else "0000"
        self._client: Optional[BleakClient] = None
        self._lock = asyncio.Lock()
        self._is_connected = False
        self._disconnect_callback = disconnected_callback
        self._data_update_callback = data_update_callback
        self._current_state: Dict[str, Any] = {}
        self._disconnect_event = asyncio.Event()
        self._buffer = bytearray()
        self._parse_task: Optional[asyncio.Task] = None
        self.polling_enabled = True
        self.auto_restore_display = True 
        
        self._virtual_display_mode = initial_display_mode
        self._save_display_mode_callback = save_display_mode_callback

    def _set_virtual_display_mode(self, mode: int):
        """Updates internal memory and triggers save to HA config."""
        if self._virtual_display_mode != mode:
            self._virtual_display_mode = mode
            if self._save_display_mode_callback:
                self._save_display_mode_callback(mode)

    @property
    def name(self) -> str:
        return self._device.name or self._device.address

    @property
    def address(self) -> str:
        return self._device.address

    @property
    def is_connected(self) -> bool:
        return self._client is not None and self._client.is_connected

    async def set_polling(self, enable: bool):
        self.polling_enabled = enable
        if not enable:
            await self.stop()

    def _handle_disconnect(self, client: BleakClient) -> None:
        if not self._disconnect_event.is_set():
            self._client = None
            self._is_connected = False
            self._disconnect_event.set()
            if self._disconnect_callback:
                self._disconnect_callback()

    async def _notification_handler(self, sender: int, data: bytearray) -> None:
        if len(data) >= 2 and data[0] == PRANA_RESP_START_BYTE1 and data[1] == PRANA_RESP_START_BYTE2:
            self._buffer = bytearray(data)
        else:
            self._buffer.extend(data)

        if self._parse_task:
            self._parse_task.cancel()
        self._parse_task = asyncio.create_task(self._debounce_parse())

    async def _debounce_parse(self):
        await asyncio.sleep(0.25)
        if len(self._buffer) > 9:
            cmd = self._buffer[2]
            if cmd == 0x05: 
                self._parse_state_data(self._buffer)

    def _parse_state_data(self, data: bytes) -> None:
        if len(data) < 100: return 
        new_state = {}
        try:
            new_state["power"] = bool(data[10])
            
            b_raw = data[12]
            new_state["brightness_raw"] = b_raw
            if b_raw > 0:
                new_state["brightness"] = int(math.log2(b_raw)) + 1
            else:
                new_state["brightness"] = 1
                
            new_state["heating_on"] = bool(data[14])
            
            base_idx = data[20]
            new_state["base_mode_index"] = base_idx
            
            if base_idx == 1:
                new_state["mode"] = "Auto"
            elif base_idx == 2:
                new_state["mode"] = "Auto+"
            else:
                new_state["mode"] = "Manual"

            new_state["fans_locked"] = bool(data[22])
            new_state["speed"] = data[26] // 10
            new_state["speed_in"] = data[30] // 10
            new_state["speed_out"] = data[34] // 10
            new_state["winter_mode_active"] = bool(data[42])

            def convert_temp(offset):
                return (struct.unpack_from('>H', data, offset)[0] & 0x3FFF) / 10.0

            # SWAPPED: 48 is now Supply, 54 is now Indoor
            new_state["temp_supply"] = convert_temp(48)
            new_state["temp_out"] = convert_temp(51)
            new_state["temp_in"] = convert_temp(54)
            new_state["temp_exhaust"] = convert_temp(57)

            hum = data[60] - 128
            if 0 < hum < 100: new_state["humidity"] = hum

            new_state["co2"] = struct.unpack_from('>H', data, 61)[0] & 0x3FFF
            new_state["voc"] = struct.unpack_from('>H', data, 63)[0] & 0x7FFF
            new_state["pressure"] = 512 + data[78]
            
            dev_disp = data[99]
            if dev_disp != self._virtual_display_mode and 0 < dev_disp < 11 and dev_disp != 8:
                LOGGER.info("Self-healing display mode from %s to %s", self._virtual_display_mode, dev_disp)
                self._set_virtual_display_mode(dev_disp)

            try:
                new_state["display_mode"] = DISPLAY_MODE_MAP[PranaDisplayMode(self._virtual_display_mode)]
            except Exception:
                new_state["display_mode"] = "Fan State"
            
            delta_t = new_state["temp_in"] - new_state["temp_out"]
            if new_state["power"] and abs(delta_t) >= 1.0:
                eff = ((new_state["temp_supply"] - new_state["temp_out"]) / delta_t) * 100
                eff = max(0.0, min(100.0, eff))
                new_state["efficiency_pct"] = round(eff)
                if eff >= 80: new_state["efficiency"] = "Super"
                elif eff >= 60: new_state["efficiency"] = "High"
                else: new_state["efficiency"] = "Good"
            else:
                new_state["efficiency_pct"] = None
                new_state["efficiency"] = "Unknown"

            self._current_state.update(new_state)
            if self._data_update_callback:
                self._data_update_callback(self._current_state)
        except Exception as e:
            LOGGER.error("Parse error: %s", e)

    async def _ensure_connected_locked(self) -> bool:
        if not self.polling_enabled: return False
        if self._client and self._client.is_connected: return True
        try:
             if self._hass:
                 fresh_device = bluetooth.async_ble_device_from_address(self._hass, self.address, connectable=True)
                 if fresh_device: self._device = fresh_device
             self._client = await establish_connection(BleakClient, self._device, self.name, self._handle_disconnect, max_attempts=3)
             if not self._client or not self._client.is_connected: raise BleakError("Connection failed")
             self._is_connected = True
             self._disconnect_event.clear()
             
             await asyncio.sleep(0.5)
             await self._client.start_notify(UUID_RWN_CHARACTERISTIC, self._notification_handler)
             await asyncio.sleep(0.2)
             
             await self._send_command_locked(_build_time_sync_frame())
             await asyncio.sleep(0.5)
             return True
        except Exception:
             await self._disconnect_client()
             return False

    async def _disconnect_client(self):
        client = self._client
        self._client = None
        self._is_connected = False
        if client:
            try: await client.disconnect()
            except: pass
        if not self._disconnect_event.is_set():
            self._disconnect_event.set()

    async def stop(self) -> None:
        await self._disconnect_client()

    async def _send_command_locked(self, frame: bytearray) -> bool:
        if not self._client or not self._client.is_connected: return False
        self._buffer = bytearray() 
        try:
            await self._client.write_gatt_char(UUID_RWN_CHARACTERISTIC, frame, response=True)
            return True
        except Exception:
            self._handle_disconnect(self._client)
            return False

    async def _execute_action(self, frame: bytearray) -> bool:
        async with self._lock:
            if not await self._ensure_connected_locked(): return False
            success = await self._send_command_locked(frame)
            if success:
                await asyncio.sleep(0.5)
                await self._send_command_locked(_build_state_request_frame())
                await asyncio.sleep(1.0) 
            return success

    async def _force_manual_locked(self):
        mode_idx = self._current_state.get("base_mode_index", 0)
        if mode_idx != 0:
            diff = (0 - mode_idx + 3) % 3
            for _ in range(diff):
                await self._send_command_locked(_build_action_frame(0x18))
                await asyncio.sleep(0.5)
            self._current_state["base_mode_index"] = 0
            self._current_state["mode"] = "Manual"

    async def _set_display_mode_locked(self, target: int) -> bool:
        current = self._virtual_display_mode
        if current == target: return True
        
        diff_r = (target - current + 11) % 11
        diff_l = (current - target + 11) % 11
        
        steps = 0
        if diff_r <= diff_l:
            cmd = PRANA_CMD_DISPLAY_RIGHT
            c = current
            while c != target:
                c = (c + 1) % 11
                if c == 8: c = (c + 1) % 11 
                steps += 1
        else:
            cmd = PRANA_CMD_DISPLAY_LEFT
            c = current
            while c != target:
                c = (c - 1 + 11) % 11
                if c == 8: c = (c - 1 + 11) % 11 
                steps += 1
        
        for _ in range(steps):
            await self._send_command_locked(_build_action_frame(cmd))
            await asyncio.sleep(0.5)
            
        self._set_virtual_display_mode(target)
        return True

    async def update_data(self) -> Dict[str, Any]:
        async with self._lock:
            if not await self._ensure_connected_locked():
                return self._current_state.copy()
            await self._send_command_locked(_build_state_request_frame())
            await asyncio.sleep(1.0) 
            return self._current_state.copy()

    async def set_power(self, power: bool) -> bool:
        self._set_virtual_display_mode(0) 
        cmd = 0x0A if power else 0x01
        return await self._execute_action(_build_action_frame(cmd))
    
    async def set_speed(self, speed: int, target: str = "both") -> bool:
        async with self._lock:
             if not await self._ensure_connected_locked(): return False
             
             previous_display = self._virtual_display_mode
             self._set_virtual_display_mode(0) 
             
             await self._force_manual_locked()
             
             if self._current_state.get("fans_locked", False): target = "both"
             speed = max(1, min(10, speed))
             
             if target == "in":
                 current = self._current_state.get("speed_in", 1)
                 cmd_up, cmd_down = 0x0E, 0x0F
             elif target == "out":
                 current = self._current_state.get("speed_out", 1)
                 cmd_up, cmd_down = 0x11, 0x12
             else:
                 current = self._current_state.get("speed", 1)
                 cmd_up, cmd_down = 0x0C, 0x0B
                 
             diff = speed - current
             if diff == 0: return True
                 
             cmd = cmd_up if diff > 0 else cmd_down
             for _ in range(abs(diff)):
                 await self._send_command_locked(_build_action_frame(cmd))
                 await asyncio.sleep(0.3)
             
             if self.auto_restore_display and previous_display != 0:
                 diff_r = (previous_display - 0 + 11) % 11
                 diff_l = (0 - previous_display + 11) % 11
                 steps = 0
                 if diff_r <= diff_l:
                     cmd = PRANA_CMD_DISPLAY_RIGHT
                     c = 0
                     while c != previous_display:
                         c = (c + 1) % 11
                         if c == 8: c = (c + 1) % 11 
                         steps += 1
                 else:
                     cmd = PRANA_CMD_DISPLAY_LEFT
                     c = 0
                     while c != previous_display:
                         c = (c - 1 + 11) % 11
                         if c == 8: c = (c - 1 + 11) % 11 
                         steps += 1
                 for _ in range(steps):
                     await self._send_command_locked(_build_action_frame(cmd))
                     await asyncio.sleep(0.5)
                 self._set_virtual_display_mode(previous_display)

             await asyncio.sleep(0.5)
             await self._send_command_locked(_build_state_request_frame())
             await asyncio.sleep(1.0)
             return True

    async def set_mode(self, mode: PranaMode) -> bool:
        async with self._lock:
             if not await self._ensure_connected_locked(): return False
             
             previous_display = self._virtual_display_mode
             self._set_virtual_display_mode(0) 
             
             current_idx = self._current_state.get("base_mode_index", 0)
             target_idx = mode.value
             diff = (target_idx - current_idx + 3) % 3
             if diff > 0:
                 for _ in range(diff):
                     await self._send_command_locked(_build_action_frame(0x18))
                     await asyncio.sleep(0.5)
                     
             if self.auto_restore_display and previous_display != 0:
                 diff_r = (previous_display - 0 + 11) % 11
                 diff_l = (0 - previous_display + 11) % 11
                 steps = 0
                 if diff_r <= diff_l:
                     cmd = PRANA_CMD_DISPLAY_RIGHT
                     c = 0
                     while c != previous_display:
                         c = (c + 1) % 11
                         if c == 8: c = (c + 1) % 11 
                         steps += 1
                 else:
                     cmd = PRANA_CMD_DISPLAY_LEFT
                     c = 0
                     while c != previous_display:
                         c = (c - 1 + 11) % 11
                         if c == 8: c = (c - 1 + 11) % 11 
                         steps += 1
                 for _ in range(steps):
                     await self._send_command_locked(_build_action_frame(cmd))
                     await asyncio.sleep(0.5)
                 self._set_virtual_display_mode(previous_display)

             await self._send_command_locked(_build_state_request_frame())
             await asyncio.sleep(1.0)
             return True

    async def set_display_mode(self, mode: PranaDisplayMode) -> bool:
        async with self._lock:
            if not await self._ensure_connected_locked(): return False
            current = self._virtual_display_mode
            target = mode.value
            
            if current == target: return True
            
            diff_r = (target - current + 11) % 11
            diff_l = (current - target + 11) % 11
            
            steps = 0
            if diff_r <= diff_l:
                cmd = PRANA_CMD_DISPLAY_RIGHT
                c = current
                while c != target:
                    c = (c + 1) % 11
                    if c == 8: c = (c + 1) % 11 
                    steps += 1
            else:
                cmd = PRANA_CMD_DISPLAY_LEFT
                c = current
                while c != target:
                    c = (c - 1 + 11) % 11
                    if c == 8: c = (c - 1 + 11) % 11 
                    steps += 1
            
            for _ in range(steps):
                await self._send_command_locked(_build_action_frame(cmd))
                await asyncio.sleep(0.5)
                
            self._set_virtual_display_mode(target)
            await self._send_command_locked(_build_state_request_frame())
            await asyncio.sleep(1.0)
            return True

    async def set_brightness(self, brightness: int) -> bool:
        async with self._lock:
             if not await self._ensure_connected_locked(): return False
             current_lvl = self._current_state.get("brightness", 1)
             diff = (brightness - current_lvl + 6) % 6
             if diff > 0:
                 for _ in range(diff):
                     await self._send_command_locked(_build_action_frame(0x02))
                     await asyncio.sleep(0.5)
                 await self._send_command_locked(_build_state_request_frame())
                 await asyncio.sleep(1.0)
             return True

    async def toggle_heating(self, state: bool) -> bool:
        if self._current_state.get("heating_on", False) != state:
             return await self._execute_action(_build_action_frame(0x05))
        return True

    async def toggle_winter_mode(self, state: bool) -> bool:
        if self._current_state.get("winter_mode_active", False) != state:
             return await self._execute_action(_build_action_frame(0x16))
        return True

    async def toggle_fans_locked(self, state: bool) -> bool:
        if self._current_state.get("fans_locked", False) != state:
             return await self._execute_action(_build_action_frame(0x09))
        return True