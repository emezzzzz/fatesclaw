#!/usr/bin/env bash
set -euo pipefail

log() {
  printf '[install-dashboard] %s\n' "$*"
}

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
APP_DIR="$(CDPATH= cd -- "$SCRIPT_DIR/../apps/fatesclaw-dashboard" && pwd)"

cd "$APP_DIR"
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .

log "Dashboard installed in $APP_DIR/.venv"
log "Create a local env file from config/dashboard.env.example before running real hardware mode."
