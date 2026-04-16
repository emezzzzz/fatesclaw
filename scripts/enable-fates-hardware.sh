#!/usr/bin/env bash
set -euo pipefail

log() {
  printf '[enable-fates-hardware] %s\n' "$*"
}

SUDO=""
if [ "$(id -u)" -ne 0 ]; then
  SUDO="sudo"
fi

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
REPO_DIR="$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)"
BOOT_CONFIG="${BOOT_CONFIG:-/boot/firmware/config.txt}"
OVERLAY_SRC="$REPO_DIR/apps/fatesclaw-dashboard/overlays/fates-buttons-4encoders-rpi.dts"
OVERLAY_NAME="${FATESCLAW_CONTROLS_OVERLAY:-fates-buttons-4encoders-rpi}"
OVERLAY_DST_DIR="${OVERLAY_DST_DIR:-/boot/firmware/overlays}"
OVERLAY_DTBO="$OVERLAY_DST_DIR/$OVERLAY_NAME.dtbo"

if [ ! -f "$BOOT_CONFIG" ]; then
  log "Boot config not found at $BOOT_CONFIG"
  log "Set BOOT_CONFIG=/path/to/config.txt if your Raspberry Pi OS uses another path."
  exit 1
fi

ensure_line() {
  local line="$1"
  if ! grep -qxF "$line" "$BOOT_CONFIG"; then
    printf '%s\n' "$line" | $SUDO tee -a "$BOOT_CONFIG" >/dev/null
    log "Added: $line"
  else
    log "Already present: $line"
  fi
}

backup="$BOOT_CONFIG.fatesclaw.$(date +%Y%m%d%H%M%S).bak"
log "Backing up $BOOT_CONFIG to $backup"
$SUDO cp "$BOOT_CONFIG" "$backup"

ensure_line "dtparam=spi=on"
ensure_line "dtparam=i2c_arm=on"
ensure_line "dtparam=i2s=on"

if [ "${FATESCLAW_INSTALL_CONTROLS_OVERLAY:-1}" = "1" ]; then
  if ! command -v dtc >/dev/null 2>&1; then
    log "dtc not found; install device-tree-compiler first."
    exit 1
  fi
  if [ ! -f "$OVERLAY_SRC" ]; then
    log "Overlay source not found: $OVERLAY_SRC"
    exit 1
  fi
  tmp_dtbo="$(mktemp)"
  log "Compiling controls overlay $OVERLAY_NAME"
  dtc -@ -I dts -O dtb -o "$tmp_dtbo" "$OVERLAY_SRC"
  $SUDO install -m 0644 "$tmp_dtbo" "$OVERLAY_DTBO"
  rm -f "$tmp_dtbo"
  ensure_line "dtoverlay=$OVERLAY_NAME"
fi

if [ "${FATESCLAW_DISABLE_KERNEL_OLED_OVERLAY:-1}" = "1" ]; then
  log "Commenting active fates-ssd1322 overlay lines for userspace luma.oled/spidev mode"
  $SUDO sed -i.bak -E 's/^(dtoverlay=fates-ssd1322.*)$/# \1/' "$BOOT_CONFIG"
fi

log "Hardware config updated. Reboot the Pi, then run verify scripts."
