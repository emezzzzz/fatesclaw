from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path


def _split_ints(value: str, sep: str = ",") -> tuple[int, ...]:
    if not value.strip():
        return ()
    return tuple(int(part.strip()) for part in value.split(sep) if part.strip())


def _parse_encoder_pairs(value: str) -> tuple[tuple[int, int], ...]:
    if not value.strip():
        return ()
    pairs: list[tuple[int, int]] = []
    for chunk in value.split(";"):
        parts = [part.strip() for part in chunk.split(":") if part.strip()]
        if len(parts) != 2:
            continue
        pairs.append((int(parts[0]), int(parts[1])))
    return tuple(pairs)


def _parse_oled_rotation(value: str) -> int:
    normalized = value.strip()
    mapping = {
        "0": 0,
        "1": 1,
        "2": 2,
        "3": 3,
        "90": 1,
        "180": 2,
        "270": 3,
    }
    if normalized not in mapping:
        raise ValueError("AGENT_PANEL_OLED_ROTATION must be one of 0, 1, 2, 3, 90, 180, 270")
    return mapping[normalized]


def _parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def _parse_optional_int(value: str | None) -> int | None:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    return int(stripped, 0)


def _parse_pin_pair(value: str | None) -> tuple[int, int] | None:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    chunks = [part.strip() for part in stripped.split(":") if part.strip()]
    if len(chunks) != 2:
        raise ValueError(f"invalid pin pair '{value}', expected 'A:B'")
    return int(chunks[0], 0), int(chunks[1], 0)


DEFAULT_GATEWAY_URL = "ws://127.0.0.1:18789/ws"
OPENCLAW_CONFIG_PATH = Path.home() / ".openclaw" / "openclaw.json"


@dataclass(slots=True, frozen=True)
class GatewayAuth:
    mode: str | None = None
    secret: str | None = None
    source: str = "none"

    @property
    def enabled(self) -> bool:
        return bool(self.mode and self.secret)


def _clean_secret(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _load_openclaw_gateway_settings() -> tuple[str | None, GatewayAuth]:
    try:
        payload = json.loads(OPENCLAW_CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None, GatewayAuth()

    gateway = payload.get("gateway")
    if not isinstance(gateway, dict):
        return None, GatewayAuth()

    port = gateway.get("port")
    url = None
    if isinstance(port, int) and port > 0:
        url = f"ws://127.0.0.1:{port}/ws"

    auth_payload = gateway.get("auth")
    if not isinstance(auth_payload, dict):
        return url, GatewayAuth()

    token = _clean_secret(auth_payload.get("token") if isinstance(auth_payload.get("token"), str) else None)
    password = _clean_secret(
        auth_payload.get("password") if isinstance(auth_payload.get("password"), str) else None
    )
    if token:
        return url, GatewayAuth(mode="token", secret=token, source="openclaw-config")
    if password:
        return url, GatewayAuth(mode="password", secret=password, source="openclaw-config")
    return url, GatewayAuth()


@dataclass(slots=True, frozen=True)
class ButtonConfig:
    enter_pin: int | None = None
    left_pin: int | None = None
    right_pin: int | None = None
    pull_up: bool = True
    bounce_ms: int = 25
    hold_ms: int = 600


@dataclass(slots=True, frozen=True)
class EncoderConfig:
    main_pins: tuple[int, int] | None = None
    left_pins: tuple[int, int] | None = None
    right_pins: tuple[int, int] | None = None
    pull_up: bool = True
    steps_per_detent: int = 2
    accel_window_ms: int = 120
    accel_multiplier: int = 3
    invert_main: bool = False
    invert_left: bool = False
    invert_right: bool = False


@dataclass(slots=True)
class Config:
    gateway_url: str = DEFAULT_GATEWAY_URL
    gateway_auth: GatewayAuth = field(default_factory=GatewayAuth)
    gateway_url_overridden: bool = False
    use_mock_gateway: bool = False
    log_level: str = "INFO"
    log_dir: Path = Path("./logs")
    oled_mode: str = "mock"
    oled_port: str = "i2c"
    oled_address: int = 0x3C
    oled_width: int = 128
    oled_height: int = 64
    oled_rotation: int = 0
    oled_spi_device: int = 0
    oled_spi_port: int = 0
    oled_reset_pin: int | None = None
    oled_dc_pin: int | None = None
    oled_contrast: int | None = None
    refresh_hz: int = 8
    home_animation_speed: float = 1.0
    session_log_poll_seconds: float = 0.8
    default_agent: str = "default"
    keyboard_device: str | None = None
    use_evdev_controls: bool = True
    btn_evdev_device: str | None = None
    enc_main_evdev_device: str | None = None
    enc_left_evdev_device: str | None = None
    enc_right_evdev_device: str | None = None
    btn_left_keycode: int = 1
    btn_enter_keycode: int = 2
    btn_right_keycode: int = 3
    button_pins: tuple[int, ...] = field(default_factory=tuple)
    encoder_pins: tuple[tuple[int, int], ...] = field(default_factory=tuple)
    controls_buttons: ButtonConfig = field(default_factory=ButtonConfig)
    controls_encoders: EncoderConfig = field(default_factory=EncoderConfig)
    hostname_override: str | None = None
    mock_oled_output: Path = Path("./tmp/oled-preview.png")

    @classmethod
    def from_env(cls) -> "Config":
        gateway_url_overridden = "AGENT_PANEL_GATEWAY_URL" in os.environ
        explicit_token = _clean_secret(os.getenv("OPENCLAW_GATEWAY_TOKEN"))
        explicit_password = _clean_secret(os.getenv("OPENCLAW_GATEWAY_PASSWORD"))
        if explicit_token:
            gateway_auth = GatewayAuth(mode="token", secret=explicit_token, source="env")
        elif explicit_password:
            gateway_auth = GatewayAuth(mode="password", secret=explicit_password, source="env")
        else:
            gateway_auth = GatewayAuth()

        default_gateway_url, default_gateway_auth = _load_openclaw_gateway_settings()
        gateway_url = os.getenv("AGENT_PANEL_GATEWAY_URL") or default_gateway_url or DEFAULT_GATEWAY_URL
        oled_mode = os.getenv("AGENT_PANEL_OLED_MODE", "mock")
        oled_port = os.getenv("AGENT_PANEL_OLED_PORT", "spi" if oled_mode == "ssd1322" else "i2c")

        default_oled_width = "128" if oled_mode == "ssd1322" else "128"
        default_oled_rotation = "180" if oled_mode == "ssd1322" else "0"
        default_reset_pin = "4" if oled_mode == "ssd1322" and oled_port == "spi" else ""
        default_dc_pin = "17" if oled_mode == "ssd1322" and oled_port == "spi" else ""
        legacy_button_pins = _split_ints(os.getenv("AGENT_PANEL_BUTTON_PINS", ""))
        legacy_encoder_pins = _parse_encoder_pairs(os.getenv("AGENT_PANEL_ENCODER_PINS", ""))

        button_enter_pin = _parse_optional_int(os.getenv("AGENT_PANEL_BTN_ENTER_PIN"))
        button_left_pin = _parse_optional_int(os.getenv("AGENT_PANEL_BTN_LEFT_PIN"))
        button_right_pin = _parse_optional_int(os.getenv("AGENT_PANEL_BTN_RIGHT_PIN"))
        if button_left_pin is None and len(legacy_button_pins) >= 1:
            button_left_pin = legacy_button_pins[0]
        if button_enter_pin is None and len(legacy_button_pins) >= 2:
            button_enter_pin = legacy_button_pins[1]
        if button_right_pin is None and len(legacy_button_pins) >= 3:
            button_right_pin = legacy_button_pins[2]

        main_pins = _parse_pin_pair(os.getenv("AGENT_PANEL_ENC_MAIN_PINS"))
        left_pins = _parse_pin_pair(os.getenv("AGENT_PANEL_ENC_LEFT_PINS"))
        right_pins = _parse_pin_pair(os.getenv("AGENT_PANEL_ENC_RIGHT_PINS"))
        if main_pins is None and len(legacy_encoder_pins) >= 1:
            main_pins = legacy_encoder_pins[0]
        if left_pins is None and len(legacy_encoder_pins) >= 2:
            left_pins = legacy_encoder_pins[1]
        if right_pins is None and len(legacy_encoder_pins) >= 3:
            right_pins = legacy_encoder_pins[2]

        use_mock_gateway = os.getenv("AGENT_PANEL_MOCK_GATEWAY", "0") == "1"
        if not use_mock_gateway:
            if gateway_url_overridden and not gateway_auth.enabled:
                raise ValueError(
                    "AGENT_PANEL_GATEWAY_URL is set; explicit gateway auth is required via "
                    "OPENCLAW_GATEWAY_TOKEN or OPENCLAW_GATEWAY_PASSWORD"
                )
            if not gateway_auth.enabled and not gateway_url_overridden:
                gateway_auth = default_gateway_auth

        return cls(
            gateway_url=gateway_url,
            gateway_auth=gateway_auth,
            gateway_url_overridden=gateway_url_overridden,
            use_mock_gateway=use_mock_gateway,
            log_level=os.getenv("AGENT_PANEL_LOG_LEVEL", "INFO").upper(),
            log_dir=Path(os.getenv("AGENT_PANEL_LOG_DIR", "./logs")),
            oled_mode=oled_mode,
            oled_port=oled_port,
            oled_address=int(os.getenv("AGENT_PANEL_OLED_ADDRESS", "0x3C"), 0),
            oled_width=int(os.getenv("AGENT_PANEL_OLED_WIDTH", default_oled_width)),
            oled_height=int(os.getenv("AGENT_PANEL_OLED_HEIGHT", "64")),
            oled_rotation=_parse_oled_rotation(os.getenv("AGENT_PANEL_OLED_ROTATION", default_oled_rotation)),
            oled_spi_device=int(os.getenv("AGENT_PANEL_OLED_SPI_DEVICE", "0")),
            oled_spi_port=int(os.getenv("AGENT_PANEL_OLED_SPI_PORT", "0")),
            oled_reset_pin=(
                int(os.getenv("AGENT_PANEL_OLED_RESET_PIN", default_reset_pin), 0)
                if os.getenv("AGENT_PANEL_OLED_RESET_PIN", default_reset_pin)
                else None
            ),
            oled_dc_pin=(
                int(os.getenv("AGENT_PANEL_OLED_DC_PIN", default_dc_pin), 0)
                if os.getenv("AGENT_PANEL_OLED_DC_PIN", default_dc_pin)
                else None
            ),
            oled_contrast=_parse_optional_int(os.getenv("AGENT_PANEL_OLED_CONTRAST")),
            refresh_hz=int(os.getenv("AGENT_PANEL_REFRESH_HZ", "8")),
            home_animation_speed=max(0.1, float(os.getenv("AGENT_PANEL_HOME_ANIMATION_SPEED", "1.0"))),
            session_log_poll_seconds=max(0.2, float(os.getenv("AGENT_PANEL_SESSION_LOG_POLL_SECONDS", "0.8"))),
            default_agent=(os.getenv("AGENT_PANEL_DEFAULT_AGENT", "default").strip() or "default"),
            keyboard_device=os.getenv("AGENT_PANEL_EVDEV_KEYBOARD") or None,
            use_evdev_controls=_parse_bool(os.getenv("AGENT_PANEL_USE_EVDEV_CONTROLS"), True),
            btn_evdev_device=os.getenv("AGENT_PANEL_BTN_EVDEV_DEVICE") or None,
            enc_main_evdev_device=os.getenv("AGENT_PANEL_ENC_MAIN_EVDEV_DEVICE") or None,
            enc_left_evdev_device=os.getenv("AGENT_PANEL_ENC_LEFT_EVDEV_DEVICE") or None,
            enc_right_evdev_device=os.getenv("AGENT_PANEL_ENC_RIGHT_EVDEV_DEVICE") or None,
            btn_left_keycode=int(os.getenv("AGENT_PANEL_BTN_LEFT_KEYCODE", "1")),
            btn_enter_keycode=int(os.getenv("AGENT_PANEL_BTN_ENTER_KEYCODE", "2")),
            btn_right_keycode=int(os.getenv("AGENT_PANEL_BTN_RIGHT_KEYCODE", "3")),
            button_pins=legacy_button_pins,
            encoder_pins=legacy_encoder_pins,
            controls_buttons=ButtonConfig(
                enter_pin=button_enter_pin,
                left_pin=button_left_pin,
                right_pin=button_right_pin,
                pull_up=_parse_bool(os.getenv("AGENT_PANEL_BUTTON_PULL_UP"), True),
                bounce_ms=max(1, int(os.getenv("AGENT_PANEL_BUTTON_DEBOUNCE_MS", "25"))),
                hold_ms=max(100, int(os.getenv("AGENT_PANEL_BUTTON_HOLD_MS", "600"))),
            ),
            controls_encoders=EncoderConfig(
                main_pins=main_pins,
                left_pins=left_pins,
                right_pins=right_pins,
                pull_up=_parse_bool(os.getenv("AGENT_PANEL_ENCODER_PULL_UP"), True),
                steps_per_detent=max(1, int(os.getenv("AGENT_PANEL_ENCODER_STEPS_PER_DETENT", "2"))),
                accel_window_ms=max(20, int(os.getenv("AGENT_PANEL_ENCODER_ACCEL_WINDOW_MS", "120"))),
                accel_multiplier=max(1, int(os.getenv("AGENT_PANEL_ENCODER_ACCEL_MULTIPLIER", "3"))),
                invert_main=_parse_bool(os.getenv("AGENT_PANEL_ENC_MAIN_INVERT"), False),
                invert_left=_parse_bool(os.getenv("AGENT_PANEL_ENC_LEFT_INVERT"), False),
                invert_right=_parse_bool(os.getenv("AGENT_PANEL_ENC_RIGHT_INVERT"), False),
            ),
            hostname_override=os.getenv("AGENT_PANEL_HOSTNAME") or None,
            mock_oled_output=Path(os.getenv("AGENT_PANEL_MOCK_OLED_OUTPUT", "./tmp/oled-preview.png")),
        )
