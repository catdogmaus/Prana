"""Fan platform for Prana Integration."""
import logging
import math
from typing import Any, Optional

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.percentage import (
    int_states_in_range,
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

from .const import DOMAIN, LOGGER, MODE_MAP, PranaMode
from . import PranaDataUpdateCoordinator 
from .entity import PranaEntity
from .api import PranaBLEDevice

# Define speed range based on ESPHome implementation (seems to be 1-10)
SPEED_RANGE = (1, 10)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Prana fan based on a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: PranaDataUpdateCoordinator = data["coordinator"]
    api: PranaBLEDevice = data["api"]

    async_add_entities([PranaFanEntity(coordinator, api)])


class PranaFanEntity(PranaEntity, FanEntity):
    """Representation of a Prana fan entity."""

    _attr_supported_features = FanEntityFeature.SET_SPEED # Add PRESET_MODE if modes handled here
    _attr_name = None # Use device name as fan name
    _attr_speed_count = int_states_in_range(SPEED_RANGE)


    def __init__(
        self,
        coordinator: PranaDataUpdateCoordinator,
        api: PranaBLEDevice,
    ) -> None:
        """Initialize the fan entity."""
        super().__init__(coordinator, api)
        self._attr_unique_id = f"{api.address}_fan"
        # Set initial state
         # self._handle_coordinator_update()


    @property
    def is_on(self) -> bool | None:
        """Return true if the fan is on."""
        if self.coordinator.data:
            # Fan is on if the main power switch is on
            return self.coordinator.data.get("power")
        return None

    @property
    def percentage(self) -> int | None:
        """Return the current speed percentage."""
        if self.coordinator.data and self.coordinator.data.get("speed") is not None:
            speed = self.coordinator.data.get("speed")
            # Ensure speed is within the expected range before converting
            if SPEED_RANGE[0] <= speed <= SPEED_RANGE[1]:
                 return ranged_value_to_percentage(SPEED_RANGE, speed)
            elif speed == 0: # Treat speed 0 as off? Or lowest percentage?
                 return 0 # Represent as 0%
        return None

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        return int_states_in_range(SPEED_RANGE)

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        if percentage == 0:
            # If setting percentage to 0, turn off the fan
            await self.async_turn_off()
            return

        # Convert percentage to Prana speed value (1-10)
        prana_speed = math.ceil(percentage_to_ranged_value(SPEED_RANGE, percentage))
        # Ensure speed is at least the minimum value when turning on/setting > 0%
        prana_speed = max(SPEED_RANGE[0], prana_speed)

        LOGGER.debug("Setting fan %s speed to %d (%d%%)", self._api.name, prana_speed, percentage)
        if await self._api.set_speed(prana_speed):
            # Optimistically update state
            self._attr_percentage = percentage
            self.async_write_ha_state()
            # Request coordinator refresh to confirm state
            await self.coordinator.async_request_refresh()
        else:
            LOGGER.error("Failed to set speed for %s", self._api.name)

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn the fan on."""
        # If percentage is specified, set it. Otherwise, just turn power on.
        if percentage is not None:
            await self.async_set_percentage(percentage)
        else:
            # Just turn power on, device might resume last speed
            LOGGER.debug("Turning on fan %s (power only)", self._api.name)
            if await self._api.set_power(True):
                 # Optimistically update state
                 self._attr_is_on = True
                 self.async_write_ha_state()
                 # Request coordinator refresh to confirm state
                 await self.coordinator.async_request_refresh()
            else:
                 LOGGER.error("Failed to turn on %s", self._api.name)


    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the fan off."""
        LOGGER.debug("Turning off fan %s (power)", self._api.name)
        if await self._api.set_power(False):
            # Optimistically update state
            self._attr_is_on = False
            self._attr_percentage = 0 # Explicitly set percentage to 0 when off
            self.async_write_ha_state()
            # Request coordinator refresh to confirm state
            await self.coordinator.async_request_refresh()
        else:
            LOGGER.error("Failed to turn off %s", self._api.name)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        is_on_updated = None
        percentage_updated = None
        if self.coordinator.data:
             is_on_updated = self.coordinator.data.get("power")
             speed = self.coordinator.data.get("speed")
             if speed is not None and is_on_updated: # Only calculate percentage if on and speed known
                 if SPEED_RANGE[0] <= speed <= SPEED_RANGE[1]:
                      percentage_updated = ranged_value_to_percentage(SPEED_RANGE, speed)
                 elif speed == 0:
                      percentage_updated = 0 # Or should speed 0 mean something else?
             elif not is_on_updated:
                  percentage_updated = 0 # Set percentage to 0 if power is off

        self._attr_is_on = is_on_updated
        self._attr_percentage = percentage_updated
        self.async_write_ha_state()