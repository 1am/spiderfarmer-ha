"""Home Assistant fan-platform entry point.

HA loads platforms by filename (this file must be named `fan.py` for
`Platform.FAN` to resolve), but HA's fan platform is really just its
generic "rotating thing with a percentage" primitive. SpiderFarmer's
devices that map onto it live in their own modules:

* ``blower.py`` — ``SFBlowerEntity`` for the ventilation blower at
  ``0x06`` (OEM UI calls it "Light 2"; reg 14 = %).
* ``fan.py`` (future) — when a real duct fan appears on the bus, add an
  ``SFFanEntity`` in a new ``fan_entity.py`` and wire it up from this
  setup callback. Unique IDs (``sf_<addr>_blower`` vs
  ``sf_<addr>_fan``) keep the two from colliding.
"""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .blower import async_setup_entry as _setup_blower


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Fan-platform setup: surface every SpiderFarmer device that maps to HA's fan primitive."""
    await _setup_blower(hass, entry, async_add_entities)
    # Future: await _setup_fan(hass, entry, async_add_entities)
