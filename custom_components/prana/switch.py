"""Switch entities for Prana HASS integration."""
import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import PranaApi
from .const import DOMAIN
from .entity import PranaBaseEntity

_LOGGER = logging.getLogger(__name__)

SWITCH_TYPES: tuple[SwitchEntityDescription, ...] = (
    SwitchEntityDescription(key="power", name="Power", icon="mdi:power"),
    SwitchEntityDescription(key="heating", name="Heating", icon="mdi:heat-wave"),
    SwitchEntityDescription(key="winter_mode", name="Winter Mode", icon="mdi:snowflake-thermometer"),
    SwitchEntityDescription(key="fan_lock", name="Fan Lock", icon="mdi:lock"),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Prana switch entities from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    api: PranaApi = data["api"]
    coordinator = data["coordinator"]
    device_address = entry.data["address"]

    entities = [
        PranaSwitchEntity(coordinator, api, device_address, description)
        for description in SWITCH_TYPES
    ]
    async_add_entities(entities)


class PranaSwitchEntity(PranaBaseEntity, SwitchEntity):
    """Representation of a Prana Switch."""

    def __init__(self, coordinator, api: PranaApi, device_address: str, description: SwitchEntityDescription) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, api, device_address, description.key, description.name)
        self.entity_description = description
        self._attr_name = description.name # Use the descriptive name from entity_description

    @property
    def is_on(self) -> bool | None:
        """Return the state of the switch."""
        if self.coordinator.data and self._entity_key in self.coordinator.data:
            return bool(self.coordinator.data[self._entity_key])
        return None # Unknown

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        _LOGGER.debug("Turning %s ON for %s", self.entity_description.name, self.api.name)
        success = False
        if self.entity_description.key == "power":
            success = await self.api.async_set_power(True)
        elif self.entity_description.key == "heating":
            success = await self.api.async_set_heating(True)
        elif self.entity_description.key == "winter_mode":
            success = await self.api.async_set_winter_mode(True)
        elif self.entity_description.key == "fan_lock":
            success = await self.api.async_set_fan_lock(True)
        
        if success:
            # Optimistically update the state
            if self.coordinator.data:
                self.coordinator.data[self.entity_description.key] = True
            self.async_write_ha_state()
            await self.coordinator.async_request_refresh() # Request a full refresh

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        _LOGGER.debug("Turning %s OFF for %s", self.entity_description.name, self.api.name)
        success = False
        if self.entity_description.key == "power":
            success = await self.api.async_set_power(False)
        elif self.entity_description.key == "heating":
            success = await self.api.async_set_heating(False)
        elif self.entity_description.key == "winter_mode":
            success = await self.api.async_set_winter_mode(False)
        elif self.entity_description.key == "fan_lock":
            success = await self.api.async_set_fan_lock(False)

        if success:
            if self.coordinator.data:
                self.coordinator.data[self.entity_description.key] = False
            self.async_write_ha_state()
            await self.coordinator.async_request_refresh()