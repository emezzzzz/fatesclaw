#!/usr/bin/env bash
set -euo pipefail

log() {
  printf '[verify-controls] %s\n' "$*"
}

log "Kernel input devices"
cat /proc/bus/input/devices || true

log "Detected Fates-style devices"
grep -E 'Name="soc:knob|Name="keys"' -A3 /proc/bus/input/devices || true

if command -v evtest >/dev/null 2>&1; then
  log "evtest is installed. Run a specific device manually, for example:"
  log "sudo evtest /dev/input/eventX"
else
  log "evtest not installed. Install it with: sudo apt-get install evtest"
fi
