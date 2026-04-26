#!/usr/bin/env bash
# Deploy the spiderfarmer custom_component to a Home Assistant instance over SSH.
#
# `custom_components/spiderfarmer/spiderwire/` is a git submodule. As long as
# it is checked out locally (`git submodule update --init --recursive`), we
# just rsync the whole integration tree — HA imports whatever files are on
# disk, it does not fetch submodules itself.
#
# Configuration (env vars, all have sensible defaults):
#   HA_HOST    SSH target, e.g. root@homeassistant.local   [root@10.10.10.10]
#   HA_PORT    SSH port                                    [22]
#   HA_CONFIG  HA config dir on the host                   [/homeassistant]
#   RESTART    if "1", run `ha core restart` after deploy  [0]

set -euo pipefail

HA_HOST="${HA_HOST:-root@10.10.10.10}"
HA_PORT="${HA_PORT:-22}"
HA_CONFIG="${HA_CONFIG:-/homeassistant}"
RESTART="${RESTART:-0}"

HA_DEST="${HA_CONFIG}/custom_components/spiderfarmer"
SSH=(ssh -p "${HA_PORT}" "${HA_HOST}")

# Run from repo root (this script lives in <repo>/scripts/).
cd "$(dirname "$0")/.."

if [ ! -d custom_components/spiderfarmer ]; then
  echo "error: custom_components/spiderfarmer/ not found (run from spiderfarmer-ha repo)" >&2
  exit 1
fi

# spiderwire/ is a submodule — refuse to deploy an empty one, otherwise HA
# would silently fail to import `from .spiderwire.bus import …`.
if [ ! -f custom_components/spiderfarmer/spiderwire/bus.py ]; then
  echo "error: custom_components/spiderfarmer/spiderwire/ is missing or empty." >&2
  echo "       Run: git submodule update --init --recursive" >&2
  exit 1
fi

echo ">>> Deploying spiderfarmer integration to ${HA_HOST}:${HA_DEST}"

"${SSH[@]}" "mkdir -p '${HA_DEST}'"

rsync -avz --delete \
  --exclude '__pycache__' --exclude '*.pyc' --exclude '.mypy_cache' \
  --exclude '.git' --exclude '.git/' \
  -e "ssh -p ${HA_PORT}" \
  custom_components/spiderfarmer/ \
  "${HA_HOST}:${HA_DEST}/"

# Sanity check: the integration must have its key files on the host,
# otherwise HA won't load it.
echo ">>> Verifying installation on host"
"${SSH[@]}" bash -s <<EOF
set -euo pipefail
test -f '${HA_DEST}/__init__.py'        || { echo 'missing __init__.py' >&2; exit 1; }
test -f '${HA_DEST}/manifest.json'      || { echo 'missing manifest.json' >&2; exit 1; }
test -f '${HA_DEST}/spiderwire/bus.py'  || { echo 'missing spiderwire/bus.py' >&2; exit 1; }
echo "    OK: \$(grep -E '"version"' '${HA_DEST}/manifest.json')"
EOF

if [ "${RESTART}" = "1" ] || [ "${RESTART}" = "true" ]; then
  echo ">>> Restarting Home Assistant Core"
  "${SSH[@]}" 'ha core restart'
fi

echo ">>> Done."
