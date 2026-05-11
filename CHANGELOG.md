# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.1] - 2026-05-11

### Changed

- Bump `spiderwire` requirement from `0.1.0a1` to `0.1.1`.

## [0.1.0] - 2026-05-09

Initial public pre-release of spiderwire Home Assistant integration

### Added

- Home Assistant integration for the SpiderFarmer GSS RS-485 bus over a
  USB-RS485 adapter, with no cloud or app account required.
- Config flow for serial port, baud rate, and a per-bus friendly name;
  multiple busses supported by adding the integration once per adapter.
- `DataUpdateCoordinator` mirroring the OEM hub's tiered polling cadence
  (fast sensors ~1 s, actuators ~2.5 s, slow scan and setpoint
  heartbeat in the background).
- Sensor hub (`0x0A`) entities: air temperature, air humidity, soil
  temperature, VPD, PPFD, and **Light 1** (on/off + brightness, routed
  to the dimmer at `0x04` via blind FC06).
- CO₂ sensor (`0x03`) entity exposing ppm.
- Blower / ventilation (`0x06`) exposed on the `fan` platform with
  0–100 % speed control (`SFBlowerEntity`).
- Per-bus device grouping via `via_device`, so peripherals nest under
  their bus hub in the HA device list.
- HACS metadata (`hacs.json`) and `manifest.json` declaring `pyserial`
  and `spiderwire` as PyPI requirements (no submodule, no manual
  install).
