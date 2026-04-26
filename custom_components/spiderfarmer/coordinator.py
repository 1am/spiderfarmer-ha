"""DataUpdateCoordinator that drives the SpiderFarmer bus orchestration.

One HA update = one `BusMaster.tick()`. The tick handles the full OEM
GSS tiered schedule (fast/actuator/scan/heartbeat) via its own internal
deadlines, so HA just needs to tick it at the fast cadence (~1 s).

We also keep a "shadow" of every actuator register the user has written
since startup and re-assert it on the actuator-tier cadence (~2.5 s).
This mirrors what the OEM GSS hub does — it never writes the dimmer
once and walks away, it keeps re-issuing the brightness every few
seconds. Without that, the hub firmware reverts to "ON / 100 %" within
a heartbeat or two (observed: brightness 41 → 100 ~5 s after the
single user write, dimmer reg 16 enable latch presumably resets and
the hub falls back to its boot default).

Beyond the re-assertion shadow we deliberately keep things dumb: write
goes through, polls drive the display, no optimistic overlays. That
matches `gss-ctrl light` / `gss-ctrl blower`, which fire blind FC06
and trust the next poll to surface the new state.
"""

from __future__ import annotations

import logging
import time
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .spiderwire.bus import BusMaster, DEFAULT_ACTUATOR_INTERVAL
from .spiderwire.registers import DeviceData
from .spiderwire.transport import RS485Transport

from .const import CONF_BUS_NAME, CONF_SERIAL_PORT, DEFAULT_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


class SpiderFarmerCoordinator(DataUpdateCoordinator[dict[int, DeviceData]]):
    """Drive the bus via `BusMaster.tick()` and expose typed device data."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        transport: RS485Transport,
    ) -> None:
        bus_name = entry.data.get(CONF_BUS_NAME) or entry.data.get(CONF_SERIAL_PORT, "bus")
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"SpiderFarmer bus ({bus_name})",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.transport = transport
        self.bus = BusMaster(transport=transport)
        self.entry_id = entry.entry_id
        self.bus_name = bus_name
        # Shadow desired-state map keyed by (addr, reg). Populated on
        # every user-driven write; replayed on the actuator-tier
        # cadence so the firmware can't revert behind our backs.
        self._desired: dict[tuple[int, int], tuple[int, bool]] = {}
        self._next_reassert: float = 0.0

    async def _async_update_data(self) -> dict[int, DeviceData]:
        try:
            return await self.hass.async_add_executor_job(self._tick)
        except Exception as err:
            raise UpdateFailed(f"Bus tick failed: {err}") from err

    def _tick(self) -> dict[int, DeviceData]:
        self._reassert_desired_if_due()
        self.bus.tick()
        return dict(self.bus.devices)

    def _reassert_desired_if_due(self) -> None:
        """Re-issue every shadow write on the actuator-tier cadence.

        Order matters for the light: dimmer enable latch (reg 16) must
        fire before brightness (reg 10), and the hub gate (reg 18) goes
        last. The dict's insertion order from `async_write_register`
        already encodes the user's last sequence; we just iterate it.
        """
        if not self._desired:
            return
        now = time.monotonic()
        if now < self._next_reassert:
            return
        for (addr, reg), (value, blind) in self._desired.items():
            try:
                self.transport.write_register(
                    addr, reg, value, wait_for_response=not blind
                )
            except Exception:
                _LOGGER.debug(
                    "Re-assert of 0x%02X reg %d = %d failed (will retry next tick)",
                    addr, reg, value,
                )
        self._next_reassert = now + DEFAULT_ACTUATOR_INTERVAL

    async def async_write_register(
        self,
        addr: int,
        reg: int,
        value: int,
        wait_for_response: bool = True,
    ) -> None:
        """Write a single register and remember it for re-assertion.

        Mirrors what `gss-ctrl light` / `gss-ctrl blower` do: fire the
        FC06, return, let the next poll surface the new state. The
        shadow-map entry keeps `_tick()` re-issuing the write so the
        firmware can't revert (see module docstring); apart from that
        we don't second-guess the polled value.

        `wait_for_response=False` is required for the primary light
        dimmer at `0x04`, which acts on FC06 writes but never echoes
        them (see docs/device-map.md §"0x04 — Light dimmer").
        """
        # Replace any prior value for this register so the shadow map
        # always reflects the user's latest intent (and re-orders to
        # the back, preserving write-sequence semantics on replay).
        self._desired.pop((addr, reg), None)
        self._desired[(addr, reg)] = (value, not wait_for_response)
        await self.hass.async_add_executor_job(
            self._write_register, addr, reg, value, wait_for_response
        )

    def _write_register(
        self, addr: int, reg: int, value: int, wait_for_response: bool
    ) -> None:
        self.transport.write_register(
            addr, reg, value, wait_for_response=wait_for_response
        )
