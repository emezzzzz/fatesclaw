# Raspberry Pi OS Setup

## Image

Use Raspberry Pi Imager and select:

- Raspberry Pi OS Lite 64-bit.
- SSH enabled.
- A non-default password or SSH key.
- Locale, timezone, and keyboard layout appropriate for your site.

Ethernet is recommended for the first boot. A desktop environment is not
required.

## First Login

Use placeholders in notes and automation:

```bash
ssh <PI_USER>@<PI_HOST>
```

Update the base OS:

```bash
sudo apt-get update
sudo apt-get upgrade -y
```

Or run the repo bootstrap script:

```bash
cd <PROJECT_PATH>
./scripts/bootstrap-pi.sh
```

## Baseline Packages

The bootstrap script installs development and hardware tools needed for this
stack: Python venv tooling, build tools, ALSA utilities, PortAudio headers,
GPIO helpers, `evtest`, `i2c-tools`, `device-tree-compiler`, Node.js, and npm.

Reboot after hardware overlay changes, not necessarily after the baseline
package install.
