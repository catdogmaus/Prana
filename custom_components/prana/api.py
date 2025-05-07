"""API for interacting with Prana BLE devices."""
import asyncio
import logging
from typing import Any, Optional, Callable, Dict

from bleak import BleakClient, BleakError
from bleak.backends.device import BLEDevice

from .const import (
    LOGGER,
    UUID_PRANA_WRITE,
    UUID_PRANA_READ,
    UUID_RWN_CHARACTERISTIC, # Using this based on user feedback
    UUID_PRANA_SERVICE,      # Using this based on user feedback
    PRANA_CMD_MAX_LEN,
    PRANA_CMD_AUTH,
    PRANA_CMD_SET_SPEED,
    PRANA_CMD_SET_MODE,
    PRANA_CMD_SET_POWER,
    PRANA_CMD_GET_STATE,
    PRANA_CMD_RESET_FILTER,
    PRANA_CMD_SET_BRIGHTNESS,
    PRANA_RESP_START_BYTE1,
    PRANA_RESP_START_BYTE2,
    PranaMode,
)

# Timeout for BLE operations
BLE_TIMEOUT = 20
RECONNECT_DELAY = 5

def _calculate_checksum(data: bytes) -> int:
    """Calculate the checksum for a Prana command/response."""
    return sum(data) & 0xFF

def _build_frame(command: int, password: str, args: Optional[list[int]] = None) -> bytearray:
    """Build the full 20-byte command frame to send to the Prana device."""
    if args is None:
        args = []

    frame = bytearray(PRANA_CMD_MAX_LEN) # Should be 20
    frame[0] = command
    pwd_bytes = password.encode('ascii')
    frame[1:5] = pwd_bytes[:4]

    arg_len = len(args)
    args_start_index = 5
    # Initialize args_end_index before the conditional block
    args_end_index = args_start_index

    if arg_len > 0:
        args_end_index = args_start_index + arg_len
        if args_end_index >= PRANA_CMD_MAX_LEN - 1:
            LOGGER.warning("Arguments too long for frame, truncating.")
            args_end_index = PRANA_CMD_MAX_LEN - 2
            arg_len = args_end_index - args_start_index
        frame[args_start_index:args_end_index] = args[:arg_len]

    # Calculate checksum ONLY over the first 5 bytes (Command + Password)
    checksum_payload_len = 5
    calculated_checksum = _calculate_checksum(frame[:checksum_payload_len])
    LOGGER.debug("Checksum calculated over first %d bytes: %s", checksum_payload_len, frame[:checksum_payload_len].hex())

    frame[PRANA_CMD_MAX_LEN - 1] = calculated_checksum

    LOGGER.debug("Built full 20-byte frame: %s", frame.hex())
    return frame


class PranaBLEApiException(Exception):
    """Custom exception for API errors."""

class PranaBLEDevice:
    """Class to manage communication with a Prana BLE device."""

    def __init__(
        self,
        device: BLEDevice,
        password: str,
        disconnected_callback: Optional[Callable[[], None]] = None,
        data_update_callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> None:
        """Initialize the Prana BLE device API."""
        self._device = device
        self._password = password
        self._client: Optional[BleakClient] = None
        self._lock = asyncio.Lock()
        self._is_connected = False
        self._disconnect_callback = disconnected_callback
        self._data_update_callback = data_update_callback
        self._notification_queue = asyncio.Queue()
        self._current_state: Dict[str, Any] = {}
        self._disconnect_event = asyncio.Event()
        self._is_authenticated = False # Track authentication status

    @property
    def name(self) -> str:
        """Return the name of the device."""
        return self._device.name or self._device.address

    @property
    def address(self) -> str:
        """Return the address of the device."""
        return self._device.address

    @property
    def is_connected(self) -> bool:
        """Return the connection status."""
        return self._client is not None and self._client.is_connected

    def _handle_disconnect(self, client: BleakClient) -> None:
        """Handle spontaneous disconnection."""
        if not self._disconnect_event.is_set():
            LOGGER.warning("Device %s disconnected (reported by Bleak)", self.address)
            self._client = None
            self._is_connected = False
            self._is_authenticated = False # Reset auth status on disconnect
            self._disconnect_event.set()
            if self._disconnect_callback:
                self._disconnect_callback()
            else:
                LOGGER.warning("_disconnect_callback not set for Prana API")

    async def _notification_handler(self, sender: int, data: bytearray) -> None:
        """Handle incoming data notifications from UUID_RWN_CHARACTERISTIC."""
        LOGGER.error("!!! NOTIFICATION HANDLER CALLED (Handle: %d, Data: %s)", sender, data.hex()) # FORCED LOG
        LOGGER.debug("Received notification (handle %d): %s", sender, data.hex())
        if len(data) < 6:
            LOGGER.warning("Received runt frame: %s", data.hex())
            return
        if data[0] != PRANA_RESP_START_BYTE1 or data[1] != PRANA_RESP_START_BYTE2:
            LOGGER.warning("Received invalid frame start: %s", data.hex())
            return

        frame_len = data[2]
        expected_total_len = 3 + frame_len + 1
        if len(data) < expected_total_len:
             LOGGER.warning("Received incomplete frame (expected %d bytes, got %d): %s", expected_total_len, len(data), data.hex())
             return

        payload = data[3 : 3 + frame_len]
        received_checksum = data[3 + frame_len]
        calculated_checksum = _calculate_checksum(payload)

        if received_checksum != calculated_checksum:
            LOGGER.warning(
                "Checksum mismatch! Got %02x, calculated %02x. Frame: %s",
                received_checksum, calculated_checksum, data.hex()
            )
            return

        cmd = payload[0]
        if cmd == PRANA_CMD_GET_STATE:
            self._parse_state_data(payload[1:])
        elif cmd == PRANA_CMD_AUTH:
             if len(payload) > 1:
                  if payload[1] == 0x01:
                      LOGGER.info("Received potential AUTH Success indicator for %s", self.address)
                      self._is_authenticated = True
                  else:
                      LOGGER.warning("Received potential AUTH Failure indicator for %s: %s", self.address, payload.hex())
                      self._is_authenticated = False
             else:
                 LOGGER.info("Received AUTH response for %s (no specific data)", self.address)
                 self._is_authenticated = True # Assume ACK means ok
        # Add elif for other command responses if needed

    def _parse_state_data(self, data: bytes) -> None:
        """Parse the state data received from the device (after 0x55 AA len 05)."""
        if len(data) < 14:
             LOGGER.warning("State data payload too short: %d bytes. Data: %s", len(data), data.hex())
             return

        new_state = {}
        try:
            new_state["power"] = bool(data[0])
            new_state["speed"] = data[1]

            raw_mode = data[2]
            try:
                mode_enum = PranaMode(raw_mode)
                new_state["mode"] = mode_enum.name
            except ValueError:
                 LOGGER.warning("Unknown mode value received: %d", raw_mode)
                 new_state["mode"] = self._current_state.get("mode", None)

            new_state["winter_mode_active"] = bool(data[3])
            new_state["auto_mode_active"] = bool(data[4])

            new_state["temp_in"] = int.from_bytes([data[5]], byteorder='little', signed=True)
            new_state["temp_out"] = int.from_bytes([data[6]], byteorder='little', signed=True)
            new_state["temp_exhaust"] = int.from_bytes([data[7]], byteorder='little', signed=True)
            new_state["temp_supply"] = int.from_bytes([data[8]], byteorder='little', signed=True)

            new_state["humidity"] = data[9] if data[9] != 0xFF else None

            co2_bytes = data[10:12]
            new_state["co2"] = int.from_bytes(co2_bytes, byteorder='little', signed=False) if co2_bytes != b'\xff\xff' else None

            voc_bytes = data[12:14]
            new_state["voc"] = int.from_bytes(voc_bytes, byteorder='little', signed=False) if voc_bytes != b'\xff\xff' else None

            new_state["filter_timer_days"] = data[14] if len(data) > 14 else None
            new_state["brightness"] = data[15] if len(data) > 15 else None

            # If we successfully parse state, assume we are functionally authenticated enough to read.
            if not self._is_authenticated:
                LOGGER.info("Marking as authenticated due to successful state data parsing.")
                self._is_authenticated = True

            self._current_state = new_state
            LOGGER.debug("Parsed state: %s", self._current_state)
            if self._data_update_callback:
                self._data_update_callback(self._current_state)

        except IndexError:
            LOGGER.error("Error parsing state data - data too short: %s", data.hex())
        except Exception as e:
            LOGGER.error("Unexpected error parsing state data: %s", e, exc_info=True)

    async def _ensure_connected(self) -> bool:
        """Ensure the device is connected, attempting connection and notification setup."""
        LOGGER.debug(">>> _ensure_connected START. Currently connected: %s", self.is_connected)
        if self._client and self._client.is_connected:
            LOGGER.debug(">>> _ensure_connected: Already connected.")
            return True

        # Lock is acquired by the caller
        LOGGER.debug(">>> _ensure_connected attempting connection (lock held by caller)")
        if self._client and self._client.is_connected:
            LOGGER.debug(">>> _ensure_connected: Already connected (checked after lock).")
            return True

        LOGGER.debug(">>> _ensure_connected: Attempting bleak connect to %s", self.address)
        try:
            if not self._client:
                 LOGGER.debug(">>> _ensure_connected: Creating new BleakClient")
                 self._client = BleakClient(self._device, disconnected_callback=self._handle_disconnect)

            await self._client.connect(timeout=BLE_TIMEOUT)
            self._is_connected = True
            self._disconnect_event.clear()
            LOGGER.info(">>> _ensure_connected: Connected successfully to %s", self.address)

            try:
                LOGGER.debug(">>> _ensure_connected: Attempting start_notify for %s", UUID_RWN_CHARACTERISTIC)
                await self._client.start_notify(UUID_RWN_CHARACTERISTIC, self._notification_handler)
                LOGGER.debug(">>> _ensure_connected: Started notifications successfully.")
            except Exception as e:
                LOGGER.error(">>> _ensure_connected: Error starting notifications: %s", e)
                await self._disconnect_client()
                return False # Cannot proceed without notifications

            # --- Authentication attempt (result logged but doesn't block connection success) ---
            LOGGER.debug(">>> _ensure_connected: Calling authenticate (result ignored for connection success)...")
            auth_success = await self.authenticate() # Authenticate is now separate
            LOGGER.info(">>> _ensure_connected: Authenticate attempt result: %s (continuing regardless)", auth_success)
            if auth_success:
                 self._is_authenticated = True # Set internal flag if AUTH send succeeds

            LOGGER.debug(">>> _ensure_connected: Connection and notification setup successful.")
            return True # Return True if connect and notify setup worked, regardless of auth result

        except BleakError as e:
            LOGGER.error(">>> _ensure_connected: BleakError connecting to %s: %s", self.address, e)
            await self._disconnect_client()
            return False
        except Exception as e:
            LOGGER.error(">>> _ensure_connected: Unexpected error during connection/setup to %s: %s", self.address, e, exc_info=True)
            await self._disconnect_client()
            return False

    async def _disconnect_client(self):
        """Safely disconnect the BleakClient."""
        client = self._client
        self._client = None
        self._is_connected = False
        self._is_authenticated = False # Reset auth on disconnect

        if client and client.is_connected:
             LOGGER.error("!!! DISCONNECTING CLIENT (connected=True) for %s", self.address) # FORCED LOG
             try:
                await client.stop_notify(UUID_RWN_CHARACTERISTIC)
             except Exception as e:
                 LOGGER.warning("Error stopping notifications during disconnect for %s: %s", self.address, e)
             try:
                await client.disconnect()
                LOGGER.info("Disconnected from %s", self.address)
             except Exception as e:
                 LOGGER.warning("Error during explicit disconnect for %s: %s", self.address, e)
        else:
             LOGGER.error("!!! DISCONNECT CLIENT CALLED but client was None or not connected for %s", self.address) # FORCED LOG

        if not self._disconnect_event.is_set():
            self._disconnect_event.set()

    async def stop(self) -> None:
        """Stop communication and disconnect."""
        LOGGER.debug("Stopping communication with %s", self.address)
        await self._disconnect_client()

    async def _send_command(self, command: int, args: Optional[list[int]] = None) -> bool:
        """Build and send a command frame. Assumes lock is held and connection *might* exist."""
        # Check connection status *before* building frame
        if not self.is_connected or not self._client:
             LOGGER.error(">>> _send_command: Cannot send command 0x%02X, client not connected.", command)
             return False

        LOGGER.debug(">>> _send_command START for command 0x%02X", command)
        try:
            frame = _build_frame(command, self._password, args)
        except Exception as e:
            LOGGER.error(">>> _send_command: Failed to build frame for command 0x%02X: %s", command, e, exc_info=True)
            return False

        LOGGER.debug(">>> _send_command: Sending frame (full 20 bytes): %s", frame.hex())
        try:
            await self._client.write_gatt_char(UUID_RWN_CHARACTERISTIC, frame, response=False)
            LOGGER.debug(">>> _send_command: Command 0x%02X sent successfully (20 bytes)", command)
            await asyncio.sleep(0.2)
            return True
        except BleakError as e:
            LOGGER.error(">>> _send_command: BleakError sending command 0x%02X (20 bytes): %s", command, e)
            self._handle_disconnect(self._client) # Let coordinator know
            return False
        except Exception as e:
            LOGGER.error(">>> _send_command: Unexpected error sending command 0x%02X (20 bytes): %s", command, e, exc_info=True)
            self._handle_disconnect(self._client) # Let coordinator know
            return False


    # --- Public API Methods ---

    async def authenticate(self) -> bool:
        """Authenticate with the device using the explicit AUTH command."""
        # Assumes lock is held by caller (_ensure_connected)
        LOGGER.debug(">>> authenticate START for %s", self.address)
        success = await self._send_command(PRANA_CMD_AUTH) # Use internal send
        if success:
            LOGGER.info(">>> authenticate: AUTH command sent successfully.")
            await asyncio.sleep(0.5) # Keep short pause after auth send
            LOGGER.debug(">>> authenticate END (sent ok)")
            # Return True based on send success only. self._is_authenticated might be set later by response/parsing.
            return True
        else:
            LOGGER.error(">>> authenticate: Failed to send AUTH command.")
            LOGGER.debug(">>> authenticate END (send failed)")
            return False

    async def request_state(self) -> bool:
        """Request the current state from the device AND attempt to read it directly."""
        # Assumes lock is held by caller (_async_update_data)
        LOGGER.debug(">>> request_state START for %s", self.address)

        # Send the GET_STATE command first
        send_success = await self._send_command(PRANA_CMD_GET_STATE)
        if not send_success:
            LOGGER.warning(">>> request_state: Failed to send GET_STATE command.")
            return False # Return False if command send failed

        # --- Attempt Direct Read ---
        LOGGER.debug(">>> request_state: GET_STATE sent. Attempting direct read from %s", UUID_RWN_CHARACTERISTIC)
        try:
            # --- Timing Adjustment ---
            await asyncio.sleep(1.0) # Increased delay to 1.0 second
            # --- End Timing Adjustment ---

            if not self.is_connected or not self._client:
                LOGGER.warning(">>> request_state: Disconnected before read attempt.")
                return False

            # Explicitly use UUID_RWN_CHARACTERISTIC for read
            raw_data = await self._client.read_gatt_char(UUID_RWN_CHARACTERISTIC)
            LOGGER.info(">>> request_state: Successfully read %d bytes: %s", len(raw_data), raw_data.hex())

            # --- Parse the read data ---
            if len(raw_data) >= 6 and raw_data[0] == PRANA_RESP_START_BYTE1 and raw_data[1] == PRANA_RESP_START_BYTE2:
                 frame_len = raw_data[2]
                 if frame_len == 0 or frame_len > (len(raw_data) - 4):
                     LOGGER.warning(">>> request_state: Read data has invalid frame length byte: %d", frame_len)
                     return False

                 expected_total_len = 3 + frame_len + 1
                 if len(raw_data) >= expected_total_len:
                     payload = raw_data[3 : 3 + frame_len]
                     received_checksum = raw_data[3 + frame_len]
                     calculated_checksum = _calculate_checksum(payload)
                     if received_checksum == calculated_checksum:
                          cmd = payload[0]
                          if cmd == PRANA_CMD_GET_STATE:
                              LOGGER.debug(">>> request_state: Read data appears to be valid state response. Parsing...")
                              self._parse_state_data(payload[1:]) # Parse and update _current_state
                              return True # Indicate success (state updated via read)
                          else:
                              LOGGER.warning(">>> request_state: Read data has valid structure but unexpected command: 0x%02X", cmd)
                     else:
                          LOGGER.warning(">>> request_state: Read data checksum mismatch. Got %02X, Calc %02X", received_checksum, calculated_checksum)
                 else:
                     LOGGER.warning(">>> request_state: Read data incomplete frame. Expected %d, Got %d", expected_total_len, len(raw_data))
            # --- Added check for all zeros ---
            elif all(b == 0 for b in raw_data):
                 LOGGER.warning(">>> request_state: Read data was all zeros. Possible auth issue or device error.")
            # --- End added check ---
            else:
                LOGGER.warning(">>> request_state: Read data doesn't match expected response format: %s", raw_data.hex())

            # If read succeeded but parsing failed or format was wrong, return False
            LOGGER.warning(">>> request_state: Read succeeded but data parsing failed or format invalid.")
            return False

        except BleakError as e:
            LOGGER.error(">>> request_state: BleakError during read_gatt_char: %s", e)
            self._handle_disconnect(self._client) # Assume connection issue on read error
            return False
        except Exception as e:
            LOGGER.error(">>> request_state: Unexpected error during read_gatt_char: %s", e, exc_info=True)
            return False

    # --- Control Methods (acquire lock, ensure connected, check auth, send) ---
    async def set_power(self, power: bool) -> bool:
        """Turn the device on or off."""
        LOGGER.debug("Setting power to %s for %s", power, self.address)
        async with self._lock:
            if not await self._ensure_connected(): return False
            if not self._is_authenticated:
                 LOGGER.warning("Attempted to set power but not authenticated.")
                 return False
            return await self._send_command(PRANA_CMD_SET_POWER, [int(power)])

    async def set_speed(self, speed: int) -> bool:
        """Set the fan speed (1-10 range assumed)."""
        clamped_speed = max(1, min(10, speed))
        LOGGER.debug("Setting speed to %d for %s", clamped_speed, self.address)
        async with self._lock:
            if not await self._ensure_connected(): return False
            if not self._is_authenticated:
                 LOGGER.warning("Attempted to set speed but not authenticated.")
                 return False
            return await self._send_command(PRANA_CMD_SET_SPEED, [clamped_speed])

    async def set_mode(self, mode: PranaMode) -> bool:
        """Set the operating mode."""
        LOGGER.debug("Setting mode to %s (%d) for %s", mode.name, mode.value, self.address)
        async with self._lock:
            if not await self._ensure_connected(): return False
            if not self._is_authenticated:
                 LOGGER.warning("Attempted to set mode but not authenticated.")
                 return False
            return await self._send_command(PRANA_CMD_SET_MODE, [mode.value])

    async def set_brightness(self, brightness: int) -> bool:
        """Set the display brightness (0-100 range assumed)."""
        clamped_brightness = max(0, min(100, brightness))
        LOGGER.debug("Setting brightness to %d for %s", clamped_brightness, self.address)
        async with self._lock:
            if not await self._ensure_connected(): return False
            if not self._is_authenticated:
                 LOGGER.warning("Attempted to set brightness but not authenticated.")
                 return False
            return await self._send_command(PRANA_CMD_SET_BRIGHTNESS, [clamped_brightness])

    async def reset_filter(self) -> bool:
        """Reset the filter timer."""
        LOGGER.debug("Resetting filter for %s", self.address)
        async with self._lock:
            if not await self._ensure_connected(): return False
            if not self._is_authenticated:
                 LOGGER.warning("Attempted to reset filter but not authenticated.")
                 return False
            return await self._send_command(PRANA_CMD_RESET_FILTER)

    async def get_current_state(self) -> Dict[str, Any]:
         """Return the last known state (updated by read or notification)."""
         return self._current_state.copy()