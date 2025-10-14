"""Sensor entities for Prana HASS integration."""
import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfPressure,
    UnitOfTemperature,
    CONCENTRATION_PARTS_PER_BILLION,
    CONCENTRATION_PARTS_PER_MILLION,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import PranaApi
from .const import DOMAIN
from .entity import PranaBaseEntity

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="temp_inlet_before",
        name="Temperature Outside Inlet",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="temp_outlet_before",
        name="Temperature Inside Outlet",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="temp_inlet_after",
        name="Temperature Inside Inlet",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="temp_outlet_after",
        name="Temperature Outside Outlet",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="humidity",
        name="Humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="co2",
        name="CO2",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        device_class=SensorDeviceClass.CO2,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="voc",
        name="VOC",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_BILLION,
        device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS_PARTS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="pressure",
        name="Pressure",
        native_unit_of_measurement=UnitOfPressure.MMHG,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Prana sensor entities from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    api: PranaApi = data["api"]
    coordinator = data["coordinator"]
    device_address = entry.data["address"]

    entities = [
        PranaSensorEntity(coordinator, api, device_address, description)
        for description in SENSOR_TYPES
    ]
    async_add_entities(entities)


class PranaSensorEntity(PranaBaseEntity, SensorEntity):
    """Representation of a Prana Sensor."""

    def __init__(self, coordinator, api: PranaApi, device_address: str, description: SensorEntityDescription) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, api, device_address, description.key, description.name)
        self.entity_description = description
        # No need to set self._attr_name here, PranaBaseEntity handles it

    @property
    def native_value(self) -> float | int | None:
        """Return the state of the sensor."""
        if self.coordinator.data and self._entity_key in self.coordinator.data:
            value = self.coordinator.data[self._entity_key]
            
            # --- FIX for TypeError ---
            # If the value from the parser is None, return None immediately.
            if value is None:
                return None
            
            # This logic is now safe because `value` is guaranteed not to be None.
            try:
                # Check if it's already a number (int or float)
                if isinstance(value, (int, float)):
                    return value
                # If not, attempt to convert from string representation
                return float(value) if '.' in str(value) else int(value)
            except (ValueError, TypeError):
                _LOGGER.warning("Could not parse sensor value for %s: %s", self.entity_id, value)
                return None
        return None