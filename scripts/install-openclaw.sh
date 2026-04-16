#!/usr/bin/env bash
set -euo pipefail

log() {
  printf '[install-openclaw] %s\n' "$*"
}

if ! command -v node >/dev/null 2>&1; then
  log "Node.js is required. Install a current LTS release before installing OpenClaw."
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  log "npm is required. Install npm before installing OpenClaw."
  exit 1
fi

if [ "${FATESCLAW_INSTALL_OPENCLAW:-0}" != "1" ]; then
  log "Dry run. Set FATESCLAW_INSTALL_OPENCLAW=1 to run the npm install command."
  log "Default command: npm install -g openclaw"
  exit 0
fi

package="${OPENCLAW_NPM_PACKAGE:-openclaw}"
log "Installing $package globally with npm"
npm install -g "$package"
log "Install complete. Configure secrets through an ignored env file."
