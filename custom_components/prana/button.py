"""Button platform for Prana Integration."""
import logging

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, LOGGER
from . import PranaDataUpdateCoordinator 
from .entity import PranaEntity
from .api import PranaBLEDevice

# Button Description
BUTTON_DESCRIPTION = ButtonEntityDescription(
    key="reset_filter",
    name="Reset Filter Timer",
    icon="mdi:filter-remove-outline",
    entity_category=EntityCategory.CONFIG,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Prana buttons based on a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: PranaDataUpdateCoordinator = data["coordinator"]
    api: PranaBLEDevice = data["api"]

    async_add_entities([PranaResetFilterButton(coordinator, api, BUTTON_DESCRIPTION)])


class PranaResetFilterButton(PranaEntity, ButtonEntity):
    """Representation of a Prana reset filter button."""

    def __init__(
        self,
        coordinator: PranaDataUpdateCoordinator,
        api: PranaBLEDevice,
        description: ButtonEntityDescription,
    ) -> None:
        """Initialize the button entity."""
        super().__init__(coordinator, api)
        self.entity_description = description
        self._attr_unique_id = f"{api.address}_{description.key}"


    async def async_press(self) -> None:
        """Handle the button press."""
        LOGGER.debug("Resetting filter timer for %s", self._api.name)
        if await self._api.reset_filter():
            LOGGER.info("Filter reset command sent successfully for %s", self._api.name)
            # Request coordinator refresh to update filter timer sensor
            await self.coordinator.async_request_refresh()
        else:
            LOGGER.error("Failed to send reset filter command for %s", self._api.name)