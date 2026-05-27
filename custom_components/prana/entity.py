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
        super().__init__(coordinator)
        self._api = api
        self._address = api.address
        
        # Clean up the device name
        clean_name = api.name
        if clean_name and clean_name.startswith("PRNAQaq"):
            clean_name = clean_name.replace("PRNAQaq", "").strip()
            if not clean_name:
                clean_name = "Prana Recuperator"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._address)},
            name=clean_name,
            manufacturer="Prana",
            model="V2 Recuperator",
        )

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.last_update_success