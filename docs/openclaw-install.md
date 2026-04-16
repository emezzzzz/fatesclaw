# OpenClaw Install

## Requirements

OpenClaw requires Node.js and npm. Install a current LTS release suitable for
Raspberry Pi OS.

Check:

```bash
node --version
npm --version
```

## Install

The install helper is dry-run by default:

```bash
./scripts/install-openclaw.sh
```

To run the default npm install command:

```bash
FATESCLAW_INSTALL_OPENCLAW=1 ./scripts/install-openclaw.sh
```

Override the package name if your OpenClaw install source differs:

```bash
OPENCLAW_NPM_PACKAGE=<OPENCLAW_PACKAGE> FATESCLAW_INSTALL_OPENCLAW=1 ./scripts/install-openclaw.sh
```

## Gateway

Recommended gateway posture:

- Bind to loopback by default.
- Use SSH tunnels for remote access.
- Keep auth tokens in ignored env files.
- Do not commit OpenClaw user config.

Default local URL used by the dashboard:

```text
ws://127.0.0.1:18789/ws
```

The repository ships only `config/openclaw.env.example` and a systemd template.
It does not include any real `openclaw.json`.

## systemd

Copy the example and replace placeholders locally:

```bash
sudo install -m 0644 config/systemd/openclaw-gateway.service.example /etc/systemd/system/openclaw-gateway.service
sudo systemctl daemon-reload
sudo systemctl enable --now openclaw-gateway.service
sudo systemctl status openclaw-gateway.service
```

Do not commit the edited service file if it contains real local paths.
