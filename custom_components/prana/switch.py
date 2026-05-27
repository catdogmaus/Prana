"""Switch platform for Prana Integration."""
from typing import Any
from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.const import EntityCategory

from .const import DOMAIN
from . import PranaDataUpdateCoordinator
from .entity import PranaEntity
from .api import PranaBLEDevice

SWITCH_DESCRIPTIONS = (
    SwitchEntityDescription(key="heating_on", translation_key="heating_on", icon="mdi:heating-coil"),
    SwitchEntityDescription(key="winter_mode_active", translation_key="winter_mode_active", icon="mdi:snowflake"),
    SwitchEntityDescription(key="fans_locked", translation_key="fans_locked", icon="mdi:lock"),
    SwitchEntityDescription(key="bt_polling", translation_key="bt_polling", icon="mdi:bluetooth", entity_category=EntityCategory.CONFIG),
)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: PranaDataUpdateCoordinator = data["coordinator"]
    api: PranaBLEDevice = data["api"]
    entities = [PranaToggleSwitch(coordinator, api, desc) for desc in SWITCH_DESCRIPTIONS]
    async_add_entities(entities)

class PranaToggleSwitch(PranaEntity, SwitchEntity):
    def __init__(self, coordinator: PranaDataUpdateCoordinator, api: PranaBLEDevice, description: SwitchEntityDescription) -> None:
        super().__init__(coordinator, api)
        self.entity_description = description
        self._attr_unique_id = f"{api.address}_{description.key}"

    @property
    def is_on(self) -> bool | None:
        if self.entity_description.key == "bt_polling":
            return self._api.polling_enabled
        if self.coordinator.data:
            return self.coordinator.data.get(self.entity_description.key)
        return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        key = self.entity_description.key
        if key == "bt_polling":
            await self._api.set_polling(True)
            self.async_write_ha_state()
            await self.coordinator.async_request_refresh()
            return
            
        success = False
        if key == "heating_on": success = await self._api.toggle_heating(True)
        elif key == "winter_mode_active": success = await self._api.toggle_winter_mode(True)
        elif key == "fans_locked": success = await self._api.toggle_fans_locked(True)
        
        if success:
            self._attr_is_on = True
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        key = self.entity_description.key
        if key == "bt_polling":
            await self._api.set_polling(False)
            self.async_write_ha_state()
            return
            
        success = False
        if key == "heating_on": success = await self._api.toggle_heating(False)
        elif key == "winter_mode_active": success = await self._api.toggle_winter_mode(False)
        elif key == "fans_locked": success = await self._api.toggle_fans_locked(False)
        
        if success:
            self._attr_is_on = False
            self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        if self.entity_description.key != "bt_polling":
            if self.coordinator.data:
                 self._attr_is_on = self.coordinator.data.get(self.entity_description.key)
        self.async_write_ha_state()