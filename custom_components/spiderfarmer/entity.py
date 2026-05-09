"""Shared entity plumbing for the SpiderFarmer integration.

Everything here exists to make *multiple RS-485 busses* coexist in one
HA instance without colliding. Each config entry = one USB-RS485 adapter
= one bus with its own address space. Two busses commonly have the same
addresses (0x04 lamp dimmer, 0x06 blower, 0x0A sensor hub — those are
the SpiderFarmer defaults on every rig), so we scope every identifier
by the config entry's ID.

Layout in HA's device registry:

    (bus device)   identifiers={("spiderfarmer", entry_id)}
        ├── Sensor Hub   0x0A   air T/RH, soil T, PPFD, VPD
        ├── CO₂ Sensor   0x03   CO₂ ppm
        ├── Light Driver 0x04   Light entity (gates via hub reg 18)
        └── Blower       0x06   Fan entity

Device names come from the *parsed* device class (`_ROLE_NAMES`), not the
firmware-reported `type_major` — every OEM SKU on this rig mis-identifies
itself, see `docs/device-map.md`.

This gives users a clean "bus A / bus B" grouping in the HA UI and keeps
unique-IDs collision-free across entries.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from spiderwire.registers import (
    BlowerData,
    CO2SensorData,
    DeviceData,
    FanControllerData,
    SensorHubData,
)

from .const import DOMAIN
from .coordinator import SpiderFarmerCoordinator


# Map the *parsed* device class (which is wiring-aware via register count)
# to a human-friendly role label. The firmware-reported `type_major` lies on
# this rig — every OEM SKU at 0x03/0x04/0x06 mis-identifies itself (see
# docs/device-map.md) — so we never use `header.type_name` for device naming.
_ROLE_NAMES: dict[type, str] = {
    SensorHubData: "Sensor Hub",
    CO2SensorData: "CO₂ Sensor",
    FanControllerData: "Light Driver",
    BlowerData: "Blower",
}


def bus_identifier(entry_id: str) -> tuple[str, str]:
    """Stable identifier for the per-entry "bus" hub device."""
    return (DOMAIN, entry_id)


def peripheral_identifier(entry_id: str, addr: int) -> tuple[str, str]:
    """Stable identifier for a peripheral on a specific bus."""
    return (DOMAIN, f"{entry_id}:{addr:#04x}")


def unique_id(entry_id: str, addr: int, key: str) -> str:
    """Stable unique_id for an entity on a specific bus.

    `key` disambiguates entities that share a device (e.g. several
    sensors on the same hub).
    """
    return f"sf_{entry_id}_{addr:#04x}_{key}"


def suggested_object_id(coordinator: SpiderFarmerCoordinator, key: str) -> str:
    """Suggest a bus-scoped entity_id slug like `spiderfarmer_bus1_co2`.

    HA only consults this on *first* registration, so existing entities
    keep their current IDs — that's intentional, we don't want to break
    user automations that reference the old slugs.

    The bus name is included so two busses (each with the same SKUs at
    `0x03/0x04/0x06/0x0A`) don't collide on entity_id and trigger HA's
    `_2`/`_3` suffix dance. Slugification is HA's job; we pass the bus
    name as-is and rely on the entity registry to lowercase / replace
    invalid chars.
    """
    return f"spiderfarmer_{coordinator.bus_name}_{key}"


def bus_device_info(coordinator: SpiderFarmerCoordinator) -> DeviceInfo:
    """DeviceInfo for the RS-485 bus itself (one per config entry)."""
    return DeviceInfo(
        identifiers={bus_identifier(coordinator.entry_id)},
        name=f"SpiderFarmer Bus ({coordinator.bus_name})",
        manufacturer="SpiderFarmer",
        model="RS-485 GSS bus",
    )


def peripheral_device_info(
    coordinator: SpiderFarmerCoordinator, addr: int
) -> DeviceInfo:
    """DeviceInfo for a peripheral, grouped under its bus via `via_device`.

    Names are deliberately bare (e.g. "Sensor Hub") — HA already shows the
    parent bus via the `via_device` link, and the manufacturer field carries
    the "SpiderFarmer" branding, so repeating either would just be noise.
    """
    device = coordinator.data.get(addr) if coordinator.data else None
    role = _ROLE_NAMES.get(type(device)) if device else None
    name = role if role else f"Device 0x{addr:02X}"
    return DeviceInfo(
        identifiers={peripheral_identifier(coordinator.entry_id, addr)},
        via_device=bus_identifier(coordinator.entry_id),
        name=name,
        manufacturer="SpiderFarmer",
        model=f"0x{device.header.model_code:04X}" if device else None,
        sw_version=device.header.fw_version if device else None,
    )


# ---------------------------------------------------------------------------
# Dynamic discovery helper
# ---------------------------------------------------------------------------
#
# Devices come and go on the RS-485 bus: the first `tick()` may not catch
# every slave (0x03 in particular often misses the opening burst), and
# users hot-plug peripherals at runtime. Doing entity discovery only inside
# `async_setup_entry` means anything that wasn't on the bus at HA startup
# stays invisible forever — that's why CO₂ "never showed up" on a rig that
# clearly had the sensor responding seconds later. So every platform uses
# this helper to (a) add whatever's currently known and (b) keep watching
# the coordinator and add entities as new addresses appear.


def setup_dynamic_entities(
    coordinator: SpiderFarmerCoordinator,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    factory: Callable[[int, DeviceData], Iterable[Entity] | None],
) -> None:
    """Add entities for each newly-seen address on the bus.

    `factory(addr, device)` returns the entities to register for that
    address (or None / empty to skip). It is called at most once per
    address; once an address has produced entities it is never revisited
    even if the device disappears and reappears (the entities themselves
    track availability via the coordinator).
    """
    seen: set[int] = set()

    def _discover() -> None:
        if not coordinator.data:
            return
        new: list[Entity] = []
        for addr, device in coordinator.data.items():
            if addr in seen:
                continue
            built = factory(addr, device)
            if built is None:
                continue
            built_list = list(built)
            if not built_list:
                continue
            new.extend(built_list)
            seen.add(addr)
        if new:
            async_add_entities(new)

    _discover()
    entry.async_on_unload(coordinator.async_add_listener(_discover))
