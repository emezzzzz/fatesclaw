# Fates Bring-Up

## Hardware Interfaces

Enable SPI and I2C:

```bash
sudo raspi-config
```

Or use:

```bash
./scripts/enable-fates-hardware.sh
```

The script appends:

```text
dtparam=spi=on
dtparam=i2c_arm=on
dtparam=i2s=on
```

It can also compile and install the Fates controls overlay from source.

## OLED Overlay Note

The dashboard uses userspace SPI via `luma.oled`. A kernel OLED overlay such as:

```text
dtoverlay=fates-ssd1322,rotate=180
```

can bind `spi0.0` and remove `/dev/spidev0.0`. For the dashboard's current
userspace OLED path, keep SPI enabled and disable the kernel OLED overlay.

Verify SPI:

```bash
ls -l /dev/spidev*
```

Run the smoke test:

```bash
./scripts/verify-oled.sh
```

## Controls

The included controls overlay exposes rotary encoders as evdev relative-axis
devices and buttons as an evdev key device.

Verify:

```bash
./scripts/verify-controls.sh
sudo evtest /dev/input/eventX
```

Replace `/dev/input/eventX` with a device shown by the script.

## Audio

Verify ALSA:

```bash
./scripts/verify-audio.sh
```

Optional playback and capture tests:

```bash
FATESCLAW_AUDIO_PLAYBACK_TEST=1 AUDIO_PLAYBACK_DEVICE=<AUDIO_PLAYBACK_DEVICE> ./scripts/verify-audio.sh
FATESCLAW_AUDIO_CAPTURE_TEST=1 AUDIO_CAPTURE_DEVICE=<AUDIO_CAPTURE_DEVICE> ./scripts/verify-audio.sh
```
