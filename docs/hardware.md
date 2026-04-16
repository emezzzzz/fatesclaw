# Hardware

## Target

- Raspberry Pi 4B.
- Raspberry Pi OS Lite 64-bit.
- Fates board.
- Newhaven/Fates SSD1322-compatible OLED.
- WM8731 audio codec exposed through ALSA.
- Three buttons.
- Three rotary encoders.

## Known Working Defaults

These defaults describe a known Pi 4B + Fates-style setup. They are not treated
as universal board truth.

- OLED transport: SPI0 CE0 through userspace `luma.oled`.
- OLED logical geometry: `128x64`.
- OLED driver path: `ssd1322_nhd`.
- OLED rotation: `180`.
- Dashboard OLED D/C pin: BCM `17`.
- Dashboard OLED reset pin: BCM `4`.
- Button GPIO assumptions: BCM `24`, `25`, `23`.
- Encoder assumptions: BCM `5:6`, `13:12`, `27:22`.

## Configurable Areas

All GPIO and evdev mappings are configurable through dashboard environment
variables. If a board revision differs, update env files rather than editing UI
logic.

The WM8731 ALSA device name can vary. Always inspect:

```bash
aplay -l
arecord -l
```

Do not commit device-specific ALSA config. Use `config/asound.conf.example` as a
template only.
