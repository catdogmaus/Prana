"""Fan platform for Prana Integration."""
import math
from typing import Any
from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.percentage import int_states_in_range, percentage_to_ranged_value, ranged_value_to_percentage

from .const import DOMAIN, LOGGER
from . import PranaDataUpdateCoordinator
from .entity import PranaEntity
from .api import PranaBLEDevice

SPEED_RANGE = (1, 10)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: PranaDataUpdateCoordinator = data["coordinator"]
    api: PranaBLEDevice = data["api"]
    async_add_entities([PranaFanEntity(coordinator, api)])

class PranaFanEntity(PranaEntity, FanEntity):
    _attr_supported_features = (FanEntityFeature.SET_SPEED | FanEntityFeature.TURN_ON | FanEntityFeature.TURN_OFF)
    _attr_translation_key = "prana_power" 
    _attr_speed_count = int_states_in_range(SPEED_RANGE)

    def __init__(self, coordinator: PranaDataUpdateCoordinator, api: PranaBLEDevice) -> None:
        super().__init__(coordinator, api)
        self._attr_unique_id = f"{api.address}_fan"

    @property
    def is_on(self) -> bool | None:
        if self.coordinator.data: return self.coordinator.data.get("power")
        return None

    @property
    def percentage(self) -> int | None:
        if self.coordinator.data and self.coordinator.data.get("speed") is not None:
            speed = self.coordinator.data.get("speed")
            if isinstance(speed, int) and SPEED_RANGE[0] <= speed <= SPEED_RANGE[1]:
                 return ranged_value_to_percentage(SPEED_RANGE, speed)
            elif speed == 0: return 0
        return None

    async def async_set_percentage(self, percentage: int) -> None:
        if percentage == 0:
            await self.async_turn_off()
            return
        prana_speed = math.ceil(percentage_to_ranged_value(SPEED_RANGE, percentage))
        prana_speed = max(SPEED_RANGE[0], prana_speed)
        
        if await self._api.set_speed(prana_speed):
            self._attr_percentage = percentage
            self.async_write_ha_state()
            await self.coordinator.async_request_refresh()

    async def async_turn_on(self, percentage: int | None = None, preset_mode: str | None = None, **kwargs: Any) -> None:
        if percentage is not None:
            await self.async_set_percentage(percentage)
        else:
            if await self._api.set_power(True):
                 self._attr_is_on = True
                 self.async_write_ha_state()
                 await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        if await self._api.set_power(False):
            self._attr_is_on = False
            self._attr_percentage = 0
            self.async_write_ha_state()
            await self.coordinator.async_request_refresh()

    @callback
    def _handle_coordinator_update(self) -> None:
        is_on_updated = None
        percentage_updated = None
        if self.coordinator.data:
             is_on_updated = self.coordinator.data.get("power")
             speed = self.coordinator.data.get("speed")
             if speed is not None and is_on_updated and isinstance(speed, int):
                 if SPEED_RANGE[0] <= speed <= SPEED_RANGE[1]:
                      percentage_updated = ranged_value_to_percentage(SPEED_RANGE, speed)
                 elif speed == 0: percentage_updated = 0
             elif not is_on_updated:
                  percentage_updated = 0

        self._attr_is_on = is_on_updated
        self._attr_percentage = percentage_updated
        self.async_write_ha_state()