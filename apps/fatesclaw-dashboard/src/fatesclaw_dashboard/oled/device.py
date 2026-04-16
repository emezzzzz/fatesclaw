from __future__ import annotations

import logging
from pathlib import Path

from PIL import Image

from fatesclaw_dashboard.config import Config

LOGGER = logging.getLogger(__name__)

try:
    from luma.core.interface.serial import spi
    from luma.oled.device import ssd1322, ssd1322_nhd
except ImportError:  # pragma: no cover
    spi = None  # type: ignore[assignment]
    ssd1322 = None  # type: ignore[assignment]
    ssd1322_nhd = None  # type: ignore[assignment]


class OLEDTarget:
    width: int
    height: int
    image_mode: str = "L"

    def display(self, image: Image.Image) -> None:
        raise NotImplementedError


class MockOLEDTarget(OLEDTarget):
    def __init__(self, width: int, height: int, output: Path) -> None:
        self.width = width
        self.height = height
        self.image_mode = "L"
        self.output = output
        self.output.parent.mkdir(parents=True, exist_ok=True)

    def display(self, image: Image.Image) -> None:
        image.save(self.output)
        LOGGER.debug("mock_oled_frame path=%s", self.output)


class LumaOLEDTarget(OLEDTarget):
    def __init__(self, config: Config) -> None:
        if ssd1322 is None or ssd1322_nhd is None:
            raise RuntimeError("luma.oled is not installed")
        if config.oled_mode != "ssd1322":
            raise RuntimeError(f"unsupported oled mode: {config.oled_mode}")
        if config.oled_port != "spi":
            raise RuntimeError("ssd1322 oled mode currently supports SPI only")

        spidev_path = Path(f"/dev/spidev{config.oled_spi_port}.{config.oled_spi_device}")
        if not spidev_path.exists():
            raise RuntimeError(
                f"SPI device {spidev_path} not found. If dtoverlay=fates-ssd1322 is enabled, "
                "it disables spidev0 for the kernel SSD1322 driver. Comment out that overlay "
                "when running fatesclaw-dashboard in luma.oled mode."
            )

        serial = spi(
            port=config.oled_spi_port,
            device=config.oled_spi_device,
            gpio_DC=config.oled_dc_pin,
            gpio_RST=config.oled_reset_pin,
        )

        if (config.oled_width, config.oled_height) == (128, 64):
            self.device = ssd1322_nhd(serial, rotate=config.oled_rotation)
        else:
            self.device = ssd1322(
                serial,
                width=config.oled_width,
                height=config.oled_height,
                rotate=config.oled_rotation,
            )
        self.width = self.device.width
        self.height = self.device.height
        # Render UI frames in greyscale and convert once at the device boundary.
        # luma.oled exposes SSD1322 in RGB mode, and drawing scalar fills directly
        # onto an RGB canvas causes Pillow to emit red-only pixels.
        self.image_mode = "L"
        self._device_mode = self.device.mode
        if config.oled_contrast is not None:
            try:
                self.device.contrast(max(0, min(255, config.oled_contrast)))
                LOGGER.info("oled_contrast_set value=%s", max(0, min(255, config.oled_contrast)))
            except Exception as exc:
                LOGGER.warning("oled_contrast_set_failed error=%s", exc)

    def display(self, image: Image.Image) -> None:
        if image.mode != self._device_mode:
            image = image.convert(self._device_mode)
        self.device.display(image)


def create_oled_target(config: Config) -> OLEDTarget:
    if config.oled_mode == "mock":
        return MockOLEDTarget(config.oled_width, config.oled_height, config.mock_oled_output)
    return LumaOLEDTarget(config)
