"""Select entities for Prana HASS integration."""
import logging
from typing import List, Optional

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import PranaApi
from .const import DOMAIN, DISPLAY_MODE_OPTIONS, FAN_MODE_OPTIONS
from .entity import PranaBaseEntity

_LOGGER = logging.getLogger(__name__)

SELECT_TYPES: tuple[SelectEntityDescription, ...] = (
    SelectEntityDescription(
        key="display_mode",
        name="Display Mode",
        icon="mdi:unfold-more-vertical", # Or mdi:television-guide
        options=DISPLAY_MODE_OPTIONS,
    ),
    SelectEntityDescription(
        key="fan_mode",
        name="Fan Mode",
        icon="mdi:fan-auto",
        options=FAN_MODE_OPTIONS,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Prana select entities from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    api: PranaApi = data["api"]
    coordinator = data["coordinator"]
    device_address = entry.data["address"]

    entities = [
        PranaSelectEntity(coordinator, api, device_address, description)
        for description in SELECT_TYPES
    ]
    async_add_entities(entities)


class PranaSelectEntity(PranaBaseEntity, SelectEntity):
    """Representation of a Prana Select entity."""

    def __init__(self, coordinator, api: PranaApi, device_address: str, description: SelectEntityDescription) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator, api, device_address, description.key, description.name)
        self.entity_description = description
        self._attr_name = description.name
        self._attr_options = description.options # type: ignore

    @property
    def current_option(self) -> Optional[str]:
        """Return the currently selected option."""
        if self.coordinator.data and self._entity_key in self.coordinator.data:
            value_index = self.coordinator.data[self._entity_key]
            if 0 <= value_index < len(self.options):
                return self.options[value_index]
        return None

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        if option not in self.options:
            _LOGGER.warning("Invalid option %s for %s", option, self.entity_id)
            return

        option_index = self.options.index(option)
        _LOGGER.debug(
            "%s: Selecting option %s (index %d) for %s",
            self.api.name, option, option_index, self.entity_description.key
        )

        success = await self.api.async_set_select_option(self.entity_description.key, option_index)
        
        if success:
            if self.coordinator.data:
                 self.coordinator.data[self.entity_description.key] = option_index # Optimistic
            self.async_write_ha_state()
            await self.coordinator.async_request_refresh()