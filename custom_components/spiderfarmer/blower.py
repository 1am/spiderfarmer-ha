"""Blower / ventilation entity (addr 0x06).

The OEM UI labels this "Light 2" but on every sniffed rig the 0x06 SKU
actually drives the ventilation blower (see
`docs/capture-20260418-1452.sal`): FC06 writes to reg 14 carry the %
directly, reg 12 latches to 1 whenever the blower is running.

Surfaced under HA's fan platform (HA has no dedicated "blower"
primitive); the platform-loader shim in `fan.py` routes setup here.
0x04 is light-only on the current rig and is handled by `light.py`.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .spiderwire.registers import (
    BLOWER_SETPOINT_REG,
    BlowerData,
)

from .coordinator import SpiderFarmerCoordinator
from .entity import (
    peripheral_device_info,
    setup_dynamic_entities,
    suggested_object_id,
    unique_id,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: SpiderFarmerCoordinator = entry.runtime_data

    def _factory(addr: int, device: object) -> list[SFBlowerEntity]:
        if isinstance(device, BlowerData):
            return [SFBlowerEntity(coordinator, addr)]
        return []

    setup_dynamic_entities(coordinator, entry, async_add_entities, _factory)


class SFBlowerEntity(CoordinatorEntity[SpiderFarmerCoordinator], FanEntity):
    """Ventilation blower on a SpiderFarmer hub (addr 0x06, reg 14 = %)."""

    _attr_has_entity_name = True
    _attr_translation_key = "blower"
    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
    )
    _attr_speed_count = 100

    def __init__(self, coordinator: SpiderFarmerCoordinator, addr: int) -> None:
        super().__init__(coordinator)
        self._addr = addr
        self._attr_unique_id = unique_id(coordinator.entry_id, addr, "blower")
        self._attr_suggested_object_id = suggested_object_id(coordinator, "blower")
        self._attr_device_info = peripheral_device_info(coordinator, addr)

    @property
    def _device(self) -> BlowerData | None:
        d = self.coordinator.data.get(self._addr)
        return d if isinstance(d, BlowerData) else None

    @property
    def is_on(self) -> bool | None:
        d = self._device
        return d.running if d else None

    @property
    def percentage(self) -> int | None:
        d = self._device
        return d.percent if d else None

    async def async_set_percentage(self, percentage: int) -> None:
        await self.coordinator.async_write_register(
            self._addr, BLOWER_SETPOINT_REG, int(percentage)
        )

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        pct = percentage if percentage is not None else (
            self._device.percent if self._device and self._device.percent > 0 else 50
        )
        await self.coordinator.async_write_register(
            self._addr, BLOWER_SETPOINT_REG, int(pct)
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_write_register(
            self._addr, BLOWER_SETPOINT_REG, 0
        )
