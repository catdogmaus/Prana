"""Fan entity for Prana HASS integration."""
import logging
import math
from typing import Any, Optional

from homeassistant.components.fan import (
    FanEntity,
    FanEntityDescription,
    FanEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.percentage import (
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

from .api import PranaApi
from .const import DOMAIN, FAN_SPEED_COUNT
from .entity import PranaBaseEntity

_LOGGER = logging.getLogger(__name__)

# Using a single fan entity to control both Inlet/Outlet fans together
# as per ESPHome's "In/Out fans" behavior.
FAN_DESCRIPTION = FanEntityDescription(
    key="combined_fan", # Internal key
    name="Fan",        # This will be prefixed by device name by PranaBaseEntity
    icon="mdi:fan",
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Prana fan entities from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    api: PranaApi = data["api"]
    coordinator = data["coordinator"]
    device_address = entry.data["address"]

    entities = [PranaFanEntity(coordinator, api, device_address, FAN_DESCRIPTION)]
    async_add_entities(entities)


class PranaFanEntity(PranaBaseEntity, FanEntity):
    """Representation of a Prana Fan."""

    _attr_supported_features = FanEntityFeature.SET_SPEED
    _speed_range = (1, FAN_SPEED_COUNT)  # Min speed 1, Max speed 10

    def __init__(self, coordinator, api: PranaApi, device_address: str, description: FanEntityDescription) -> None:
        """Initialize the fan."""
        # The key for fan state is 'current_speed' and 'power' from parsed data.
        # We use description.key for unique_id and entity_key for PranaBaseEntity.
        super().__init__(coordinator, api, device_address, description.key, description.name)
        self.entity_description = description
        self._attr_name = description.name # Use the descriptive name

    @property
    def is_on(self) -> bool | None:
        """Return true if the fan is on."""
        if self.coordinator.data:
            power_on = self.coordinator.data.get("power", False)
            # Fan is on if main power is on AND speed is > 0
            # Or, if main power is on and any of the fan sub-switches (inlet/outlet) are on.
            # ESPHome implies fan is on if speed > 0 and main power is on.
            current_speed = self.coordinator.data.get("current_speed", 0)
            return bool(power_on and current_speed > 0)
        return None

    @property
    def percentage(self) -> Optional[int]:
        """Return the current speed percentage."""
        if self.coordinator.data and self.is_on: # Only return percentage if on
            current_speed = self.coordinator.data.get("current_speed")
            if current_speed is not None and current_speed > 0:
                return ranged_value_to_percentage(self._speed_range, current_speed)
        return 0 # Off or unknown speed

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        return FAN_SPEED_COUNT

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed of the fan."""
        if percentage == 0:
            await self.async_turn_off()
            return

        # Ensure main power is on before setting speed
        if not self.api.get_parsed_status().get("power", False):
            _LOGGER.info("%s: Main power is off, turning it on before setting fan speed.", self.api.name)
            if not await self.api.async_set_power(True):
                _LOGGER.error("%s: Failed to turn on main power for fan.", self.api.name)
                return
            await self.coordinator.async_request_refresh() # Refresh to get power state
            await asyncio.sleep(0.5) # Give time for power on to reflect

        speed_value = math.ceil(percentage_to_ranged_value(self._speed_range, percentage))
        _LOGGER.debug("%s: Setting fan speed to %d (percentage %d)", self.api.name, speed_value, percentage)
        
        if await self.api.async_set_fan_speed(speed_value):
            if self.coordinator.data:
                 self.coordinator.data["current_speed"] = speed_value # Optimistic
            self.async_write_ha_state()
            await self.coordinator.async_request_refresh()


    async def async_turn_on(
        self,
        percentage: Optional[int] = None,
        preset_mode: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan."""
        # Ensure main power is on
        if not self.api.get_parsed_status().get("power", False):
            _LOGGER.info("%s: Main power is off, turning it on for fan.", self.api.name)
            if not await self.api.async_set_power(True):
                _LOGGER.error("%s: Failed to turn on main power for fan.", self.api.name)
                return
            # Optimistically update power state or wait for refresh
            if self.coordinator.data: self.coordinator.data["power"] = True
            self.async_write_ha_state()
            await self.coordinator.async_request_refresh()
            await asyncio.sleep(0.5) # Give time for power on


        if await self.api.async_turn_fan_on_off(True): # Send generic "fan on"
            # If percentage is provided, set it. Otherwise, fan turns on to last/default speed.
            if percentage is not None:
                await self.async_set_percentage(percentage)
            else: # If no speed given, turn on to speed 1 or last known speed if >0
                current_api_speed = self.api.get_parsed_status().get("current_speed", 0)
                if current_api_speed == 0:
                    await self.async_set_percentage(ranged_value_to_percentage(self._speed_range, 1)) # Default to speed 1
                else: # Already on at some speed, ensure HA state reflects this
                    if self.coordinator.data: self.coordinator.data["current_speed"] = current_api_speed
                    self.async_write_ha_state()

            await self.coordinator.async_request_refresh()


    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the fan off."""
        if await self.api.async_turn_fan_on_off(False):
            if self.coordinator.data:
                 self.coordinator.data["current_speed"] = 0 # Optimistic
            self.async_write_ha_state()
            await self.coordinator.async_request_refresh()