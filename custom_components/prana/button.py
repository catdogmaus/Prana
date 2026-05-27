"""Button platform for Prana Integration."""
import time
from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, LOGGER
from . import PranaDataUpdateCoordinator
from .entity import PranaEntity
from .api import PranaBLEDevice

BUTTON_DESCRIPTIONS = (
    ButtonEntityDescription(
        key="reset_filter", 
        translation_key="reset_filter", 
        icon="mdi:filter-remove-outline", 
        entity_category=EntityCategory.CONFIG
    ),
)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: PranaDataUpdateCoordinator = data["coordinator"]
    api: PranaBLEDevice = data["api"]
    entities = [PranaButton(coordinator, api, desc) for desc in BUTTON_DESCRIPTIONS]
    async_add_entities(entities)

class PranaButton(PranaEntity, ButtonEntity):
    def __init__(self, coordinator: PranaDataUpdateCoordinator, api: PranaBLEDevice, description: ButtonEntityDescription) -> None:
        super().__init__(coordinator, api)
        self.entity_description = description
        self._attr_unique_id = f"{api.address}_{description.key}"

    async def async_press(self) -> None:
        key = self.entity_description.key
        
        if key == "reset_filter":
            LOGGER.info("Resetting filter timer memory for %s", self._api.name)
            new_data = {**self.coordinator.config_entry.data, "filter_reset_timestamp": time.time()}
            self.hass.config_entries.async_update_entry(self.coordinator.config_entry, data=new_data)
            await self.coordinator.async_request_refresh()