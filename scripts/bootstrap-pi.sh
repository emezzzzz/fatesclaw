#!/usr/bin/env bash
set -euo pipefail

log() {
  printf '[bootstrap-pi] %s\n' "$*"
}

if ! command -v apt-get >/dev/null 2>&1; then
  log "apt-get not found; this script targets Raspberry Pi OS/Debian."
  exit 1
fi

SUDO=""
if [ "$(id -u)" -ne 0 ]; then
  SUDO="sudo"
fi

PACKAGES=(
  alsa-utils
  build-essential
  ca-certificates
  curl
  device-tree-compiler
  evtest
  git
  i2c-tools
  libasound2-dev
  nodejs
  npm
  pkg-config
  portaudio19-dev
  python3
  python3-dev
  python3-gpiozero
  python3-pip
  python3-rpi.gpio
  python3-venv
  raspi-config
)

log "Updating package index"
$SUDO apt-get update

if [ "${FATESCLAW_SKIP_UPGRADE:-0}" != "1" ]; then
  log "Upgrading installed packages"
  $SUDO DEBIAN_FRONTEND=noninteractive apt-get upgrade -y
fi

log "Installing baseline packages"
$SUDO DEBIAN_FRONTEND=noninteractive apt-get install -y "${PACKAGES[@]}"

log "Done. Reboot after hardware overlay changes, not necessarily after this bootstrap."
