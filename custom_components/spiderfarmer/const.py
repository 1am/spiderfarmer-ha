"""Constants for the SpiderFarmer integration."""

DOMAIN = "spiderfarmer"

CONF_SERIAL_PORT = "serial_port"
CONF_BAUDRATE = "baudrate"
CONF_BUS_NAME = "bus_name"

DEFAULT_BAUDRATE = 115200
# Fast-tier cycle (0x03 + 0x0A) runs every update. The BusMaster's own
# deadlines handle the actuator/scan/heartbeat tiers internally, matching
# the OEM hub's ~1 s / 2.5 s / 7 s / 3.5 s schedule.
DEFAULT_SCAN_INTERVAL = 1  # seconds
