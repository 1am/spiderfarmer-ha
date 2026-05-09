"""SpiderFarmer integration — local RS-485 Modbus control of GGS peripherals.

Each config entry represents *one* RS-485 bus (one USB-RS485 adapter,
one ESPHome gateway, …). Multiple entries coexist: identifiers and
unique-IDs are scoped by `entry.entry_id`, peripherals are grouped under
a per-entry "bus hub" device via `via_device`. See `entity.py`.
"""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er

from spiderwire.transport import RS485Transport

from .const import CONF_BAUDRATE, CONF_BUS_NAME, CONF_SERIAL_PORT, DOMAIN
from .coordinator import SpiderFarmerCoordinator
from .entity import bus_device_info

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.FAN,
    Platform.LIGHT,
    Platform.NUMBER,
]

type SpiderFarmerConfigEntry = ConfigEntry[SpiderFarmerCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: SpiderFarmerConfigEntry) -> bool:
    port = entry.data[CONF_SERIAL_PORT]
    baudrate = entry.data[CONF_BAUDRATE]

    transport = await hass.async_add_executor_job(RS485Transport, port, baudrate)
    coordinator = SpiderFarmerCoordinator(hass, entry, transport)
    try:
        await coordinator.async_config_entry_first_refresh()
    except BaseException:
        # If the first refresh raises (ConfigEntryNotReady etc.), HA never
        # calls async_unload_entry, so close the serial port ourselves —
        # otherwise the next setup attempt fails with "device or resource busy".
        await hass.async_add_executor_job(transport.close)
        raise

    # Register the per-entry "bus" hub device so peripherals have
    # something to attach to via `via_device` even before their first
    # poll succeeds.
    dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        **bus_device_info(coordinator),
    )

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SpiderFarmerConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator: SpiderFarmerCoordinator = entry.runtime_data
        await hass.async_add_executor_job(coordinator.transport.close)
    return unload_ok


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate pre-multibus installs (v1) to the bus-scoped schema (v2).

    v1 used globally-shared identifiers (`("spiderfarmer", "0x04")`) and
    unique-IDs (`sf_0x04_light1`), which collide the moment a user adds
    a second bus. v2 prefixes both with the config entry ID so multiple
    busses can coexist. We rewrite the entity + device registries in
    place so existing installs keep their history / customisations.
    """
    if entry.version >= 2:
        return True

    _LOGGER.info("Migrating SpiderFarmer entry %s to v2 (multi-bus scoping)", entry.entry_id)

    ent_reg = er.async_get(hass)

    @callback
    def _update_unique_id(
        reg_entry: er.RegistryEntry,
    ) -> dict[str, str] | None:
        old = reg_entry.unique_id
        if old.startswith("sf_") and not old.startswith(f"sf_{entry.entry_id}_"):
            new = f"sf_{entry.entry_id}_{old[len('sf_'):]}"
            return {"new_unique_id": new}
        return None

    await er.async_migrate_entries(hass, entry.entry_id, _update_unique_id)

    dev_reg = dr.async_get(hass)
    for device in list(dev_reg.devices.values()):
        if entry.entry_id not in device.config_entries:
            continue
        new_ids = set()
        changed = False
        for domain, ident in device.identifiers:
            if domain == DOMAIN and ":" not in ident and not ident.startswith(entry.entry_id):
                new_ids.add((domain, f"{entry.entry_id}:{ident}"))
                changed = True
            else:
                new_ids.add((domain, ident))
        if changed:
            dev_reg.async_update_device(device.id, new_identifiers=new_ids)

    # Backfill CONF_BUS_NAME if the user never had the chance to set it.
    if CONF_BUS_NAME not in entry.data:
        port = entry.data.get(CONF_SERIAL_PORT, "bus")
        bus_name = port.rsplit("/", 1)[-1] or port
        hass.config_entries.async_update_entry(
            entry,
            data={**entry.data, CONF_BUS_NAME: bus_name},
            version=2,
        )
    else:
        hass.config_entries.async_update_entry(entry, version=2)

    return True
