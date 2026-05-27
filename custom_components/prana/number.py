"""Number platform for Prana Integration."""
from homeassistant.components.number import NumberEntity, NumberEntityDescription, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.const import EntityCategory

from .const import DOMAIN
from . import PranaDataUpdateCoordinator
from .entity import PranaEntity
from .api import PranaBLEDevice

NUMBER_DESCRIPTIONS = (
    NumberEntityDescription(key="brightness", translation_key="brightness", icon="mdi:brightness-6", native_min_value=1, native_max_value=6, native_step=1, mode=NumberMode.SLIDER, entity_category=EntityCategory.CONFIG),
    NumberEntityDescription(key="speed_in", translation_key="speed_in", icon="mdi:fan-plus", native_min_value=1, native_max_value=10, native_step=1, mode=NumberMode.SLIDER),
    NumberEntityDescription(key="speed_out", translation_key="speed_out", icon="mdi:fan-minus", native_min_value=1, native_max_value=10, native_step=1, mode=NumberMode.SLIDER),
)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: PranaDataUpdateCoordinator = data["coordinator"]
    api: PranaBLEDevice = data["api"]
    entities = [PranaNumber(coordinator, api, desc) for desc in NUMBER_DESCRIPTIONS]
    async_add_entities(entities)

class PranaNumber(PranaEntity, NumberEntity):
    def __init__(self, coordinator: PranaDataUpdateCoordinator, api: PranaBLEDevice, description: NumberEntityDescription) -> None:
        super().__init__(coordinator, api)
        self.entity_description = description
        self._attr_unique_id = f"{api.address}_{description.key}"

    @property
    def native_value(self) -> float | None:
        if self.coordinator.data:
            return self.coordinator.data.get(self.entity_description.key)
        return None

    async def async_set_native_value(self, value: float) -> None:
        int_value = int(value)
        key = self.entity_description.key
        
        success = False
        if key == "brightness":
            success = await self._api.set_brightness(int_value)
        elif key == "speed_in":
            success = await self._api.set_speed(int_value, target="in")
        elif key == "speed_out":
            success = await self._api.set_speed(int_value, target="out")

        if success:
            self._attr_native_value = float(int_value)
            self.async_write_ha_state()
            await self.coordinator.async_request_refresh()

    @callback
    def _handle_coordinator_update(self) -> None:
        if self.coordinator.data:
             val = self.coordinator.data.get(self.entity_description.key)
             if val is not None:
                 self._attr_native_value = float(val)
        self.async_write_ha_state()