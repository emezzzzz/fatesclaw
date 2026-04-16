# fatesClaw

`fatesClaw` is a public-ready toolkit for running OpenClaw on a Raspberry Pi 4B
with a Fates-style hardware stack: Newhaven/Fates SSD1322 OLED, WM8731 ALSA
audio, three buttons, and three rotary encoders.

The repository includes Raspberry Pi setup notes, Fates hardware bring-up
scripts, OpenClaw gateway service templates, provider examples, Codex remote
development notes, and a reusable OLED dashboard app.

## Target Hardware

- Raspberry Pi 4B
- Raspberry Pi OS Lite 64-bit
- Fates board
- Newhaven OLED model used by Fates, SSD1322-compatible
- WM8731 audio codec exposed through ALSA
- 3 buttons and 3 rotary encoders
- OpenClaw running locally on the Pi

## Security Model

This repository is designed for public release. It does not ship real OpenClaw
configuration, provider credentials, session files, machine paths, SSH data, or
local runtime state. All secrets must be supplied through ignored local env files
or environment variables.

Run the sanitizer before publishing:

```bash
./scripts/sanitize-repo-check.sh
```

## Quickstart

On a fresh Pi:

```bash
git clone <YOUR_REPO_URL> fatesClaw
cd fatesClaw
./scripts/bootstrap-pi.sh
./scripts/enable-fates-hardware.sh
./scripts/install-openclaw.sh
./scripts/install-dashboard.sh
```

Create local ignored env files from examples:

```bash
cp config/openclaw.env.example config/openclaw.env
cp config/dashboard.env.example config/dashboard.env
```

Edit those local files with your own provider credentials and hardware overrides.
Do not commit them.

Run the dashboard in development mode:

```bash
./scripts/run-dashboard-dev.sh
```

## Repository Layout

- `docs/`: setup, hardware, OpenClaw, dashboard, Codex, security, and troubleshooting guides.
- `scripts/`: Pi bootstrap, hardware enablement, verification, install, and sanitization helpers.
- `config/`: placeholder-only env and systemd examples.
- `apps/fatesclaw-dashboard/`: Python OLED dashboard app and tests.
- `examples/`: provider and dashboard examples with placeholders only.
- `tests/`: lightweight repo-level static tests.

## Setup Flow

1. Prepare Raspberry Pi OS Lite 64-bit: `docs/raspberry-pi-os-setup.md`.
2. Bring up Fates hardware: `docs/fates-bringup.md`.
3. Install and run OpenClaw gateway: `docs/openclaw-install.md`.
4. Configure provider env vars: `docs/openclaw-provider-examples.md`.
5. Install the dashboard: `docs/dashboard.md`.
6. Optionally use Codex remote development: `docs/codex-remote-dev.md`.
7. Run release checks before publishing: `docs/release-checklist.md`.

## Current Status

The dashboard supports mock mode, real SSD1322 OLED mode through `luma.oled`,
OpenClaw Gateway integration, env-based gateway auth, Fates evdev controls,
keyboard fallback, Chat/Mind split views, an agent picker, and a Home heart
animation. Audio bring-up is documented and verifiable, but voice interaction is
not implemented.
