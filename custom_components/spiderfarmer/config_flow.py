"""Config flow for SpiderFarmer integration."""

from __future__ import annotations

import logging
from typing import Any

import serial
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers import selector

from .const import (
    CONF_BAUDRATE,
    CONF_BUS_NAME,
    CONF_SERIAL_PORT,
    DEFAULT_BAUDRATE,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SERIAL_PORT, default="/dev/ttyUSB0"): selector.TextSelector(),
        vol.Optional(CONF_BAUDRATE, default=DEFAULT_BAUDRATE): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=9600, max=115200, step=1, mode=selector.NumberSelectorMode.BOX
            )
        ),
        vol.Optional(CONF_BUS_NAME, default=""): selector.TextSelector(),
    }
)


def _default_bus_name(port: str) -> str:
    """Derive a human-friendly bus name from the serial port path."""
    return port.rsplit("/", 1)[-1] or port


class SpiderFarmerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SpiderFarmer."""

    VERSION = 2

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            port = user_input[CONF_SERIAL_PORT]
            baudrate = int(user_input[CONF_BAUDRATE])
            bus_name = (user_input.get(CONF_BUS_NAME) or "").strip() or _default_bus_name(port)

            error = await self.hass.async_add_executor_job(
                _test_serial, port, baudrate
            )
            if error:
                errors["base"] = error
            else:
                await self.async_set_unique_id(port)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"SpiderFarmer Bus ({bus_name})",
                    data={
                        CONF_SERIAL_PORT: port,
                        CONF_BAUDRATE: baudrate,
                        CONF_BUS_NAME: bus_name,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )


def _test_serial(port: str, baudrate: int) -> str | None:
    """Try opening the serial port. Returns an error key or None on success."""
    try:
        ser = serial.Serial(
            port=port,
            baudrate=baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.5,
        )
        ser.close()
    except serial.SerialException:
        _LOGGER.exception("Cannot open serial port %s", port)
        return "cannot_connect"
    except Exception:
        _LOGGER.exception("Unexpected error testing serial port %s", port)
        return "unknown"
    return None
