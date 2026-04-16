# Overview

`fatesClaw` packages the pieces needed to run OpenClaw as an appliance-style
agent system on a Raspberry Pi 4B with Fates hardware.

The repository is split into four layers:

- Pi operating system setup.
- Fates hardware bring-up and verification.
- OpenClaw gateway installation and provider configuration.
- OLED dashboard application for local status and controls.

The dashboard is intentionally external to OpenClaw. It connects to the local
OpenClaw Gateway over WebSocket, reads safe local session logs as a refresh
fallback, and renders a compact UI on a 128x64 grayscale OLED.

## Public Release Posture

No runtime state is part of this repository. OpenClaw config, provider keys,
session logs, local env files, SSH files, Codex config, shell history, and local
machine paths must stay outside git.

Before publishing or pushing, run:

```bash
./scripts/sanitize-repo-check.sh
```
