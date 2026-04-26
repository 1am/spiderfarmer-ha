"""Sensor platform for SpiderFarmer environmental data."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    PERCENTAGE,
    UnitOfPressure,
    UnitOfTemperature,
)

# PPFD uses the horticulture-standard unit "µmol/m²/s" which has no
# built-in Home Assistant constant; supplied as a string.
PPFD_UNIT = "µmol/m²/s"
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .spiderwire.registers import CO2SensorData, DeviceData, SensorHubData

from .coordinator import SpiderFarmerCoordinator
from .entity import (
    peripheral_device_info,
    setup_dynamic_entities,
    suggested_object_id,
    unique_id,
)


@dataclass(frozen=True, kw_only=True)
class SFSensorDescription(SensorEntityDescription):
    value_fn: Callable[[DeviceData], Any]
    exists_fn: Callable[[DeviceData], bool]


SENSOR_HUB_SENSORS: tuple[SFSensorDescription, ...] = (
    SFSensorDescription(
        key="air_temperature",
        translation_key="air_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        value_fn=lambda d: d.air_temp_c if isinstance(d, SensorHubData) else None,
        exists_fn=lambda d: isinstance(d, SensorHubData),
    ),
    SFSensorDescription(
        key="air_humidity",
        translation_key="air_humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=1,
        value_fn=lambda d: d.air_humidity_pct if isinstance(d, SensorHubData) else None,
        exists_fn=lambda d: isinstance(d, SensorHubData),
    ),
    SFSensorDescription(
        key="vpd",
        translation_key="vpd",
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPressure.KPA,
        suggested_display_precision=2,
        value_fn=lambda d: d.vpd_kpa if isinstance(d, SensorHubData) else None,
        exists_fn=lambda d: isinstance(d, SensorHubData),
    ),
    SFSensorDescription(
        key="soil_temperature",
        translation_key="soil_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        value_fn=lambda d: d.soil_temp_c if isinstance(d, SensorHubData) else None,
        exists_fn=lambda d: isinstance(d, SensorHubData),
    ),
    SFSensorDescription(
        key="ppfd",
        translation_key="ppfd",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PPFD_UNIT,
        suggested_display_precision=0,
        value_fn=lambda d: d.ppfd if isinstance(d, SensorHubData) else None,
        exists_fn=lambda d: isinstance(d, SensorHubData),
    ),
)

CO2_SENSORS: tuple[SFSensorDescription, ...] = (
    SFSensorDescription(
        key="co2",
        translation_key="co2",
        device_class=SensorDeviceClass.CO2,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        value_fn=lambda d: d.co2_ppm if isinstance(d, CO2SensorData) else None,
        exists_fn=lambda d: isinstance(d, CO2SensorData),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: SpiderFarmerCoordinator = entry.runtime_data

    def _factory(addr: int, device: DeviceData) -> list[SFSensorEntity]:
        built: list[SFSensorEntity] = []
        for desc in (*SENSOR_HUB_SENSORS, *CO2_SENSORS):
            if desc.exists_fn(device):
                built.append(SFSensorEntity(coordinator, addr, desc))
        return built

    setup_dynamic_entities(coordinator, entry, async_add_entities, _factory)


class SFSensorEntity(CoordinatorEntity[SpiderFarmerCoordinator], SensorEntity):
    """A sensor reading from a SpiderFarmer peripheral."""

    entity_description: SFSensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SpiderFarmerCoordinator,
        addr: int,
        description: SFSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._addr = addr
        self._attr_unique_id = unique_id(coordinator.entry_id, addr, description.key)
        self._attr_suggested_object_id = suggested_object_id(coordinator, description.key)
        self._attr_device_info = peripheral_device_info(coordinator, addr)

    @property
    def available(self) -> bool:
        return super().available and self._addr in self.coordinator.data

    @property
    def native_value(self) -> float | int | None:
        device = self.coordinator.data.get(self._addr)
        if device is None:
            return None
        return self.entity_description.value_fn(device)
