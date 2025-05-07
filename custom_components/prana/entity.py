"""Base entity for Prana Integration."""
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from . import PranaDataUpdateCoordinator 
from .api import PranaBLEDevice

class PranaEntity(CoordinatorEntity[PranaDataUpdateCoordinator]):
    """Base class for Prana entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: PranaDataUpdateCoordinator, api: PranaBLEDevice) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._api = api
        self._address = api.address
        # Set device information
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._address)},
            name=api.name,
            manufacturer="Prana", # Assuming manufacturer
            # model= "Specify model if detectable"
            # sw_version= "Specify sw version if detectable"
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        # Available if the coordinator successfully connected and has data,
        # and the specific data point exists.
        return (
            super().available
            and self.coordinator.last_update_success
            and self.coordinator.data is not None
        )