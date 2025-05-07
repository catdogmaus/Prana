"""The Prana Integration."""
import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import timedelta

from bleak import BleakClient, BleakError # Added BleakError import
from bleak.backends.device import BLEDevice

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady, ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER, UPDATE_INTERVAL_SECONDS
from .api import PranaBLEDevice, PranaBLEApiException

# Define platforms to be set up
PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.FAN,
    Platform.SELECT,
    Platform.NUMBER,
    Platform.BUTTON,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Prana Integration from a config entry."""
    _LOGGER = LOGGER # Use logger from const
    address = entry.data[CONF_ADDRESS]
    password = entry.data[CONF_PASSWORD]
    _LOGGER.error("!!! PRANA SETUP STARTING for %s", address) # FORCED LOG

    # Get BLE device
    ble_device = bluetooth.async_ble_device_from_address(hass, address, connectable=True)
    if not ble_device:
        _LOGGER.error("!!! PRANA SETUP FAILED: Device %s not found by Bluetooth.", address)
        # Let HA handle retry if device not found initially
        raise ConfigEntryNotReady(f"Prana device {address} not found by Bluetooth integration.")

    # Create API instance
    api = PranaBLEDevice(ble_device, password)

    # Create Coordinator
    coordinator = PranaDataUpdateCoordinator(hass, api, entry.entry_id)

    # Assign coordinator methods to API callbacks
    api._data_update_callback = coordinator._handle_api_data_update
    api._disconnected_callback = coordinator._handle_api_disconnect

    # Store API and Coordinator for platforms
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "api": api,
        "coordinator": coordinator,
    }

    # --- Let Coordinator handle the first refresh ---
    # We do NOT await the first refresh here. The coordinator schedules it.
    # This prevents blocking setup if the initial connection fails.
    _LOGGER.debug("Deferring first refresh to coordinator for %s", address)

    # Set up platforms (forward entry setup)
    _LOGGER.debug("Setting up Prana platforms for %s", address)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _LOGGER.debug("Prana platforms setup complete for %s", address)


    # Add update listener for options flow
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    # Add coordinator shutdown callback for unload
    entry.async_on_unload(coordinator.async_request_shutdown)

    _LOGGER.info("Prana integration setup initiated for %s. Coordinator will connect and fetch data.", entry.title)
    # Return True immediately. Connection/data fetching happens in the background via coordinator.
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading Prana integration entry for %s", entry.title)
    coordinator: PranaDataUpdateCoordinator | None = hass.data.get(DOMAIN, {}).get(entry.entry_id, {}).get("coordinator")

    if coordinator:
         _LOGGER.debug("Requesting shutdown for coordinator %s", coordinator.name)
         await coordinator.async_request_shutdown()
         _LOGGER.debug("Coordinator shutdown request complete for %s", coordinator.name)

    _LOGGER.debug("Unloading platforms for %s", entry.title)
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    _LOGGER.debug("Platform unload status for %s: %s", entry.title, unload_ok)

    if unload_ok:
        data = hass.data[DOMAIN].pop(entry.entry_id, None)
        if data:
            api: PranaBLEDevice = data["api"]
            _LOGGER.debug("Stopping API for %s", api.address)
            await api.stop()
            _LOGGER.debug("API stopped for %s", api.address)
        else:
            _LOGGER.warning("No data found in hass.data for entry %s during unload.", entry.entry_id)

    _LOGGER.debug("Prana integration unload completed for %s. Status: %s", entry.title, unload_ok)
    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    _LOGGER.debug("Update listener called for Prana entry %s", entry.title)
    pass


class PranaDataUpdateCoordinator(DataUpdateCoordinator[Dict[str, Any]]):
    """Manages fetching Prana data."""

    def __init__(self, hass: HomeAssistant, api: PranaBLEDevice, entry_id: str):
        """Initialize."""
        self._LOGGER = LOGGER
        self._LOGGER.error("!!! PRANA COORDINATOR INIT for %s", api.address) # FORCED LOG
        self.api = api
        self._connect_lock = asyncio.Lock()
        self._shutdown = False
        self._hass = hass

        super().__init__(
            hass,
            self._LOGGER,
            name=f"{DOMAIN}-{api.address}",
            update_interval=timedelta(seconds=UPDATE_INTERVAL_SECONDS),
        )
        self._LOGGER.debug("PranaDataUpdateCoordinator initialized for %s", api.address)
        # Callbacks assigned after coordinator init in async_setup_entry

    async def _async_update_data(self) -> Dict[str, Any]:
        """Fetch data from API for coordinator updates."""
        self._LOGGER.error("!!! PRANA ASYNC UPDATE DATA START for %s", self.api.address) # FORCED LOG
        async with self._connect_lock:
            self._LOGGER.debug(">>> _async_update_data acquired lock for %s", self.api.address)
            try:
                self._LOGGER.debug(">>> _async_update_data calling _ensure_connected for %s", self.api.address)
                connect_success = await self.api._ensure_connected()
                self._LOGGER.debug(">>> _async_update_data _ensure_connected finished for %s. Result: %s, Connected: %s", self.api.address, connect_success, self.api.is_connected)

                if not connect_success or not self.api.is_connected:
                     self._LOGGER.error(">>> _async_update_data: API connection failed or device not connected after _ensure_connected for %s.", self.api.address)
                     raise UpdateFailed(f"Failed to connect/authenticate via API for {self.api.address}")

                self._LOGGER.debug(">>> _async_update_data calling request_state for %s", self.api.address)
                request_ok = await self.api.request_state()
                self._LOGGER.debug(">>> _async_update_data request_state returned: %s for %s", request_ok, self.api.address)

                if not request_ok:
                    self._LOGGER.warning(">>> _async_update_data: Failed to send request_state command for %s", self.api.address)
                    # Check cache, raise UpdateFailed only if no data at all exists
                    cached_data = await self.api.get_current_state()
                    if cached_data:
                         self._LOGGER.warning(">>> _async_update_data: Returning cached data despite failed request for %s", self.api.address)
                         return cached_data
                    else:
                         raise UpdateFailed(f"Failed sending state request command and no cached data for {self.api.address}")

                self._LOGGER.debug(">>> _async_update_data sleeping briefly after request_state for %s", self.api.address)
                await asyncio.sleep(5.0) # Pause for potential notifications

                self._LOGGER.debug(">>> _async_update_data calling get_current_state for %s", self.api.address)
                latest_data = await self.api.get_current_state()

                if not latest_data:
                    # Failure if no data received via notification after successful request
                    self._LOGGER.warning(">>> _async_update_data: No state data available from API after request for %s", self.api.address)
                    raise UpdateFailed(f"No state data received from {self.api.address}")

                self._LOGGER.debug(">>> _async_update_data returning data for %s: %s", self.api.address, latest_data)
                return latest_data

            except PranaBLEApiException as err:
                 self._LOGGER.error(">>> _async_update_data caught PranaBLEApiException for %s: %s", self.api.address, err)
                 raise UpdateFailed(f"API Error during update: {err}") from err
            except BleakError as err: # Catch BleakError now that it's imported
                 self._LOGGER.warning(">>> _async_update_data caught BleakError for %s: %s", self.api.address, err)
                 raise UpdateFailed(f"Connection error during update: {err}") from err
            except UpdateFailed as err: # Re-raise expected UpdateFailed
                 self._LOGGER.error(">>> _async_update_data caught UpdateFailed for %s: %s", self.api.address, err)
                 raise
            except Exception as err:
                 self._LOGGER.exception(">>> _async_update_data caught Unexpected error for %s", self.api.address)
                 raise UpdateFailed(f"Unexpected error during update: {err}") from err
            finally:
                 self._LOGGER.debug(">>> _async_update_data released lock for %s", self.api.address)

    @callback
    def _handle_api_data_update(self, data: dict):
        """Process data update from the API notification handler."""
        self._LOGGER.debug("Coordinator received data update via callback for %s: %s", self.api.address, data)
        self.async_set_updated_data(data)

    @callback
    def _handle_api_disconnect(self):
        """Handle disconnect notification from the API."""
        if not self._shutdown:
            self._LOGGER.warning("Coordinator notified of disconnect for %s", self.api.address)
            self.async_update_listeners()

    @callback
    async def async_request_shutdown(self) -> None:
        """Cleanup resources when entry is being unloaded."""
        if self._shutdown:
             self._LOGGER.debug("Shutdown already requested for coordinator %s", self.name)
             return
        self._LOGGER.debug("Coordinator shutdown requested for %s", self.name)
        self._shutdown = True
        self._LOGGER.debug("Cancelling coordinator refresh tasks for %s", self.name)
        self.async_cancel_refresh()
        # API stop is handled in async_unload_entry
        self._LOGGER.debug("Coordinator shutdown actions complete for %s", self.name)