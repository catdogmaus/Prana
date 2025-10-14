"""Config flow for Prana HASS integration."""
import logging
import re # For MAC address validation
from typing import Any, Dict, Optional

import voluptuous as vol
# from bleak.backends.device import BLEDevice # Not strictly needed here
# from bleak.exc import BleakError # Not strictly needed here

from homeassistant import config_entries
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.const import CONF_ADDRESS
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.device_registry import format_mac

from .const import (
    DOMAIN,
    SERVICE_UUID,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    MODEL_NAME
)

_LOGGER = logging.getLogger(__name__)


class PranaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Prana HASS."""

    VERSION = 1
    # CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL # Defined in manifest.json is enough

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovery_info: Optional[BluetoothServiceInfoBleak] = None

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> FlowResult:
        """Handle the bluetooth discovery step."""
        _LOGGER.debug("Bluetooth discovery: Found Prana device: %s, %s", discovery_info.name, discovery_info.address)
        await self.async_set_unique_id(format_mac(discovery_info.address))
        self._abort_if_unique_id_configured()

        self._discovery_info = discovery_info
        device_name = discovery_info.name if discovery_info.name else f"{MODEL_NAME} {discovery_info.address[-5:].replace(':', '')}"
        
        self.context["title_placeholders"] = {"name": device_name, "address": discovery_info.address}
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Confirm discovery."""
        if user_input is not None:
            if not self._discovery_info:
                 return self.async_abort(reason="internal_error_no_discovery")
            
            return self.async_create_entry(
                title=self.context["title_placeholders"]["name"], 
                data={CONF_ADDRESS: self._discovery_info.address}
            )

        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders=self.context.get("title_placeholders", {"name": "Unknown Prana Device", "address": "N/A"}),
        )

    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle the user initiated flow (manual MAC address entry)."""
        errors: Dict[str, str] = {}

        if user_input is not None:
            address = user_input[CONF_ADDRESS].strip()
            
            if not re.match(r"^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$", address, re.IGNORECASE) and \
               not re.match(r"^[0-9A-Fa-f]{12}$", address, re.IGNORECASE):
                errors["base"] = "invalid_mac"
            else:
                normalized_mac = format_mac(address)
                await self.async_set_unique_id(normalized_mac, raise_on_progress=False)
                self._abort_if_unique_id_configured(updates={CONF_ADDRESS: normalized_mac})
                
                device_name = f"{MODEL_NAME} {normalized_mac[-5:].replace(':', '')}"
                
                return self.async_create_entry(
                    title=device_name, 
                    data={CONF_ADDRESS: normalized_mac}
                )

        # Prepare dynamic part for the description placeholder
        discovered_prana_devices_info_list = []
        current_configured_addresses = self._async_current_ids()

        try:
            for discovery in async_discovered_service_info(self.hass, connectable=True): # connectable=True helps filter
                if SERVICE_UUID.lower() in [uuid.lower() for uuid in discovery.service_uuids]:
                    if discovery.address not in current_configured_addresses:
                        name = discovery.name if discovery.name else "Unknown Prana"
                        discovered_prana_devices_info_list.append(f"- {name} ({discovery.address})")
        except Exception as e:
            _LOGGER.warning("Error during Bluetooth discovery scan in config flow: %s", e)

        discovered_list_text = ""
        if discovered_prana_devices_info_list:
            discovered_list_text = (
                "\n\n**Discovered Prana devices (you can copy the MAC address from here):**\n" 
                + "\n".join(discovered_prana_devices_info_list)
            )
        else:
            discovered_list_text = (
                "\n\nNo Prana devices were automatically discovered nearby at this moment. "
                "You can still try adding your device if you know its MAC address."
            )
        
        # Use description_placeholders. The actual text will come from strings.json
        # The key "discovered_list_if_any" will be replaced by the value of discovered_list_text
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_ADDRESS, default=""): str
            }),
            errors=errors,
            description_placeholders={"discovered_list_if_any": discovered_list_text}
        )

    @staticmethod
    @config_entries.HANDLERS.register("options")
    async def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return PranaOptionsFlowHandler(config_entry)


class PranaOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Prana options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage Prana options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_SCAN_INTERVAL,
                    default=self.config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                ): vol.All(vol.Coerce(int), vol.Range(min=10, max=3600)),
            }
        )

        return self.async_show_form(step_id="init", data_schema=options_schema)