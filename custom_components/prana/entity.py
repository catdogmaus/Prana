"""Base entity for Prana HASS integration."""
import logging
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.core import callback

from .api import PranaApi
from .const import DOMAIN, UPDATE_SIGNAL, MODEL_NAME

_LOGGER = logging.getLogger(__name__)


class PranaBaseEntity(CoordinatorEntity):
    """Base class for Prana entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, api: PranaApi, device_address: str, entity_key: str, name_suffix: str) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.api = api
        self._device_address = device_address
        self._entity_key = entity_key

        # --- FIX: Create a simple, stable Unique ID based ONLY on the MAC address and key ---
        self._attr_unique_id = f"{device_address}_{entity_key}"
        _LOGGER.debug("Entity %s (%s) initialized with stable unique_id: %s", name_suffix, entity_key, self._attr_unique_id)

        # Device info for linking entities to a device
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_address)},
            name=api.name,  # Use the friendly API name for the device grouping
            manufacturer="Prana",
            model=MODEL_NAME,
        )

        # The friendly name of the entity can still be descriptive
        if hasattr(self, 'entity_description') and self.entity_description and self.entity_description.name:
             self._attr_name = self.entity_description.name
        else:
             self._attr_name = name_suffix

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        # Let the coordinator handle availability based on update success.
        # Add a check for the API being connected for commands to be responsive.
        return super().available and self.api.is_connected()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        instance_specific_signal_to_listen = f"{UPDATE_SIGNAL}_{self.api.name}"
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                instance_specific_signal_to_listen,
                self._handle_api_update
            )
        )

    @property
    def _entity_data(self):
        """Shortcut to the specific data for this entity from parsed status."""
        if self.coordinator.data and isinstance(self.coordinator.data, dict):
            return self.coordinator.data.get(self._entity_key)
        return None

    @callback
    def _handle_api_update(self, parsed_status: dict | None) -> None:
        """Handle updates pushed directly from the API (e.g., on disconnect)."""
        # This callback's primary job is to make the entity unavailable faster
        # than the coordinator poll if the device disconnects unexpectedly.
        if self.available != self.api.is_connected():
            self.async_write_ha_state()