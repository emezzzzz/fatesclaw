#!/usr/bin/env bash
set -euo pipefail

log() {
  printf '[verify-oled] %s\n' "$*"
}

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
APP_DIR="$(CDPATH= cd -- "$SCRIPT_DIR/../apps/fatesclaw-dashboard" && pwd)"

log "SPI devices"
ls -l /dev/spidev* 2>/dev/null || true

cd "$APP_DIR"
if [ -f ".venv/bin/activate" ]; then
  . .venv/bin/activate
fi

export SSD1322_TEST_DRIVER="${SSD1322_TEST_DRIVER:-ssd1322_nhd}"
export SSD1322_TEST_SPI_PORT="${SSD1322_TEST_SPI_PORT:-0}"
export SSD1322_TEST_SPI_DEVICE="${SSD1322_TEST_SPI_DEVICE:-0}"
export SSD1322_TEST_WIDTH="${SSD1322_TEST_WIDTH:-128}"
export SSD1322_TEST_HEIGHT="${SSD1322_TEST_HEIGHT:-64}"
export SSD1322_TEST_DC_PIN="${SSD1322_TEST_DC_PIN:-17}"
export SSD1322_TEST_RESET_PIN="${SSD1322_TEST_RESET_PIN:-4}"

log "Running OLED smoke test"
python scripts/ssd1322_smoke_test.py
