"""Select platform for Prana Integration."""
from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, LOGGER, PranaMode, PranaDisplayMode, CONF_MODEL
from . import PranaDataUpdateCoordinator
from .entity import PranaEntity
from .api import PranaBLEDevice

MODE_MAP = {
    PranaMode.MANUAL: "Manual",
    PranaMode.AUTO: "Auto",
    PranaMode.AUTO_PLUS: "Auto+",
}
MODE_NAME_TO_ENUM = {v: k for k, v in MODE_MAP.items()}

DISPLAY_MODE_MAP = {
    PranaDisplayMode.FAN: "Fan State",
    PranaDisplayMode.TEMP_IN: "Temp Inside",
    PranaDisplayMode.TEMP_OUT: "Temp Outside",
    PranaDisplayMode.CO2: "CO2",
    PranaDisplayMode.VOC: "VOC",
    PranaDisplayMode.HUMIDITY: "Humidity",
    PranaDisplayMode.AIR_QUALITY: "Efficiency", 
    PranaDisplayMode.PRESSURE: "Pressure",
}
DISPLAY_MODE_NAME_TO_ENUM = {v: k for k, v in DISPLAY_MODE_MAP.items()}

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: PranaDataUpdateCoordinator = data["coordinator"]
    api: PranaBLEDevice = data["api"]
    model = entry.data.get(CONF_MODEL, "Premium Plus")

    mode_options = ["Manual"]
    if model in ["Premium", "Premium Plus"]: mode_options.append("Auto")
    if model == "Premium Plus": mode_options.append("Auto+")

    display_options = ["Fan State"]
    if model in ["Premium", "Premium Plus"]:
        display_options.extend(["Temp Inside", "Temp Outside", "Humidity", "Pressure"])
    if model == "Premium Plus":
        display_options.extend(["CO2", "VOC", "Efficiency"])

    active_selects = []
    if model != "Standard":
        active_selects.append(SelectEntityDescription(key="mode", translation_key="mode", icon="mdi:cog-outline", options=mode_options))
        active_selects.append(SelectEntityDescription(key="display_mode", translation_key="display_mode", icon="mdi:monitor-dashboard", options=display_options))

    entities = [PranaSelect(coordinator, api, desc) for desc in active_selects]
    async_add_entities(entities)

class PranaSelect(PranaEntity, SelectEntity):
    def __init__(self, coordinator: PranaDataUpdateCoordinator, api: PranaBLEDevice, description: SelectEntityDescription) -> None:
        super().__init__(coordinator, api)
        self.entity_description = description
        self._attr_unique_id = f"{api.address}_{description.key}"

    @property
    def current_option(self) -> str | None:
        if self.coordinator.data:
            return self.coordinator.data.get(self.entity_description.key)
        return None

    async def async_select_option(self, option: str) -> None:
        if self.entity_description.key == "mode" and option in MODE_NAME_TO_ENUM:
            await self._api.set_mode(MODE_NAME_TO_ENUM[option])
        elif self.entity_description.key == "display_mode" and option in DISPLAY_MODE_NAME_TO_ENUM:
            await self._api.set_display_mode(DISPLAY_MODE_NAME_TO_ENUM[option])
            
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    @callback
    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()