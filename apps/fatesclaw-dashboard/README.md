# fatesclaw-dashboard

`fatesclaw-dashboard` is a small Python app that renders an OpenClaw status and
control surface on the Fates/Newhaven SSD1322 OLED. It can run in mock mode on a
development machine or on a Raspberry Pi 4B with Fates hardware.

## Install

```bash
cd apps/fatesclaw-dashboard
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

## Mock Mode

```bash
AGENT_PANEL_MOCK_GATEWAY=1 \
AGENT_PANEL_OLED_MODE=mock \
python -m fatesclaw_dashboard.main
```

Mock OLED mode writes the latest frame to `tmp/oled-preview.png`.

## Real OLED Mode

```bash
AGENT_PANEL_MOCK_GATEWAY=0 \
AGENT_PANEL_OLED_MODE=ssd1322 \
AGENT_PANEL_OLED_ROTATION=180 \
AGENT_PANEL_USE_EVDEV_CONTROLS=1 \
python -m fatesclaw_dashboard.main
```

The real OLED path assumes userspace SPI through `luma.oled`. If a kernel
`fates-ssd1322` overlay owns `spi0.0`, disable that overlay for this dashboard
path and keep `dtparam=spi=on`.

## Gateway Auth

Default gateway URL:

```text
ws://127.0.0.1:18789/ws
```

If `AGENT_PANEL_GATEWAY_URL` is explicitly set, provide one of:

```bash
OPENCLAW_GATEWAY_TOKEN=<OPENCLAW_GATEWAY_TOKEN>
OPENCLAW_GATEWAY_PASSWORD=<OPENCLAW_GATEWAY_PASSWORD>
```

Token auth wins when both are present. Secret values are not logged.

## Controls

- `ENC_LEFT`: switch views.
- `ENC_MAIN`: select/scroll.
- `ENC_RIGHT`: contextual control.
- `BTN_LEFT`: back/cancel or reject.
- `BTN_ENTER`: open/select/submit.
- `BTN_RIGHT`: menu or approve.

Keyboard fallback is available for development. In `CHAT`, typed text appears on
the bottom prompt line and `Enter` submits the draft.
