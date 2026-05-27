"""Config flow for Prana Integration."""
import logging
from typing import Any, Dict, Optional
import voluptuous as vol
from bleak import BleakClient, BleakError
from homeassistant import config_entries, exceptions
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak, async_ble_device_from_address, async_discovered_service_info
)
from homeassistant.const import CONF_ADDRESS, CONF_PASSWORD
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from bleak_retry_connector import establish_connection

from .const import DOMAIN, DEFAULT_PASSWORD, LOGGER, UUID_PRANA_SERVICE, UUID_RWN_CHARACTERISTIC, CONF_MODEL, MODEL_CHOICES

USER_ADDRESS_SCHEMA = vol.Schema({vol.Required(CONF_ADDRESS): str})
AUTH_SCHEMA = vol.Schema({
    vol.Required(CONF_PASSWORD, default=DEFAULT_PASSWORD): str,
    vol.Required(CONF_MODEL, default="Premium Plus"): vol.In(MODEL_CHOICES)
})

async def _validate_connection(hass, address: str) -> bool:
    ble_device = async_ble_device_from_address(hass, address, connectable=False)
    if not ble_device: raise CannotConnect("Device not found")
    client = None
    try:
        client = await establish_connection(BleakClient, ble_device, name=address, disconnected_callback=None, max_attempts=2)
        service = client.services.get_service(UUID_PRANA_SERVICE)
        if not service: raise CannotConnect(f"Required service missing")
        return True
    except BleakError as err:
        raise CannotConnect(f"Connection failed: {err}") from err
    finally:
        if client and client.is_connected:
            await client.disconnect()

class PranaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1
    def __init__(self) -> None:
        self._discovered_devices: Dict[str, str] = {}
        self._address: Optional[str] = None

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return PranaOptionsFlowHandler()

    async def async_step_bluetooth(self, discovery_info: BluetoothServiceInfoBleak) -> FlowResult:
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured(updates={CONF_ADDRESS: discovery_info.address})
        self._address = discovery_info.address
        self.context["title_placeholders"] = {"name": discovery_info.name or discovery_info.address}
        return await self.async_step_authenticate()

    async def async_step_user(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        if user_input is not None:
             self._address = user_input["address"]
             await self.async_set_unique_id(self._address, raise_on_progress=False)
             self._abort_if_unique_id_configured()
             device_name = self._discovered_devices.get(self._address, self._address)
             self.context["title_placeholders"] = {"name": device_name}
             return await self.async_step_authenticate()

        current_addresses = self._async_current_ids()
        self._discovered_devices.clear()
        
        for discovery_info in async_discovered_service_info(self.hass, connectable=False):
            address = discovery_info.address
            if address in current_addresses: continue
            
            name = discovery_info.name or ""
            has_uuid = UUID_PRANA_SERVICE.lower() in [uuid.lower() for uuid in discovery_info.service_uuids]
            
            # --- NEW: Added PRNB to the match rules ---
            has_name = name.startswith("PRNA") or name.startswith("PRNB") or name.startswith("Prana")
            
            if has_uuid or has_name:
                 self._discovered_devices[address] = name or address

        if not self._discovered_devices:
             return self.async_show_form(step_id="user", data_schema=USER_ADDRESS_SCHEMA)

        return self.async_show_form(step_id="user", data_schema=vol.Schema({vol.Required(CONF_ADDRESS): vol.In(self._discovered_devices)}))

    async def async_step_authenticate(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        errors = {}
        if user_input is not None:
            try:
                await _validate_connection(self.hass, self._address)
                return self.async_create_entry(
                    title=self._address, data={
                        CONF_ADDRESS: self._address, 
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                        CONF_MODEL: user_input[CONF_MODEL]
                    }
                )
            except CannotConnect: errors["base"] = "cannot_connect"
            except Exception: errors["base"] = "unknown"

        name = self.context.get("title_placeholders", {}).get("name", self._address)
        return self.async_show_form(step_id="authenticate", data_schema=AUTH_SCHEMA, description_placeholders={"name": name}, errors=errors)

class PranaOptionsFlowHandler(config_entries.OptionsFlow):
    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        default_months = self.config_entry.options.get("filter_duration_months", 12)
        default_restore = self.config_entry.options.get("auto_restore_display", True)
        
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional("filter_duration_months", default=default_months): int,
                vol.Optional("auto_restore_display", default=default_restore): bool
            })
        )

class CannotConnect(exceptions.HomeAssistantError): pass
class InvalidAuth(exceptions.HomeAssistantError): pass