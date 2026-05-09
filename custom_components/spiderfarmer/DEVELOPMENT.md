# Spiderfarmer-HA — developer guide

How to hack on the Home Assistant integration (and the
[`spiderwire`](https://github.com/1am/spiderwire) library it depends
on) from a checkout of this repo.

## 1. Prerequisites

- **Python 3.13** (matches HA Core), managed via
  [`uv`](https://docs.astral.sh/uv/).
- A Home Assistant dev instance (Core from source, Container, or HA OS
  with SSH).
- A USB-RS485 adapter wired to the GSS bus.

## 2. Clone the repo and install spiderwire

```bash
git clone https://github.com/1am/spiderfarmer-ha.git
cd spiderfarmer-ha
```

The protocol library
([`spiderwire`](https://pypi.org/project/spiderwire/), source at
[`1am/spiderwire`](https://github.com/1am/spiderwire)) is consumed as
a published package, declared in `manifest.json` `requirements`. Home
Assistant installs it from PyPI on first start — nothing to do for a
plain "use this integration" workflow.

To hack on the library alongside the integration, clone it next to
this repo and install editable into the same virtualenv (or HA Core
checkout) you use for development:

```bash
git clone https://github.com/1am/spiderwire.git
pip install -e ./spiderwire
```

To bump the version this integration pins, edit the `spiderwire`
entry in `custom_components/spiderfarmer/manifest.json` `requirements`
once a new release is published to PyPI.

## 3. Verify the bus from the CLI side

Before touching HA, smoke-test the bus from the SpiderWire CLI in a
separate checkout:

```bash
git clone https://github.com/1am/spiderwire.git
cd spiderwire
make install
make scan PORT=/dev/ttyUSB0
make poll PORT=/dev/ttyUSB0
```

If `scan` finds your devices, the protocol layer is healthy and any
remaining issues are in the HA integration.

## 4. Point Home Assistant at this checkout

The HA way to load a custom integration is to drop it under
`<config>/custom_components/<domain>/`. For development we **symlink**
so edits are live in HA:

### HA Core from source

```bash
ln -s "$(pwd)/custom_components/spiderfarmer" \
      <HA-Core-checkout>/config/custom_components/spiderfarmer
```

### HA Container / Docker

```yaml
# docker-compose.override.yml
services:
  homeassistant:
    volumes:
      - /abs/path/to/spiderfarmer-ha/custom_components/spiderfarmer:/config/custom_components/spiderfarmer:ro
    devices:
      - /dev/ttyUSB0:/dev/ttyUSB0
```

### HA OS / remote Pi

```bash
rsync -avz --delete custom_components/spiderfarmer/ \
      root@homeassistant.local:/config/custom_components/spiderfarmer/
```

The integration imports the library as a top-level package
(`from spiderwire.bus import …`); HA installs it from PyPI on first
start of the integration. For an editable checkout (see step 2),
`pip install -e ./spiderwire` into the same Python environment HA
runs in and the integration will pick up your local edits.

Edits to the library are picked up on HA restart (or on the next
**Reload** for files that don't touch `__init__.py` / `manifest.json` /
`config_flow.py`).

## 5. Enable debug logs

```yaml
# configuration.yaml
logger:
  default: info
  logs:
    custom_components.spiderfarmer: debug
```

Reload without a restart: **Developer Tools → YAML → Reload Logger**.

## 6. Fast iteration loop

1. Edit a file in `custom_components/spiderfarmer/` (integration) or
   in your editable `spiderwire/` checkout (library).
2. **Settings → Devices & Services → SpiderFarmer GSS → ⋮ → Reload**
   (no HA restart needed; keeps state).
3. For `manifest.json` or `config_flow.py` changes, restart HA.

## 7. Submitting changes

- Library changes belong in
  [`1am/spiderwire`](https://github.com/1am/spiderwire). After they
  land and a new release is published to
  [PyPI](https://pypi.org/project/spiderwire/), bump the `spiderwire`
  pin in `custom_components/spiderfarmer/manifest.json` `requirements`
  in this repo.
- Bump `manifest.json` `version` on any user-visible change (HACS uses
  it for update detection).
- Run `ruff check` / `ruff format` if you have ruff installed.
