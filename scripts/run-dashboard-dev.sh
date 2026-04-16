#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
APP_DIR="$(CDPATH= cd -- "$SCRIPT_DIR/../apps/fatesclaw-dashboard" && pwd)"

cd "$APP_DIR"
export AGENT_PANEL_ENV_FILE="${AGENT_PANEL_ENV_FILE:-../../config/dashboard.env}"
exec ./scripts/run_dev.sh
