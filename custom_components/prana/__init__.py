"""The Prana HASS integration."""
import asyncio
import logging
from datetime import timedelta

from bleak import BleakClient
from bleak.exc import BleakError
from bleak_retry_connector import establish_connection

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import PranaApi
from .const import (
    CONF_SCAN_INTERVAL,
    DOMAIN,
    PLATFORMS,
    MODEL_NAME
)

_LOGGER = logging.getLogger(__name__)

SHORT_UPDATE_INTERVAL = 20 # seconds

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Prana HASS from a config entry."""
    address = entry.data[CONF_ADDRESS]

    ble_device = bluetooth.async_ble_device_from_address(hass, address.upper(), connectable=True)
    if not ble_device:
        raise ConfigEntryNotReady(f"Could not find BLE device with address {address}")
    
    api_name = entry.title
    prana_api = PranaApi(hass, ble_device, api_name)
    
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = { "api": prana_api }

    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, SHORT_UPDATE_INTERVAL)
    _LOGGER.debug("Using scan interval: %s seconds", scan_interval)

    async def async_update_data() -> dict | None:
        """Fetch data from API using bleak-retry-connector."""
        _LOGGER.debug("Coordinator: Polling data for %s", prana_api.name)
        try:
            if not prana_api.is_connected():
                _LOGGER.info("%s is not connected. Establishing connection...", prana_api.name)
                client = await establish_connection(
                    client_class=BleakClient,
                    device=prana_api.ble_device,
                    name=prana_api.name,
                    disconnected_callback=prana_api.handle_disconnect,
                    max_attempts=2
                )
                return await prana_api.update_after_connect(client)
            else:
                _LOGGER.debug("%s is already connected. Sending status poll.", prana_api.name)
                return await prana_api.async_get_status()
        except Exception as err:
            _LOGGER.warning("Error fetching Prana data: %s", err)
            await prana_api.disconnect()
            raise UpdateFailed(f"Error communicating with Prana device: {err}") from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=prana_api.name,
        update_method=async_update_data,
        update_interval=timedelta(seconds=scan_interval),
    )
    
    hass.data[DOMAIN][entry.entry_id]["coordinator"] = coordinator

    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    @callback
    def _async_options_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
        hass.async_create_task(hass.config_entries.async_reload(entry.entry_id))

    async def _async_shutdown(event: Event) -> None:
        await prana_api.disconnect()

    entry.async_on_unload(entry.add_update_listener(_async_options_update_listener))
    entry.async_on_unload(hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_shutdown))
    entry.async_on_unload(prana_api.disconnect)

    _LOGGER.info("Prana entry %s setup complete.", entry.entry_id)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.info("Unloading Prana entry %s", entry.entry_id)
    if entry.entry_id in hass.data.get(DOMAIN, {}):
        api: PranaApi = hass.data[DOMAIN][entry.entry_id]["api"]
        await api.disconnect()
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok and entry.entry_id in hass.data.get(DOMAIN, {}):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok