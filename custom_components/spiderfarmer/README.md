# Spiderfarmer-HA

Local-polling Home Assistant integration for the **SpiderFarmer GSS**
peripheral bus (inline fans, CO₂ sensor, sensor hub, light driver) over
a USB ↔ RS-485 adapter. No cloud, no app account.

The Modbus protocol layer lives in a separate repo,
[`spiderwire`](https://github.com/1am/spiderwire), and is pulled in
here as a **git submodule** at
`custom_components/spiderfarmer/spiderwire/`. The integration imports
it as a relative package (`from .spiderwire.bus import …`); no PyPI
hop, no separate `pip install`.

## Requirements

- Home Assistant **2024.12** or newer (uses `runtime_data` and the
  `config_entry`-aware `DataUpdateCoordinator`).
- A USB-RS485 adapter wired to the GGS bus (A/B + GND), visible in HA
  as `/dev/ttyUSB0` or similar.
- `pyserial>=3.5` — pulled in automatically via `manifest.json`
  `requirements`.

## Install — HACS

1. In HACS → **Integrations → ⋮ → Custom repositories**.
2. Add `https://github.com/1am/spiderfarmer-ha` as category
   **Integration**.
3. Search for *SpiderFarmer GSS* and install.
4. Restart Home Assistant.
5. **Settings → Devices & Services → Add Integration → SpiderFarmer GSS**.

> HACS note: HACS clones the integration without recursing submodules,
> so the released `main` branch ships a vendored copy of `spiderwire/`
> rather than an empty submodule. The submodule pointer is what
> developers see when they clone the repo with `git clone --recurse-submodules`.

## Install — manual

```bash
git clone --recurse-submodules https://github.com/1am/spiderfarmer-ha.git
cp -r spiderfarmer-ha/custom_components/spiderfarmer \
      /path/to/homeassistant/config/custom_components/
```

Restart Home Assistant, then add the integration via **Settings →
Devices & Services → Add Integration → SpiderFarmer GSS**.

## Configuration

You'll be asked for:

| Field | Default | Notes |
| --- | --- | --- |
| Serial port | `/dev/ttyUSB0` | Path to your USB-RS485 adapter |
| Baud rate | `115200` | Stock SpiderFarmer firmware speed |
| Bus name | port basename | Friendly label for this bus (see "Multiple busses" below) |

The integration polls every device on the bus every 5 seconds.

### Multiple busses

Each config entry is one **RS-485 bus** — one USB-RS485 adapter, one
address space. To run more than one bus (e.g. one per grow tent) just
**add the integration again** with a different serial port; you can do
this as many times as you have adapters. Identifiers are scoped per
config entry, so two busses can happily run the default
`0x04 / 0x06 / 0x0A` SpiderFarmer address set without colliding.

Give each bus a distinct **Bus name** (e.g. `tent-veg`, `tent-flower`)
so HA's device list reads

```
SpiderFarmer Bus (tent-veg)
  └─ Sensor hub, Dimmer, Blower, …
SpiderFarmer Bus (tent-flower)
  └─ Sensor hub, Dimmer, Blower, …
```

Per-bus peripherals group under their bus hub via `via_device`.

## What you get

Entities are created automatically for each device discovered on the bus:

- **Sensor hub (0x0A)** – Air temperature, air humidity, soil temperature,
  VPD, PPFD, and **Light 1** (dimmable grow light — on/off + brightness).
  Light 1 writes are routed to the dimmer at `0x04` (blind FC06, the
  dimmer never echoes — see
  [`spiderwire/docs/device-map.md`](https://github.com/1am/spiderwire/blob/main/docs/device-map.md)).
- **CO₂ sensor (0x03)** – CO₂ concentration in ppm.
- **Blower / ventilation (0x06)** – exposed on HA's fan platform with
  0-100 % speed control. The OEM app labels this "Light 2" but the
  0x06 SKU is physically the blower (FC06 → reg 14 carries the %
  directly). HA uses `fan.` as the domain prefix because that's its
  primitive for percentage-controlled rotating devices — the entity
  name is "Blower" and the class is `SFBlowerEntity` in `blower.py`.
- Other addresses are polled silently; extend `sensor.py` / `blower.py`
  / `light.py` as needed to surface new devices.

## Troubleshooting

- **"Cannot open serial port"** – check that the device path is correct
  and that the Home Assistant user can access it (`dialout` group on
  most distros, or pass `--device` to the Docker container).
- **No devices detected** – verify wiring (A/B swapped is the #1 cause)
  and baud rate. You can test outside HA with
  [`gss-ctrl`](https://github.com/1am/spiderwire) from the SpiderWire
  repo: `gss-ctrl /dev/ttyUSB0 scan -v`.
- **Bus errors / partial data** – the coordinator keeps the last good
  reading for up to 3 consecutive failures per device before marking it
  offline. Check HA logs under the `custom_components.spiderfarmer`
  logger.

## Development

This repo's `custom_components/spiderfarmer/spiderwire/` is a git
submodule pointing at [`1am/spiderwire`](https://github.com/1am/spiderwire).
Clone with submodules to hack on both at once:

```bash
git clone --recurse-submodules https://github.com/1am/spiderfarmer-ha.git
# or, if you already cloned:
git submodule update --init --recursive
```

See [`DEVELOPMENT.md`](DEVELOPMENT.md) for symlinking this checkout
into a dev HA instance, enabling debug logs, and the
edit-reload-iterate loop.
