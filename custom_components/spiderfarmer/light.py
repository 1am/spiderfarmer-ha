"""Light platform — the main grow-light fixture (Light 1).

State on the sensor hub (`0x0A` regs 18/19), brightness setpoint on the
dimmer (`0x04` reg 10, 0-100 %). Both targets accept FC06 but neither
echoes on this firmware — verified by `gss-ctrl light` timing out
identically against the hub before we switched to blind writes — so all
three writes (hub enable, dimmer enable, dimmer brightness) are fired
blind. The next coordinator poll surfaces the new state.

The OEM-UI "Light 2" label actually refers to the blower at `0x06`; that
lives in `blower.py` (surfaced on HA's fan platform), not here. See
`docs/device-map.md` §0x06 and `docs/capture-20260418-1452.sal` for the
wire-level proof.
"""

from __future__ import annotations

import asyncio
from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ColorMode,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from spiderwire.registers import FanControllerData, SensorHubData

from .coordinator import SpiderFarmerCoordinator
from .entity import peripheral_device_info, suggested_object_id, unique_id

HUB_ENABLE_REG = 18
DIMMER_ENABLE_REG = 16
BRIGHTNESS_REG = 10

DEFAULT_DIMMER_ADDR = 0x04
DEFAULT_HUB_ADDR = 0x0A

# The dimmer needs ~50 ms to latch reg 16 before reg 10 takes effect;
# without it the brightness write silently no-ops and the light stays
# at 0 after a previous turn-off (matches the gss-ctrl CLI fix).
DIMMER_LATCH_SETTLE_S = 0.05


def _pct_to_ha(pct: int) -> int:
    return round(pct * 255 / 100)


def _ha_to_pct(ha_brightness: int) -> int:
    return max(1, min(100, round(ha_brightness * 100 / 255)))


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add Light 1 once *both* the sensor hub and the dimmer have been seen.

    The hub holds the on/off gate (reg 18) and the dimmer holds brightness
    (reg 10). If either is missing on the first poll, defer creation until
    the coordinator picks the second one up — same pattern as the other
    platforms, just with a two-address precondition instead of one.
    """
    coordinator: SpiderFarmerCoordinator = entry.runtime_data
    added = False

    def _discover() -> None:
        nonlocal added
        if added or not coordinator.data:
            return
        has_hub = any(
            isinstance(d, SensorHubData) for d in coordinator.data.values()
        )
        has_dimmer = any(
            isinstance(d, FanControllerData) for d in coordinator.data.values()
        )
        if has_hub and has_dimmer:
            async_add_entities([SFLight1Entity(coordinator)])
            added = True

    _discover()
    entry.async_on_unload(coordinator.async_add_listener(_discover))


class SFLight1Entity(CoordinatorEntity[SpiderFarmerCoordinator], LightEntity):
    """Light 1: brightness on the dimmer (`0x04`), enable gate on the hub (`0x0A`).

    Surfaced under the dimmer device — that's the SKU the user wires to a
    fixture and recognises as "the light". The hub stays a sensor-only
    device; we only borrow its reg 18 enable flag and reg 19 reported value.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "light"
    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}

    def __init__(
        self,
        coordinator: SpiderFarmerCoordinator,
        hub_addr: int = DEFAULT_HUB_ADDR,
        dimmer_addr: int = DEFAULT_DIMMER_ADDR,
    ) -> None:
        super().__init__(coordinator)
        self._hub_addr = hub_addr
        self._dimmer_addr = dimmer_addr
        # Keep the legacy hub-scoped unique_id so existing installs don't
        # orphan their entity; only the device assignment moves.
        self._attr_unique_id = unique_id(coordinator.entry_id, hub_addr, "light1")
        self._attr_suggested_object_id = suggested_object_id(coordinator, "light")
        self._attr_device_info = peripheral_device_info(coordinator, dimmer_addr)

    @property
    def _hub(self) -> SensorHubData | None:
        d = self.coordinator.data.get(self._hub_addr)
        return d if isinstance(d, SensorHubData) else None

    @property
    def _dimmer(self) -> FanControllerData | None:
        d = self.coordinator.data.get(self._dimmer_addr)
        return d if isinstance(d, FanControllerData) else None

    @property
    def is_on(self) -> bool | None:
        h = self._hub
        return h.light_enabled if h else None

    @property
    def brightness(self) -> int | None:
        # Read the dimmer's own reg 10 — the hub's reg 19 readback
        # takes ~13 s to converge, which is what made the displayed
        # brightness "jump" right after a slider change.
        d = self._dimmer
        return _pct_to_ha(d.brightness_pct) if d else None

    async def async_turn_on(self, **kwargs: Any) -> None:
        if ATTR_BRIGHTNESS in kwargs:
            pct = _ha_to_pct(kwargs[ATTR_BRIGHTNESS])
        else:
            current = self._dimmer.brightness_pct if self._dimmer else 0
            # Fall back to full brightness if the dimmer is parked at 0 —
            # otherwise the user toggles "on" and gets an invisible 1 %.
            pct = current if current > 0 else 100
        # Same sequence as `gss-ctrl light`: dimmer enable + brightness
        # first, hub gate last. Otherwise the light flashes the previous
        # brightness for a frame and after a turn-off (reg 10 = 0) it
        # sometimes never lights up at all.
        await self.coordinator.async_write_register(
            self._dimmer_addr, DIMMER_ENABLE_REG, 1, wait_for_response=False
        )
        await asyncio.sleep(DIMMER_LATCH_SETTLE_S)
        await self.coordinator.async_write_register(
            self._dimmer_addr, BRIGHTNESS_REG, pct, wait_for_response=False
        )
        await self.coordinator.async_write_register(
            self._hub_addr, HUB_ENABLE_REG, 1, wait_for_response=False
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_write_register(
            self._hub_addr, HUB_ENABLE_REG, 0, wait_for_response=False
        )
        await self.coordinator.async_write_register(
            self._dimmer_addr, BRIGHTNESS_REG, 0, wait_for_response=False
        )
