# Spiderfarmer-HA — developer guide

How to hack on the Home Assistant integration (and the
[`spiderwire`](https://github.com/1am/spiderwire) library it bundles)
from a checkout of this repo.

## 1. Prerequisites

- **Python 3.13** (matches HA Core), managed via
  [`uv`](https://docs.astral.sh/uv/).
- A Home Assistant dev instance (Core from source, Container, or HA OS
  with SSH).
- A USB-RS485 adapter wired to the GSS bus.

## 2. Clone with submodules

```bash
git clone --recurse-submodules https://github.com/1am/spiderfarmer-ha.git
cd spiderfarmer-ha
```

The protocol library lives at
`custom_components/spiderfarmer/spiderwire/` as a git submodule
pointing at [`1am/spiderwire`](https://github.com/1am/spiderwire). If
you already cloned without `--recurse-submodules`:

```bash
git submodule update --init --recursive
```

To pick up upstream library changes:

```bash
git submodule update --remote custom_components/spiderfarmer/spiderwire
git add custom_components/spiderfarmer/spiderwire
git commit -m 'Bump spiderwire'
```

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

The integration imports the library via relative imports
(`from .spiderwire.bus import …`). No separate pip install is needed —
HA picks `spiderwire/` up as part of the custom component because the
submodule clones it into the integration's own directory.

Edits to `spiderwire/` are picked up on HA restart (or on the next
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
   `custom_components/spiderfarmer/spiderwire/` (library).
2. **Settings → Devices & Services → SpiderFarmer GSS → ⋮ → Reload**
   (no HA restart needed; keeps state).
3. For `manifest.json` or `config_flow.py` changes, restart HA.

## 7. Submitting changes

- Library changes (`spiderwire/`) must be committed and pushed to
  [`1am/spiderwire`](https://github.com/1am/spiderwire) first; this
  repo only stores the submodule pointer.
- Bump `manifest.json` `version` on any user-visible change (HACS uses
  it for update detection).
- Run `ruff check` / `ruff format` if you have ruff installed.
