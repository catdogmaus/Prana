"""Number entity for Prana HASS integration (Display Brightness)."""
import logging
from typing import Any

from homeassistant.components.number import NumberEntity, NumberEntityDescription, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import PranaApi
from .const import DOMAIN
from .entity import PranaBaseEntity

_LOGGER = logging.getLogger(__name__)

BRIGHTNESS_DESCRIPTION = NumberEntityDescription(
    key="brightness",
    name="Display Brightness",
    icon="mdi:television-ambient-light",
    native_min_value=0,  # 0 usually means off
    native_max_value=10,
    native_step=1,
    mode=NumberMode.SLIDER, # Or NumberMode.BOX
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Prana number entities from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    api: PranaApi = data["api"]
    coordinator = data["coordinator"]
    device_address = entry.data["address"]

    entities = [PranaNumberEntity(coordinator, api, device_address, BRIGHTNESS_DESCRIPTION)]
    async_add_entities(entities)


class PranaNumberEntity(PranaBaseEntity, NumberEntity):
    """Representation of a Prana Number entity (specifically for brightness)."""

    def __init__(self, coordinator, api: PranaApi, device_address: str, description: NumberEntityDescription) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator, api, device_address, description.key, description.name)
        self.entity_description = description
        self._attr_name = description.name


    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        if self.coordinator.data and self._entity_key in self.coordinator.data:
            return float(self.coordinator.data[self._entity_key])
        return None

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        target_value = int(value)
        _LOGGER.debug("%s: Setting %s to %d", self.api.name, self.entity_description.key, target_value)

        success = False
        if self.entity_description.key == "brightness":
            success = await self.api.async_set_brightness(target_value)
        
        if success:
            if self.coordinator.data:
                 self.coordinator.data[self.entity_description.key] = target_value # Optimistic
            self.async_write_ha_state()
            await self.coordinator.async_request_refresh()