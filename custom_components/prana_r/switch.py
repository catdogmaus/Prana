"""Switch platform for Prana Integration."""
import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, LOGGER
from . import PranaDataUpdateCoordinator 
from .entity import PranaEntity
from .api import PranaBLEDevice

# Switch Description
SWITCH_DESCRIPTION = SwitchEntityDescription(
    key="power",
    name="Power",
    icon="mdi:power",
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Prana switches based on a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: PranaDataUpdateCoordinator = data["coordinator"]
    api: PranaBLEDevice = data["api"]

    async_add_entities([PranaPowerSwitch(coordinator, api, SWITCH_DESCRIPTION)])


class PranaPowerSwitch(PranaEntity, SwitchEntity):
    """Representation of a Prana power switch."""

    def __init__(
        self,
        coordinator: PranaDataUpdateCoordinator,
        api: PranaBLEDevice,
        description: SwitchEntityDescription,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, api)
        self.entity_description = description
        self._attr_unique_id = f"{api.address}_{description.key}"
        # Set initial state
         # self._handle_coordinator_update()


    @property
    def is_on(self) -> bool | None:
        """Return true if the switch is on."""
        if self.coordinator.data:
            return self.coordinator.data.get("power")
        return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        LOGGER.debug("Turning on %s", self._api.name)
        if await self._api.set_power(True):
            # Optimistically update state
            self._attr_is_on = True
            self.async_write_ha_state()
            # Request coordinator refresh to confirm state
            await self.coordinator.async_request_refresh()
        else:
            LOGGER.error("Failed to turn on %s", self._api.name)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        LOGGER.debug("Turning off %s", self._api.name)
        if await self._api.set_power(False):
            # Optimistically update state
            self._attr_is_on = False
            self.async_write_ha_state()
            # Request coordinator refresh to confirm state
            await self.coordinator.async_request_refresh()
        else:
            LOGGER.error("Failed to turn off %s", self._api.name)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.coordinator.data:
             self._attr_is_on = self.coordinator.data.get("power")
        else:
             self._attr_is_on = None
        self.async_write_ha_state()