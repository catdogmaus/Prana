"""Select platform for Prana Integration."""
import logging
from typing import Optional

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, LOGGER, MODE_MAP, MODE_LIST, PranaMode
from . import PranaDataUpdateCoordinator 
from .entity import PranaEntity
from .api import PranaBLEDevice

# Select Description
SELECT_DESCRIPTION = SelectEntityDescription(
    key="mode",
    name="Mode",
    icon="mdi:cog-outline", # Or mdi:air-filter ?
    options=MODE_LIST, # Use the list of friendly names
)

# Reverse map for friendly name to enum
MODE_NAME_TO_ENUM = {v: k for k, v in MODE_MAP.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Prana selects based on a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: PranaDataUpdateCoordinator = data["coordinator"]
    api: PranaBLEDevice = data["api"]

    async_add_entities([PranaModeSelect(coordinator, api, SELECT_DESCRIPTION)])


class PranaModeSelect(PranaEntity, SelectEntity):
    """Representation of a Prana mode select entity."""

    def __init__(
        self,
        coordinator: PranaDataUpdateCoordinator,
        api: PranaBLEDevice,
        description: SelectEntityDescription,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator, api)
        self.entity_description = description
        self._attr_unique_id = f"{api.address}_{description.key}"
        # Set initial state
         # self._handle_coordinator_update()


    @property
    def current_option(self) -> str | None:
        """Return the currently selected option."""
        if self.coordinator.data:
            mode_enum_name = self.coordinator.data.get("mode") # This should be the enum name string
            if mode_enum_name:
                try:
                    mode_enum = PranaMode[mode_enum_name]
                    return MODE_MAP.get(mode_enum) # Convert enum back to friendly name
                except KeyError:
                    LOGGER.warning("Unknown mode enum name in state: %s", mode_enum_name)
                    return None
        return None

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        if option not in MODE_NAME_TO_ENUM:
            LOGGER.error("Invalid mode selected: %s", option)
            return

        target_mode_enum = MODE_NAME_TO_ENUM[option]
        LOGGER.debug("Setting mode for %s to %s (%s)", self._api.name, option, target_mode_enum)

        if await self._api.set_mode(target_mode_enum):
            # Optimistically update state
            self._attr_current_option = option
            self.async_write_ha_state()
            # Request coordinator refresh to confirm state
            await self.coordinator.async_request_refresh()
        else:
            LOGGER.error("Failed to set mode %s for %s", option, self._api.name)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        option = None
        if self.coordinator.data:
             mode_enum_name = self.coordinator.data.get("mode")
             if mode_enum_name:
                try:
                    mode_enum = PranaMode[mode_enum_name]
                    option = MODE_MAP.get(mode_enum)
                except KeyError:
                    option = None # Keep it None if unknown mode received

        self._attr_current_option = option
        self.async_write_ha_state()