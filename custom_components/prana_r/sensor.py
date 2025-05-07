"""Sensor platform for Prana Integration."""
from typing import Optional

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfTemperature,
    CONCENTRATION_PARTS_PER_MILLION,
    # --- Start: Import Fix ---
    # TIME_DAYS is no longer directly in const
    UnitOfTime, # Import the Enum instead
    # --- End: Import Fix ---
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

# Import bluetooth helper from HA
from homeassistant.components import bluetooth

from .const import DOMAIN
from . import PranaDataUpdateCoordinator 
from .entity import PranaEntity
from .api import PranaBLEDevice

# Sensor descriptions
SENSOR_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="temp_in",
        name="Indoor Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="temp_out",
        name="Outdoor Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
     SensorEntityDescription(
        key="temp_exhaust",
        name="Exhaust Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
     SensorEntityDescription(
        key="temp_supply",
        name="Supply Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="humidity",
        name="Humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="co2",
        name="CO2",
        device_class=SensorDeviceClass.CO2,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
     SensorEntityDescription(
        key="voc",
        name="VOC",
        device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    SensorEntityDescription(
        key="filter_timer_days",
        name="Filter Remaining Time",
        icon="mdi:filter-variant",
        # --- Start: Import Fix ---
        native_unit_of_measurement=UnitOfTime.DAYS, # Use Enum member
        # --- End: Import Fix ---
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
     SensorEntityDescription(
        key="winter_mode_active",
        name="Winter Mode Active",
        icon="mdi:snowflake",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENUM,
        options=["on", "off"],
     ),
      SensorEntityDescription(
        key="auto_mode_active",
        name="Auto Mode Active",
        icon="mdi:cogs",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENUM,
        options=["on", "off"],
     ),
    SensorEntityDescription(
        key="rssi",
        name="Signal Strength",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Prana sensors based on a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: PranaDataUpdateCoordinator = data["coordinator"]
    api: PranaBLEDevice = data["api"]

    entities = [
        PranaSensorEntity(coordinator, api, description)
        for description in SENSOR_DESCRIPTIONS
        # Add sensors only if the key exists in the initial data? Optional.
        # if coordinator.data and description.key in coordinator.data
    ]

    # Add RSSI sensor separately as it comes from bluetooth stack
    # rssi_entity = PranaSensorEntity(coordinator, api, next(d for d in SENSOR_DESCRIPTIONS if d.key == "rssi"))
    # entities.append(rssi_entity) # Simpler to handle RSSI within the class directly

    async_add_entities(entities)


class PranaSensorEntity(PranaEntity, SensorEntity):
    """Representation of a Prana sensor."""

    def __init__(
        self,
        coordinator: PranaDataUpdateCoordinator,
        api: PranaBLEDevice,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, api)
        self.entity_description = description
        self._attr_unique_id = f"{api.address}_{description.key}"
        # Set initial state
         # self._handle_coordinator_update() # Call this to set initial value

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        # Handle RSSI separately
        if self.entity_description.key == "rssi":
            service_info = bluetooth.async_last_service_info(self.hass, self._api.address, connectable=True)
            return service_info.rssi if service_info else None

        # Handle other sensors based on coordinator data
        if self.coordinator.data and self.entity_description.key in self.coordinator.data:
            value = self.coordinator.data.get(self.entity_description.key)

            # Handle boolean sensors mapped to ENUM device class
            if self.entity_description.key in ["winter_mode_active", "auto_mode_active"]:
                 return "on" if value else "off"

            # Return parsed value, could be None if parsing failed or key missing
            return value

        # Return None if no data or key missing
        return None

    # Override _handle_coordinator_update to set the internal state correctly
    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Update RSSI if this is the RSSI sensor
        if self.entity_description.key == "rssi":
            service_info = bluetooth.async_last_service_info(self.hass, self._api.address, connectable=True)
            self._attr_native_value = service_info.rssi if service_info else None
        # Update other sensors from coordinator data
        elif self.coordinator.data and self.entity_description.key in self.coordinator.data:
             value = self.coordinator.data.get(self.entity_description.key)
             # Handle boolean sensors mapped to ENUM device class
             if self.entity_description.key in ["winter_mode_active", "auto_mode_active"]:
                  self._attr_native_value = "on" if value else "off"
             else:
                  self._attr_native_value = value
        else:
             # No data for this sensor in the coordinator update
             self._attr_native_value = None

        # Mark the state as updated
        self.async_write_ha_state()