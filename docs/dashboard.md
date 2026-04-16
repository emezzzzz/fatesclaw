# Dashboard

The dashboard app lives in `apps/fatesclaw-dashboard`.

## Install

```bash
./scripts/install-dashboard.sh
```

## Mock Run

```bash
cd apps/fatesclaw-dashboard
AGENT_PANEL_MOCK_GATEWAY=1 AGENT_PANEL_OLED_MODE=mock python -m fatesclaw_dashboard.main
```

## Real Pi Run

```bash
cp config/dashboard.env.example config/dashboard.env
./scripts/run-dashboard-dev.sh
```

The default real OLED profile is:

```text
AGENT_PANEL_MOCK_GATEWAY=0
AGENT_PANEL_OLED_MODE=ssd1322
AGENT_PANEL_OLED_ROTATION=180
AGENT_PANEL_USE_EVDEV_CONTROLS=1
```

## Gateway Auth

If `AGENT_PANEL_GATEWAY_URL` is set, explicit auth is required:

```text
OPENCLAW_GATEWAY_TOKEN=<OPENCLAW_GATEWAY_TOKEN>
```

or:

```text
OPENCLAW_GATEWAY_PASSWORD=<OPENCLAW_GATEWAY_PASSWORD>
```

Token auth is preferred when both are present. Secret values are not logged.

## Views

- `HOME`: gateway ON/OFF, current mode, last event, animated heart.
- `CHAT`: said content only, with `U:` and `A:` prefixes.
- `MIND`: thought/process content only.
- `AGENTS`: active agent picker.
- `JOBS`, `APPROVALS`, `SYSTEM`: operational status and conservative actions.

## Input

Fates controls use logical roles, not UI hardcoding:

- `BTN_ENTER`, `BTN_LEFT`, `BTN_RIGHT`
- `ENC_MAIN`, `ENC_LEFT`, `ENC_RIGHT`

Keyboard fallback remains available. In `CHAT`, typing updates the bottom `›`
prompt line and `Enter` submits.
