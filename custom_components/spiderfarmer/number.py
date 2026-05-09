"""Number platform — direct sliders for brightness and blower percent.

The `light` and `fan` entities expose sliders only inside HA's more-info
dialog. The dashboard tile cards default to a plain on/off button, which
is great for quick toggling but hides the underlying analog control.
These number entities give the user a draggable 0-100 slider directly
visible on the device card / dashboard, without losing the on/off
shortcuts.

Wiring follows `docs/device-map.md` and matches the existing entities:

  * Light Brightness → dimmer `0x04` reg 10 (0-100 %), with a blind
    write to reg 16 = 1 to make sure the dimmer is latched. The hub
    gate (`0x0A` reg 18) is intentionally **not** touched here — the
    light entity owns on/off, this entity owns brightness. Setting 0
    via the slider parks the dimmer at 0 % but keeps the gate state
    the user picked.
  * Blower Speed → blower `0x06` reg 14 (0-100 %). The blower has no
    separate enable register; reg 14 = 0 effectively turns it off, so
    the slider doubles as on/off too.

Display value comes straight from the dimmer/blower's own polled
register — same as `gss-ctrl read`. We deliberately don't show an
optimistic "user intent" overlay; the next poll surfaces the new
state.
"""

from __future__ import annotations

import asyncio

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from spiderwire.registers import (
    BLOWER_SETPOINT_REG,
    BlowerData,
    DeviceData,
    FanControllerData,
)

from .coordinator import SpiderFarmerCoordinator
from .entity import (
    peripheral_device_info,
    setup_dynamic_entities,
    suggested_object_id,
    unique_id,
)
from .light import (
    BRIGHTNESS_REG,
    DEFAULT_DIMMER_ADDR,
    DIMMER_ENABLE_REG,
    DIMMER_LATCH_SETTLE_S,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: SpiderFarmerCoordinator = entry.runtime_data

    def _factory(addr: int, device: DeviceData) -> list[NumberEntity]:
        if isinstance(device, FanControllerData):
            return [SFLightBrightnessNumber(coordinator, dimmer_addr=addr)]
        if isinstance(device, BlowerData):
            return [SFBlowerPercentNumber(coordinator, addr=addr)]
        return []

    setup_dynamic_entities(coordinator, entry, async_add_entities, _factory)


class SFLightBrightnessNumber(
    CoordinatorEntity[SpiderFarmerCoordinator], NumberEntity
):
    """Direct 0-100 % brightness slider, attached to the dimmer device."""

    _attr_has_entity_name = True
    _attr_translation_key = "light_brightness"
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_mode = NumberMode.SLIDER

    def __init__(
        self,
        coordinator: SpiderFarmerCoordinator,
        dimmer_addr: int = DEFAULT_DIMMER_ADDR,
    ) -> None:
        super().__init__(coordinator)
        self._dimmer_addr = dimmer_addr
        self._attr_unique_id = unique_id(
            coordinator.entry_id, dimmer_addr, "brightness"
        )
        self._attr_suggested_object_id = suggested_object_id(
            coordinator, "light_brightness"
        )
        self._attr_device_info = peripheral_device_info(coordinator, dimmer_addr)

    @property
    def _dimmer(self) -> FanControllerData | None:
        d = self.coordinator.data.get(self._dimmer_addr)
        return d if isinstance(d, FanControllerData) else None

    @property
    def native_value(self) -> float | None:
        # Read the dimmer's own reg 10 — that's what we actually wrote.
        # The hub's reg 19 readback was attractive ("ground truth") but
        # takes ~13 s to converge, so the slider used to snap back to
        # the stale value for that window after every change.
        d = self._dimmer
        return float(d.brightness_pct) if d else None

    async def async_set_native_value(self, value: float) -> None:
        pct = max(0, min(100, int(round(value))))
        # Same latch dance as the light entity (`light.py`) — without the
        # 50 ms gap reg 10 silently no-ops after a previous off.
        await self.coordinator.async_write_register(
            self._dimmer_addr, DIMMER_ENABLE_REG, 1, wait_for_response=False
        )
        await asyncio.sleep(DIMMER_LATCH_SETTLE_S)
        await self.coordinator.async_write_register(
            self._dimmer_addr, BRIGHTNESS_REG, pct, wait_for_response=False
        )


class SFBlowerPercentNumber(
    CoordinatorEntity[SpiderFarmerCoordinator], NumberEntity
):
    """Direct 0-100 % blower-speed slider, attached to the blower device."""

    _attr_has_entity_name = True
    _attr_translation_key = "blower_percent"
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_mode = NumberMode.SLIDER

    def __init__(self, coordinator: SpiderFarmerCoordinator, addr: int) -> None:
        super().__init__(coordinator)
        self._addr = addr
        self._attr_unique_id = unique_id(coordinator.entry_id, addr, "blower_percent")
        self._attr_suggested_object_id = suggested_object_id(coordinator, "blower_speed")
        self._attr_device_info = peripheral_device_info(coordinator, addr)

    @property
    def _device(self) -> BlowerData | None:
        d = self.coordinator.data.get(self._addr)
        return d if isinstance(d, BlowerData) else None

    @property
    def native_value(self) -> float | None:
        d = self._device
        return float(d.percent) if d else None

    async def async_set_native_value(self, value: float) -> None:
        pct = max(0, min(100, int(round(value))))
        await self.coordinator.async_write_register(
            self._addr, BLOWER_SETPOINT_REG, pct
        )
