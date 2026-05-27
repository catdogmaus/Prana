"""Sensor platform for Prana Integration."""
import time
from datetime import datetime, timezone
from typing import Optional

from homeassistant.components.sensor import (
    SensorDeviceClass, SensorEntity, SensorEntityDescription, SensorStateClass
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE, SIGNAL_STRENGTH_DECIBELS_MILLIWATT, EntityCategory,
    UnitOfTemperature, CONCENTRATION_PARTS_PER_MILLION, CONCENTRATION_PARTS_PER_BILLION
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.components import bluetooth

from .const import DOMAIN, CONF_MODEL
from . import PranaDataUpdateCoordinator
from .api import PranaBLEDevice
from .entity import PranaEntity 

ALL_SENSORS = [
    SensorEntityDescription(key="temp_in", translation_key="temp_in", device_class=SensorDeviceClass.TEMPERATURE, native_unit_of_measurement=UnitOfTemperature.CELSIUS, state_class=SensorStateClass.MEASUREMENT),
    SensorEntityDescription(key="temp_out", translation_key="temp_out", device_class=SensorDeviceClass.TEMPERATURE, native_unit_of_measurement=UnitOfTemperature.CELSIUS, state_class=SensorStateClass.MEASUREMENT),
    SensorEntityDescription(key="temp_supply", translation_key="temp_supply", device_class=SensorDeviceClass.TEMPERATURE, native_unit_of_measurement=UnitOfTemperature.CELSIUS, state_class=SensorStateClass.MEASUREMENT, entity_registry_enabled_default=False),
    SensorEntityDescription(key="temp_exhaust", translation_key="temp_exhaust", device_class=SensorDeviceClass.TEMPERATURE, native_unit_of_measurement=UnitOfTemperature.CELSIUS, state_class=SensorStateClass.MEASUREMENT, entity_registry_enabled_default=False),
    SensorEntityDescription(key="humidity", translation_key="humidity", device_class=SensorDeviceClass.HUMIDITY, native_unit_of_measurement=PERCENTAGE, state_class=SensorStateClass.MEASUREMENT),
    SensorEntityDescription(key="pressure", translation_key="pressure", icon="mdi:gauge", native_unit_of_measurement="mmHg", state_class=SensorStateClass.MEASUREMENT),
    SensorEntityDescription(key="co2", translation_key="co2", device_class=SensorDeviceClass.CO2, native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION, state_class=SensorStateClass.MEASUREMENT),
    SensorEntityDescription(key="voc", translation_key="voc", device_class=None, icon="mdi:air-filter", native_unit_of_measurement=CONCENTRATION_PARTS_PER_BILLION, state_class=SensorStateClass.MEASUREMENT, suggested_display_precision=0),
    SensorEntityDescription(key="efficiency_pct", translation_key="efficiency_pct", icon="mdi:brightness-percent", native_unit_of_measurement=PERCENTAGE, state_class=SensorStateClass.MEASUREMENT),
    SensorEntityDescription(key="efficiency", translation_key="efficiency", icon="mdi:leaf", device_class=SensorDeviceClass.ENUM, options=["Super", "High", "Good", "Unknown"]),
    SensorEntityDescription(key="speed_in", translation_key="speed_in", icon="mdi:fan-plus", native_unit_of_measurement="lvl", state_class=SensorStateClass.MEASUREMENT),
    SensorEntityDescription(key="speed_out", translation_key="speed_out", icon="mdi:fan-minus", native_unit_of_measurement="lvl", state_class=SensorStateClass.MEASUREMENT),
    SensorEntityDescription(key="winter_mode_active", translation_key="winter_mode_active", icon="mdi:snowflake", entity_category=EntityCategory.DIAGNOSTIC, device_class=SensorDeviceClass.ENUM, options=["on", "off"]),
    SensorEntityDescription(key="rssi", translation_key="rssi", device_class=SensorDeviceClass.SIGNAL_STRENGTH, native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT, state_class=SensorStateClass.MEASUREMENT, entity_category=EntityCategory.DIAGNOSTIC, entity_registry_enabled_default=False),
    
    # Updated to natively support Home Assistant Timestamp Localization
    SensorEntityDescription(
        key="filter_remaining", 
        translation_key="filter_remaining", 
        icon="mdi:filter-variant", 
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC
    ),
]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: PranaDataUpdateCoordinator = data["coordinator"]
    api: PranaBLEDevice = data["api"]
    model = entry.data.get(CONF_MODEL, "Premium Plus")

    active_sensors = []
    for desc in ALL_SENSORS:
        if desc.key in ["co2", "voc", "efficiency", "efficiency_pct"]:
            if model != "Premium Plus": continue
        if desc.key in ["temp_in", "temp_out", "temp_supply", "temp_exhaust", "humidity", "pressure"]:
            if model == "Standard": continue
        active_sensors.append(desc)

    entities = [PranaSensorEntity(coordinator, api, desc) for desc in active_sensors]
    async_add_entities(entities)

class PranaSensorEntity(PranaEntity, SensorEntity):
    def __init__(self, coordinator: PranaDataUpdateCoordinator, api: PranaBLEDevice, description: SensorEntityDescription) -> None:
        super().__init__(coordinator, api)
        self.entity_description = description
        self._attr_unique_id = f"{api.address}_{description.key}"

    @property
    def native_value(self) -> StateType:
        key = self.entity_description.key
        if key == "rssi":
            service_info = bluetooth.async_last_service_info(self.hass, self._api.address, connectable=False)
            return service_info.rssi if service_info else None

        if key == "filter_remaining":
            reset_ts = self.coordinator.config_entry.data.get("filter_reset_timestamp", time.time())
            duration_months = self.coordinator.config_entry.options.get("filter_duration_months", 12)
            
            # Converts the months into days, then to a future UTC timestamp for HA
            expiration_ts = reset_ts + (duration_months * 30.436875 * 86400.0)
            return datetime.fromtimestamp(expiration_ts, tz=timezone.utc)

        if self.coordinator.data and key in self.coordinator.data:
            value = self.coordinator.data.get(key)
            if key in ["winter_mode_active", "auto_mode_active"]:
                 return "on" if value else "off"
            return value
        return None

    @callback
    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()