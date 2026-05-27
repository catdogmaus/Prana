"""The Prana Integration."""
import asyncio
import logging
import time
from datetime import timedelta
from typing import Any, Dict

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER, UPDATE_INTERVAL_SECONDS, DEFAULT_PASSWORD, CONF_MODEL
from .api import PranaBLEDevice

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.FAN,
    Platform.SELECT,
    Platform.NUMBER,
    Platform.BUTTON,
]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    address = entry.data[CONF_ADDRESS]
    password = entry.data.get(CONF_PASSWORD, DEFAULT_PASSWORD)
    address = address.upper()

    if "filter_reset_timestamp" not in entry.data:
        new_data = {**entry.data, "filter_reset_timestamp": time.time(), "virtual_display_mode": 0}
        hass.config_entries.async_update_entry(entry, data=new_data)

    ble_device = bluetooth.async_ble_device_from_address(hass, address, connectable=False)
    if not ble_device:
        raise ConfigEntryNotReady(f"Prana device {address} not found. Ensure it is powered on.")

    initial_display = entry.data.get("virtual_display_mode", 0)

    def save_display_mode(mode: int):
        """Callback to save display mode memory across HA restarts."""
        new_data = {**entry.data, "virtual_display_mode": mode}
        hass.config_entries.async_update_entry(entry, data=new_data)

    api = PranaBLEDevice(
        ble_device, 
        password, 
        hass=hass, 
        initial_display_mode=initial_display,
        save_display_mode_callback=save_display_mode
    )
    api.auto_restore_display = entry.options.get("auto_restore_display", True)
    
    coordinator = PranaDataUpdateCoordinator(hass, api, entry)
    api._data_update_callback = coordinator._handle_api_data_update
    api._disconnected_callback = coordinator._handle_api_disconnect

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "api": api,
        "coordinator": coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady:
        pass 

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    entry.async_on_unload(coordinator.async_request_shutdown)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = hass.data.get(DOMAIN, {}).get(entry.entry_id, {}).get("coordinator")
    if coordinator:
         await coordinator.async_request_shutdown()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        data = hass.data[DOMAIN].pop(entry.entry_id, None)
        if data:
            await data["api"].stop()
    return unload_ok

async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options/data updates SILENTLY without reloading Bluetooth."""
    data = hass.data[DOMAIN].get(entry.entry_id)
    if data and "api" in data:
        data["api"].auto_restore_display = entry.options.get("auto_restore_display", True)
        LOGGER.debug("Prana config updated quietly. Reload suppressed.")

class PranaDataUpdateCoordinator(DataUpdateCoordinator[Dict[str, Any]]):
    def __init__(self, hass: HomeAssistant, api: PranaBLEDevice, config_entry: ConfigEntry):
        self.api = api
        self.config_entry = config_entry
        self._shutdown = False
        super().__init__(
            hass, LOGGER, name=f"{DOMAIN}-{api.address}",
            update_interval=timedelta(seconds=UPDATE_INTERVAL_SECONDS),
        )

    async def _async_update_data(self) -> Dict[str, Any]:
        try:
            data = await self.api.update_data()
            if not data:
                raise UpdateFailed("No data returned from device")
            return data
        except Exception as err:
            raise UpdateFailed(f"Error communicating with device: {err}") from err

    @callback
    def _handle_api_data_update(self, data: dict):
        self.async_set_updated_data(data)

    @callback
    def _handle_api_disconnect(self):
        if not self._shutdown:
            self.async_update_listeners()

    async def async_request_shutdown(self) -> None:
        if self._shutdown: return
        self._shutdown = True
        await self.api.stop()