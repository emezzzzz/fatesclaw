#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [ -f ".venv/bin/activate" ]; then
  . .venv/bin/activate
fi

# Optional local defaults for this machine. This file is intentionally ignored.
ENV_FILE="${AGENT_PANEL_ENV_FILE:-.env.local}"
if [ -f "$ENV_FILE" ]; then
  while IFS= read -r line; do
    case "$line" in
      ""|\#*)
        continue
        ;;
    esac
    if [ "${line#*=}" = "$line" ]; then
      continue
    fi
    key="${line%%=*}"
    value="${line#*=}"
    if [ -z "${!key+x}" ]; then
      export "$key=$value"
    fi
  done < "$ENV_FILE"
fi

export AGENT_PANEL_MOCK_GATEWAY="${AGENT_PANEL_MOCK_GATEWAY:-1}"
export AGENT_PANEL_OLED_MODE="${AGENT_PANEL_OLED_MODE:-mock}"
export AGENT_PANEL_LOG_LEVEL="${AGENT_PANEL_LOG_LEVEL:-DEBUG}"

python -m fatesclaw_dashboard.main
