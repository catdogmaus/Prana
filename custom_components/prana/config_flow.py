"""Config flow for Prana Integration."""
import asyncio
import logging
from typing import Any, Dict, Optional

import voluptuous as vol
from bleak import BleakClient, BleakError
from bleak.backends.device import BLEDevice

from homeassistant import config_entries, exceptions
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_ble_device_from_address,
    async_discovered_service_info,
)
from homeassistant.const import CONF_ADDRESS, CONF_PASSWORD
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

# Corrected imports from local modules
from .const import (
    DOMAIN,
    DEFAULT_PASSWORD,
    LOGGER, # Use LOGGER from const.py
    UUID_PRANA_SERVICE,
    UUID_RWN_CHARACTERISTIC, # Use the correct constant name
    # UUID_PRANA_WRITE, # Not needed here
    # PRANA_CMD_AUTH, # Not needed here
)
# Import necessary function for command building is NOT needed here
# from .api import _build_frame

# Schema for user step (address selection/entry)
USER_ADDRESS_SCHEMA = vol.Schema(
    {vol.Required(CONF_ADDRESS): str}
)

# Schema for authentication step
AUTH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PASSWORD, default=DEFAULT_PASSWORD): str,
    }
)


# --- Start: Minimal _validate_auth (Connect & Discover Only) ---
async def _validate_auth(hass, address: str, password: str) -> bool:
    """Validate connection and service/characteristic discovery ONLY."""
    # NOTE: This version only checks connection and characteristic existence.
    # It does NOT send any command. Password validity is checked post-setup.
    LOGGER.debug("Attempting validation (connect & discover only) for %s", address)
    ble_device = async_ble_device_from_address(hass, address, connectable=True)
    if not ble_device:
        LOGGER.error("Device not found at address %s", address)
        raise CannotConnect("Device not found")

    # Basic password format check
    if not (isinstance(password, str) and len(password) == 4 and password.isdigit()):
         LOGGER.error("Invalid password format provided: must be 4 digits.")
         raise InvalidAuth("Password must be 4 digits")

    client = BleakClient(ble_device)
    did_connect = False
    try:
        await client.connect(timeout=15.0)
        did_connect = True
        LOGGER.info("Connected for validation. Checking services/characteristics...")

        # Check for service
        service = client.services.get_service(UUID_PRANA_SERVICE)
        if not service:
            LOGGER.error("Prana service %s not found!", UUID_PRANA_SERVICE)
            raise CannotConnect("Required service missing")

        # Check for characteristic
        rwn_char = service.get_characteristic(UUID_RWN_CHARACTERISTIC)
        if not rwn_char:
             LOGGER.error("Prana R/W/Notify characteristic %s not found!", UUID_RWN_CHARACTERISTIC)
             raise CannotConnect("Required characteristic missing")

        LOGGER.info("Service and Characteristic found. Validation PASSED.")
        # Success based only on connect/discovery.
        return True

    except BleakError as err:
        LOGGER.error("BleakError during validation for %s: %s", address, err)
        raise CannotConnect(f"Connection failed: {err}") from err
    except Exception as err:
        LOGGER.error("Unexpected error during validation for %s: %s", address, err, exc_info=True)
        raise CannotConnect(f"Unexpected error: {err}") from err
    finally:
        if did_connect and client.is_connected:
            LOGGER.debug("Disconnecting after validation...")
            await client.disconnect()
        elif did_connect and not client.is_connected:
             LOGGER.debug("Client already disconnected before finally block in validation.")
        else:
             LOGGER.debug("Connection never established during validation.")
        LOGGER.debug("Validation finished for %s", address)
# --- End: Minimal _validate_auth ---


# ... (Rest of PranaConfigFlow class as provided before) ...
class PranaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Prana Integration."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovery_info: Optional[BluetoothServiceInfoBleak] = None
        self._discovered_device: Optional[BLEDevice] = None
        self._discovered_devices: Dict[str, str] = {}
        self._address: Optional[str] = None
        self._password_to_save: Optional[str] = None # To store password between steps

    async def async_step_bluetooth(self, discovery_info: BluetoothServiceInfoBleak) -> FlowResult:
        """Handle the bluetooth discovery step."""
        LOGGER.debug("Discovered Prana device via Bluetooth: %s", discovery_info)
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured(updates={CONF_ADDRESS: discovery_info.address})

        self._discovery_info = discovery_info
        self._address = discovery_info.address
        self.context["title_placeholders"] = {"name": discovery_info.name or discovery_info.address}

        return await self.async_step_authenticate()

    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle the user initiating the flow."""
        if user_input is not None:
             self._address = user_input["address"]
             await self.async_set_unique_id(self._address, raise_on_progress=False)
             self._abort_if_unique_id_configured()

             device_name = self._address
             if self._discovered_devices and self._address in self._discovered_devices:
                 device_name = self._discovered_devices[self._address]
             else:
                 ble_device = async_ble_device_from_address(self.hass, self._address, connectable=True)
                 if ble_device:
                      device_name = ble_device.name or self._address
             self.context["title_placeholders"] = {"name": device_name}

             return await self.async_step_authenticate()

        current_addresses = self._async_current_ids()
        self._discovered_devices.clear()
        for discovery_info in async_discovered_service_info(self.hass, connectable=True):
            address = discovery_info.address
            if address in current_addresses or address in self._discovered_devices:
                continue
            if UUID_PRANA_SERVICE.lower() in [uuid.lower() for uuid in discovery_info.service_uuids]:
                 self._discovered_devices[address] = (discovery_info.name or discovery_info.address)

        if not self._discovered_devices:
             LOGGER.debug("No Prana devices discovered, showing manual address entry form.")
             return self.async_show_form(
                 step_id="user",
                 data_schema=USER_ADDRESS_SCHEMA,
                 errors=None
             )

        LOGGER.debug("Discovered Prana devices: %s", self._discovered_devices)
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_ADDRESS): vol.In(self._discovered_devices)}
            ),
             errors=None
        )

    async def async_step_authenticate(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle the authentication step (collect password)."""
        errors: Dict[str, str] = {}
        if not self._address:
            return self.async_abort(reason="unknown")

        if user_input is not None:
            password = user_input[CONF_PASSWORD]
            try:
                # Attempt the minimal validation (connect & discover only)
                await _validate_auth(self.hass, self._address, password)

                LOGGER.info("Minimal validation successful, creating entry for %s", self._address)

                device_name = self._address
                if self._discovery_info and self._discovery_info.address == self._address:
                     device_name = self._discovery_info.name or self._address
                elif self._discovered_devices and self._address in self._discovered_devices:
                     device_name = self._discovered_devices[self._address]
                else:
                     ble_device = async_ble_device_from_address(self.hass, self._address, connectable=True)
                     if ble_device:
                          device_name = ble_device.name or self._address

                return self.async_create_entry(
                    title=device_name,
                    data={
                        CONF_ADDRESS: self._address,
                        CONF_PASSWORD: password,
                    },
                )

            except CannotConnect as e:
                LOGGER.warning("Cannot connect during minimal validation: %s", e)
                errors["base"] = "cannot_connect"
            except InvalidAuth as e: # Keep for password format check
                LOGGER.warning("Invalid auth during minimal validation: %s", e)
                errors["base"] = "invalid_auth"
            except Exception:
                LOGGER.exception("Unexpected exception during authentication step")
                errors["base"] = "unknown"

        name_placeholder = self.context.get("title_placeholders", {}).get("name", self._address)
        return self.async_show_form(
            step_id="authenticate",
            data_schema=AUTH_SCHEMA,
            description_placeholders={"name": name_placeholder},
            errors=errors,
        )

# Custom Exceptions
class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""

class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""