#!/usr/bin/env python3
from __future__ import annotations

import logging
import os
import sys
import time
import traceback
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

try:
    from luma.core.interface.serial import gpio_cs_spi, spi
    from luma.oled.device import ssd1322, ssd1322_nhd
except ImportError as exc:  # pragma: no cover
    print(f"FAILED TO IMPORT OLED DEPENDENCIES: {exc}", file=sys.stderr)
    raise

try:
    import RPi.GPIO as GPIO
except ImportError:  # pragma: no cover
    GPIO = None  # type: ignore[assignment]


LOGGER = logging.getLogger("ssd1322_smoke_test")


@dataclass(frozen=True)
class Config:
    spi_port: int
    spi_device: int
    spi_speed_hz: int
    spi_mode: int | None
    gpio_cs_pin: int | None
    cs_active_high: bool
    shdn_pin: int | None
    bs0_pin: int | None
    bs1_pin: int | None
    dc_pin: int
    reset_pin: int
    width: int
    height: int
    animation_seconds: float
    static_hold_seconds: float
    all_on_hold_seconds: float
    controller_all_on_hold_seconds: float
    refresh_hz: float
    bar_thickness: int
    reset_hold_seconds: float
    reset_release_seconds: float
    driver: str
    transport: str
    preview_output: Path
    preview_dir: Path
    save_each_frame: bool
    trace_max_bytes: int
    profile: str
    post_init_hex: str

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            spi_port=int(os.getenv("SSD1322_TEST_SPI_PORT", "0")),
            spi_device=int(os.getenv("SSD1322_TEST_SPI_DEVICE", "0")),
            spi_speed_hz=int(os.getenv("SSD1322_TEST_SPI_SPEED_HZ", "8000000")),
            spi_mode=(
                None
                if os.getenv("SSD1322_TEST_SPI_MODE") in {None, "", "default"}
                else int(os.getenv("SSD1322_TEST_SPI_MODE", "0"))
            ),
            gpio_cs_pin=(
                None
                if os.getenv("SSD1322_TEST_GPIO_CS_PIN") in {None, "", "none"}
                else int(os.getenv("SSD1322_TEST_GPIO_CS_PIN", "0"))
            ),
            cs_active_high=os.getenv("SSD1322_TEST_CS_ACTIVE_HIGH", "0").strip() == "1",
            shdn_pin=(
                None
                if os.getenv("SSD1322_TEST_SHDN_PIN") in {None, "", "none"}
                else int(os.getenv("SSD1322_TEST_SHDN_PIN", "0"))
            ),
            bs0_pin=(
                None
                if os.getenv("SSD1322_TEST_BS0_PIN") in {None, "", "none"}
                else int(os.getenv("SSD1322_TEST_BS0_PIN", "0"))
            ),
            bs1_pin=(
                None
                if os.getenv("SSD1322_TEST_BS1_PIN") in {None, "", "none"}
                else int(os.getenv("SSD1322_TEST_BS1_PIN", "0"))
            ),
            dc_pin=int(os.getenv("SSD1322_TEST_DC_PIN", "24")),
            reset_pin=int(os.getenv("SSD1322_TEST_RESET_PIN", "25")),
            width=int(os.getenv("SSD1322_TEST_WIDTH", "256")),
            height=int(os.getenv("SSD1322_TEST_HEIGHT", "64")),
            animation_seconds=float(os.getenv("SSD1322_TEST_ANIMATION_SECONDS", "10")),
            static_hold_seconds=float(os.getenv("SSD1322_TEST_STATIC_HOLD_SECONDS", "1")),
            all_on_hold_seconds=float(os.getenv("SSD1322_TEST_ALL_ON_HOLD_SECONDS", "1")),
            controller_all_on_hold_seconds=float(
                os.getenv("SSD1322_TEST_CONTROLLER_ALL_ON_HOLD_SECONDS", "1")
            ),
            refresh_hz=float(os.getenv("SSD1322_TEST_REFRESH_HZ", "10")),
            bar_thickness=max(1, int(os.getenv("SSD1322_TEST_BAR_THICKNESS", "4"))),
            reset_hold_seconds=float(os.getenv("SSD1322_TEST_RESET_HOLD_SECONDS", "0.1")),
            reset_release_seconds=float(os.getenv("SSD1322_TEST_RESET_RELEASE_SECONDS", "0.15")),
            driver=os.getenv("SSD1322_TEST_DRIVER", "auto").strip().lower(),
            transport=os.getenv("SSD1322_TEST_TRANSPORT", "hw").strip().lower(),
            preview_output=Path(
                os.getenv("SSD1322_TEST_PREVIEW_OUTPUT", "./tmp/ssd1322-smoke-preview.png")
            ),
            preview_dir=Path(
                os.getenv("SSD1322_TEST_PREVIEW_DIR", "./tmp/ssd1322-smoke-frames")
            ),
            save_each_frame=os.getenv("SSD1322_TEST_SAVE_EACH_FRAME", "0").strip() == "1",
            trace_max_bytes=max(8, int(os.getenv("SSD1322_TEST_TRACE_MAX_BYTES", "32"))),
            profile=os.getenv("SSD1322_TEST_PROFILE", "default").strip().lower(),
            post_init_hex=os.getenv("SSD1322_TEST_POST_INIT_HEX", "").strip(),
        )


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stdout,
    )


def load_font() -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype("DejaVuSans.ttf", 16)
    except OSError:
        LOGGER.warning("font_load_fallback reason=DejaVuSans.ttf unavailable")
        return ImageFont.load_default()


class TraceSerial:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.command_calls = 0
        self.data_calls = 0
        self.command_bytes = 0
        self.data_bytes = 0
        LOGGER.debug(
            "trace_serial_init spi_port=%s spi_device=%s spi_speed_hz=%s spi_mode=%s gpio_cs_pin=%s shdn_pin=%s bs0_pin=%s bs1_pin=%s dc_pin=%s reset_pin=%s",
            config.spi_port,
            config.spi_device,
            config.spi_speed_hz,
            config.spi_mode,
            config.gpio_cs_pin,
            config.shdn_pin,
            config.bs0_pin,
            config.bs1_pin,
            config.dc_pin,
            config.reset_pin,
        )

    def _sample(self, payload: list[int]) -> str:
        limit = self.config.trace_max_bytes
        head = " ".join(f"{byte:02X}" for byte in payload[:limit])
        if len(payload) > limit:
            head = f"{head} ..."
        return head

    def command(self, *cmd: int) -> None:
        payload = list(cmd)
        self.command_calls += 1
        self.command_bytes += len(payload)
        LOGGER.debug(
            "trace_command call=%s bytes=%s payload=%s",
            self.command_calls,
            len(payload),
            self._sample(payload),
        )

    def data(self, data: list[int]) -> None:
        payload = list(data)
        self.data_calls += 1
        self.data_bytes += len(payload)
        LOGGER.debug(
            "trace_data call=%s bytes=%s payload=%s",
            self.data_calls,
            len(payload),
            self._sample(payload),
        )

    def cleanup(self) -> None:
        LOGGER.debug(
            "trace_serial_cleanup command_calls=%s command_bytes=%s data_calls=%s data_bytes=%s",
            self.command_calls,
            self.command_bytes,
            self.data_calls,
            self.data_bytes,
        )


def save_preview(image: Image.Image, destination: Path, label: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    image.save(destination)
    LOGGER.debug("preview_saved label=%s path=%s", label, destination)


class ProbeGPIO:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.enabled = any(pin is not None for pin in (config.shdn_pin, config.bs0_pin, config.bs1_pin))
        self._pins: list[int] = []

    def setup(self) -> None:
        if not self.enabled:
            LOGGER.debug("probe_gpio_skip reason=no_optional_control_pins")
            return
        if GPIO is None:
            raise RuntimeError("RPi.GPIO is not installed; cannot drive SHDN/BS pins")

        LOGGER.debug(
            "probe_gpio_setup_start shdn_pin=%s bs0_pin=%s bs1_pin=%s",
            self.config.shdn_pin,
            self.config.bs0_pin,
            self.config.bs1_pin,
        )
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)

        if self.config.shdn_pin is not None:
            GPIO.setup(self.config.shdn_pin, GPIO.OUT, initial=GPIO.HIGH)
            self._pins.append(self.config.shdn_pin)
            LOGGER.debug("probe_gpio_assert pin=%s role=shdn level=HIGH", self.config.shdn_pin)
        if self.config.bs0_pin is not None:
            GPIO.setup(self.config.bs0_pin, GPIO.OUT, initial=GPIO.LOW)
            self._pins.append(self.config.bs0_pin)
            LOGGER.debug("probe_gpio_assert pin=%s role=bs0 level=LOW", self.config.bs0_pin)
        if self.config.bs1_pin is not None:
            GPIO.setup(self.config.bs1_pin, GPIO.OUT, initial=GPIO.LOW)
            self._pins.append(self.config.bs1_pin)
            LOGGER.debug("probe_gpio_assert pin=%s role=bs1 level=LOW", self.config.bs1_pin)

        LOGGER.debug("probe_gpio_setup_end pins=%s", self._pins)

    def cleanup(self) -> None:
        if not self._pins or GPIO is None:
            return
        LOGGER.debug("probe_gpio_cleanup pins=%s", self._pins)
        GPIO.cleanup(self._pins)


def parse_hex_groups(value: str) -> list[tuple[int, ...]]:
    groups: list[tuple[int, ...]] = []
    for raw_group in value.split(";"):
        cleaned = raw_group.replace(",", " ").split()
        if cleaned:
            groups.append(tuple(int(token, 16) for token in cleaned))
    return groups


def apply_post_init_profile(device, config: Config) -> None:
    commands: list[tuple[int, ...]] = []

    if config.profile == "default":
        pass
    elif config.profile == "nhd_phase_alt":
        commands = [
            (0xB1, 0xE2),
            (0xBB, 0x1F),
            (0xC1, 0xFF),
            (0xC7, 0x0F),
        ]
    elif config.profile == "nhd_remap_14":
        commands = [
            (0xA0, 0x14, 0x11),
            (0xA1, 0x00),
            (0xA2, 0x00),
        ]
    elif config.profile == "nhd_remap_17":
        commands = [
            (0xA0, 0x17, 0x11),
            (0xA1, 0x00),
            (0xA2, 0x00),
        ]
    elif config.profile == "generic_128":
        commands = [
            (0xA0, 0x14, 0x11),
            (0xAB, 0x01),
            (0xB1, 0xF0),
            (0xBB, 0x0D),
            (0xBE, 0x00),
            (0xC1, 0x9F),
            (0xC7, 0x0F),
            (0xA6,),
        ]
    else:
        raise RuntimeError(f"unsupported profile: {config.profile}")

    if config.post_init_hex:
        extra_groups = parse_hex_groups(config.post_init_hex)
        if not extra_groups:
            raise RuntimeError("post_init_hex was set but produced no bytes")
        commands.extend(extra_groups)

    if not commands:
        LOGGER.debug("post_init_profile_skip profile=%s", config.profile)
        return

    LOGGER.debug("post_init_profile_start profile=%s commands=%s", config.profile, len(commands))
    for index, payload in enumerate(commands):
        LOGGER.debug(
            "post_init_profile_command index=%s payload=%s",
            index,
            " ".join(f"{byte:02X}" for byte in payload),
        )
        device.command(*payload)
    LOGGER.debug("post_init_profile_end profile=%s", config.profile)


def draw_pattern(
    width: int,
    height: int,
    mode: str,
    font: ImageFont.ImageFont | ImageFont.FreeTypeFont,
    bar_x: int | None,
    bar_thickness: int,
) -> Image.Image:
    image = Image.new(mode, (width, height), color="black")
    draw = ImageDraw.Draw(image)

    draw.rectangle((0, 0, width - 1, height - 1), outline="white", width=1)
    draw.line((0, 0, width - 1, height - 1), fill=(192, 192, 192), width=1)

    text = "SSD1322 TEST"
    text_box = draw.textbbox((0, 0), text, font=font)
    text_width = text_box[2] - text_box[0]
    text_height = text_box[3] - text_box[1]
    text_x = max(0, (width - text_width) // 2)
    text_y = max(0, (height - text_height) // 2)
    draw.text((text_x, text_y), text, fill="white", font=font)

    if bar_x is not None:
        bar_left = max(1, min(bar_x, width - 2))
        bar_right = min(width - 2, bar_left + bar_thickness - 1)
        draw.rectangle((bar_left, 1, bar_right, height - 2), fill=(128, 128, 128))

    return image


def init_device(config: Config):
    LOGGER.debug(
        "serial_init_start transport=%s spi_port=%s spi_device=%s dc_pin=%s reset_pin=%s",
        config.transport,
        config.spi_port,
        config.spi_device,
        config.dc_pin,
        config.reset_pin,
    )
    if config.transport == "trace":
        serial = TraceSerial(config)
    elif config.transport == "hw":
        serial_kwargs = dict(
            port=config.spi_port,
            device=config.spi_device,
            bus_speed_hz=config.spi_speed_hz,
            gpio_DC=config.dc_pin,
            gpio_RST=config.reset_pin,
            spi_mode=config.spi_mode,
            reset_hold_time=config.reset_hold_seconds,
            reset_release_time=config.reset_release_seconds,
        )
        if config.gpio_cs_pin is not None:
            serial = gpio_cs_spi(
                gpio_CS=config.gpio_cs_pin,
                cs_high=config.cs_active_high,
                **serial_kwargs,
            )
        else:
            serial = spi(**serial_kwargs)
    else:
        raise RuntimeError(f"unsupported transport: {config.transport}")
    LOGGER.debug("serial_init_ok serial=%r", serial)

    if config.driver not in {"auto", "ssd1322", "ssd1322_nhd"}:
        raise RuntimeError(f"unsupported driver: {config.driver}")

    if config.driver == "auto":
        driver_name = "ssd1322_nhd" if (config.width, config.height) == (128, 64) else "ssd1322"
    else:
        driver_name = config.driver
    driver = ssd1322_nhd if driver_name == "ssd1322_nhd" else ssd1322
    LOGGER.debug(
        "device_init_start width=%s height=%s driver=%s",
        config.width,
        config.height,
        driver_name,
    )
    device = driver(serial, width=config.width, height=config.height)
    LOGGER.debug(
        "device_init_ok device=%r mode=%s size=%sx%s",
        device,
        getattr(device, "mode", "unknown"),
        config.width,
        config.height,
    )
    return device


def run() -> int:
    config = Config.from_env()
    LOGGER.debug("config_loaded %s", config)
    font = load_font()
    LOGGER.debug("font_ready font=%r", font)
    probe_gpio = ProbeGPIO(config)

    try:
        probe_gpio.setup()
        device = init_device(config)
        apply_post_init_profile(device, config)
    except Exception as exc:
        LOGGER.exception("init_failed reason=%s", exc)
        print(f"INIT FAILED: {exc}", file=sys.stderr)
        return 1

    try:
        LOGGER.debug("first_frame_draw_start")
        first_frame = draw_pattern(
            width=config.width,
            height=config.height,
            mode=device.mode,
            font=font,
            bar_x=None,
            bar_thickness=config.bar_thickness,
        )
        save_preview(first_frame, config.preview_output, "first_frame")
        device.display(first_frame)
        LOGGER.debug("first_frame_draw_ok")

        if config.controller_all_on_hold_seconds > 0:
            LOGGER.debug(
                "controller_all_on_start seconds=%s",
                config.controller_all_on_hold_seconds,
            )
            device.command(0xA5)
            time.sleep(config.controller_all_on_hold_seconds)
            device.command(0xA6)
            LOGGER.debug(
                "controller_all_on_end seconds=%s",
                config.controller_all_on_hold_seconds,
            )

        if config.all_on_hold_seconds > 0:
            LOGGER.debug("all_on_frame_draw_start seconds=%s", config.all_on_hold_seconds)
            all_on_frame = Image.new(device.mode, (config.width, config.height), color="white")
            save_preview(all_on_frame, config.preview_dir / "all-on-frame.png", "all_on_frame")
            device.display(all_on_frame)
            LOGGER.debug("all_on_frame_draw_ok")
            time.sleep(config.all_on_hold_seconds)
            LOGGER.debug("all_on_frame_hold_end seconds=%s", config.all_on_hold_seconds)

        if config.static_hold_seconds > 0:
            LOGGER.debug("static_frame_hold_start seconds=%s", config.static_hold_seconds)
            device.display(first_frame)
            time.sleep(config.static_hold_seconds)
            LOGGER.debug("static_frame_hold_end seconds=%s", config.static_hold_seconds)

        start = time.monotonic()
        frame = 0
        frame_interval = 1.0 / config.refresh_hz if config.refresh_hz > 0 else 0.1
        loop_exit_reason = "animation_duration_elapsed"
        LOGGER.debug(
            "animation_loop_start seconds=%s refresh_hz=%s frame_interval=%s",
            config.animation_seconds,
            config.refresh_hz,
            frame_interval,
        )
        while True:
            elapsed = time.monotonic() - start
            if elapsed >= config.animation_seconds:
                break

            travel = max(1, config.width - config.bar_thickness - 1)
            progress = elapsed / config.animation_seconds if config.animation_seconds > 0 else 1.0
            bar_x = 1 + int(progress * travel)
            image = draw_pattern(
                width=config.width,
                height=config.height,
                mode=device.mode,
                font=font,
                bar_x=bar_x,
                bar_thickness=config.bar_thickness,
            )
            LOGGER.debug(
                "refresh_start frame=%s elapsed=%.3f bar_x=%s",
                frame,
                elapsed,
                bar_x,
            )
            if config.save_each_frame:
                save_preview(image, config.preview_dir / f"frame-{frame:04d}.png", f"frame_{frame}")
            elif frame == 0:
                save_preview(image, config.preview_dir / "frame-0000.png", "frame_0")
            device.display(image)
            LOGGER.debug(
                "refresh_ok frame=%s elapsed=%.3f bar_x=%s",
                frame,
                elapsed,
                bar_x,
            )
            frame += 1
            time.sleep(frame_interval)

        print(f"LOOP EXIT: {loop_exit_reason}", flush=True)
        LOGGER.debug("animation_loop_end reason=%s frames=%s", loop_exit_reason, frame)
        if hasattr(device, "_serial_interface") and hasattr(device._serial_interface, "cleanup"):
            device._serial_interface.cleanup()
        probe_gpio.cleanup()
        return 0
    except KeyboardInterrupt:
        LOGGER.exception("runtime_interrupted")
        probe_gpio.cleanup()
        print("LOOP EXIT: keyboard_interrupt", flush=True)
        return 130
    except Exception as exc:
        LOGGER.exception("runtime_failed reason=%s", exc)
        probe_gpio.cleanup()
        print(f"LOOP EXIT: exception: {exc}", file=sys.stderr, flush=True)
        return 1


def main() -> int:
    configure_logging()
    try:
        return run()
    except Exception as exc:  # pragma: no cover
        LOGGER.error("fatal_unhandled_exception reason=%s", exc)
        traceback.print_exc()
        print(f"FATAL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
