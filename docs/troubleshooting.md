# Troubleshooting

## SSH

Confirm the Pi is reachable:

```bash
ssh <PI_USER>@<PI_HOST>
```

Prefer Ethernet for first boot. Check router leases or your provisioning tool
for the current host address.

## Missing SPI

Check:

```bash
ls -l /dev/spidev*
grep -n 'dtparam=spi=on' /boot/firmware/config.txt
```

If `/dev/spidev0.0` is missing, make sure no kernel OLED overlay has claimed
SPI0 CE0.

## Missing I2C

Check:

```bash
ls -l /dev/i2c*
i2cdetect -l
```

Enable `dtparam=i2c_arm=on` and reboot.

## WM8731 Audio Not Appearing

Inspect:

```bash
aplay -l
arecord -l
dmesg | grep -i -E 'wm8731|i2s|alsa'
```

Confirm the Fates audio overlay strategy for your board revision.

## PortAudio Or RPi.GPIO Missing

Install baseline packages:

```bash
./scripts/bootstrap-pi.sh
```

Then reinstall the dashboard virtualenv:

```bash
./scripts/install-dashboard.sh
```

## OLED Blank Screen

Check:

- `/dev/spidev0.0` exists.
- `AGENT_PANEL_OLED_MODE=ssd1322`.
- DC/reset pins match your board.
- Rotation and geometry match the panel.
- Kernel `fates-ssd1322` overlay is disabled for userspace `luma.oled` mode.

Run:

```bash
./scripts/verify-oled.sh
```

## Controls Not Responding

Check:

```bash
./scripts/verify-controls.sh
```

If evdev devices are present but auto-detection fails, set explicit dashboard
env vars for `AGENT_PANEL_ENC_*_EVDEV_DEVICE` and `AGENT_PANEL_BTN_EVDEV_DEVICE`.

## Gateway URL Or Auth Mismatch

If you set `AGENT_PANEL_GATEWAY_URL`, also set explicit auth:

```text
OPENCLAW_GATEWAY_TOKEN=<OPENCLAW_GATEWAY_TOKEN>
```

or:

```text
OPENCLAW_GATEWAY_PASSWORD=<OPENCLAW_GATEWAY_PASSWORD>
```

When using the default local gateway path, the dashboard can read local OpenClaw
gateway settings without modifying them.

## systemd Fails But Shell Works

Most failures are missing environment or path differences. Inspect:

```bash
systemctl status fatesclaw-dashboard.service
journalctl -u fatesclaw-dashboard.service -n 100
```

Confirm `WorkingDirectory`, `EnvironmentFile`, and venv paths in the local
service file.

## Codex Remote Issues

Keep the app-server bound to loopback and use SSH forwarding. Confirm the local
forwarded URL from the developer machine before running `codex --remote`.
