"""Number platform for Prana Integration."""
import logging
from typing import Optional

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE # Brightness seems to be 0-100
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, LOGGER, MAX_BRIGHTNESS
from . import PranaDataUpdateCoordinator 
from .entity import PranaEntity
from .api import PranaBLEDevice

# Number Description
NUMBER_DESCRIPTION = NumberEntityDescription(
    key="brightness",
    name="Display Brightness",
    icon="mdi:brightness-6",
    native_min_value=0,
    native_max_value=MAX_BRIGHTNESS,
    native_step=1, # Assuming integer steps
    # native_unit_of_measurement=PERCENTAGE, # Use if scale is 0-100
    mode=NumberMode.SLIDER, # Or NumberMode.BOX
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Prana numbers based on a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: PranaDataUpdateCoordinator = data["coordinator"]
    api: PranaBLEDevice = data["api"]

    async_add_entities([PranaBrightnessNumber(coordinator, api, NUMBER_DESCRIPTION)])


class PranaBrightnessNumber(PranaEntity, NumberEntity):
    """Representation of a Prana brightness number entity."""

    def __init__(
        self,
        coordinator: PranaDataUpdateCoordinator,
        api: PranaBLEDevice,
        description: NumberEntityDescription,
    ) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator, api)
        self.entity_description = description
        self._attr_unique_id = f"{api.address}_{description.key}"
        # Set initial state
         # self._handle_coordinator_update()


    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        if self.coordinator.data:
            return self.coordinator.data.get("brightness")
        return None

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        int_value = int(value)
        LOGGER.debug("Setting brightness for %s to %d", self._api.name, int_value)

        if await self._api.set_brightness(int_value):
            # Optimistically update state
            self._attr_native_value = float(int_value) # Store as float consistent with NumberEntity
            self.async_write_ha_state()
            # Request coordinator refresh to confirm state
            await self.coordinator.async_request_refresh()
        else:
            LOGGER.error("Failed to set brightness %d for %s", int_value, self._api.name)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        value = None
        if self.coordinator.data:
             brightness = self.coordinator.data.get("brightness")
             if brightness is not None:
                 value = float(brightness) # Ensure it's a float

        self._attr_native_value = value
        self.async_write_ha_state()