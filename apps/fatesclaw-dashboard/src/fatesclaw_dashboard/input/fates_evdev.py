from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass

from fatesclaw_dashboard.config import Config
from fatesclaw_dashboard.input.events import ControlName, ControlType, EventType, InputEvent

LOGGER = logging.getLogger(__name__)

try:
    from evdev import InputDevice, ecodes, list_devices
except ImportError:  # pragma: no cover
    InputDevice = None  # type: ignore[assignment]
    ecodes = None  # type: ignore[assignment]
    list_devices = None  # type: ignore[assignment]


@dataclass(slots=True, frozen=True)
class _ButtonCodes:
    left: int
    enter: int
    right: int


class FatesEvdevInput:
    def __init__(self, config: Config) -> None:
        self.config = config
        self._queue: asyncio.Queue[InputEvent] = asyncio.Queue()
        self._tasks: list[asyncio.Task[None]] = []
        self._encoder_accumulator: dict[ControlName, int] = {
            ControlName.ENC_MAIN: 0,
            ControlName.ENC_LEFT: 0,
            ControlName.ENC_RIGHT: 0,
        }
        self._encoder_last_emit_ms: dict[ControlName, int] = {}

    def start(self) -> None:
        if not self.config.use_evdev_controls:
            LOGGER.info("evdev_controls_disabled reason=config")
            return
        if InputDevice is None or ecodes is None or list_devices is None:
            LOGGER.info("evdev_controls_unavailable reason=evdev_missing")
            return
        try:
            self._bind_devices()
        except Exception as exc:
            LOGGER.warning("evdev_controls_bind_failed error=%s", exc)

    def _bind_devices(self) -> None:
        button_codes = _ButtonCodes(
            left=self.config.btn_left_keycode,
            enter=self.config.btn_enter_keycode,
            right=self.config.btn_right_keycode,
        )
        encoder_paths = self._resolve_encoder_paths()
        for control, path in encoder_paths.items():
            if not path:
                continue
            self._spawn_reader(path, control=control, kind="encoder", button_codes=button_codes)
        button_path = self._resolve_button_path(button_codes)
        if button_path:
            self._spawn_reader(button_path, control=None, kind="buttons", button_codes=button_codes)
        if not self._tasks:
            LOGGER.info("evdev_controls_no_devices_found")

    def _resolve_encoder_paths(self) -> dict[ControlName, str | None]:
        if self.config.enc_main_evdev_device or self.config.enc_left_evdev_device or self.config.enc_right_evdev_device:
            return {
                ControlName.ENC_MAIN: self.config.enc_main_evdev_device,
                ControlName.ENC_LEFT: self.config.enc_left_evdev_device,
                ControlName.ENC_RIGHT: self.config.enc_right_evdev_device,
            }

        candidates: dict[ControlName, str | None] = {
            ControlName.ENC_MAIN: None,
            ControlName.ENC_LEFT: None,
            ControlName.ENC_RIGHT: None,
        }
        paths = sorted(list_devices())
        for path in paths:
            try:
                device = InputDevice(path)
            except Exception:
                continue
            if not self._has_relative_axis(device):
                continue
            name = device.name.lower().strip()
            if "knob1" in name and not candidates[ControlName.ENC_MAIN]:
                candidates[ControlName.ENC_MAIN] = path
                continue
            if "knob2" in name and not candidates[ControlName.ENC_LEFT]:
                candidates[ControlName.ENC_LEFT] = path
                continue
            if ("knob3" in name or "knob0" in name) and not candidates[ControlName.ENC_RIGHT]:
                candidates[ControlName.ENC_RIGHT] = path
                continue
        return candidates

    def _resolve_button_path(self, button_codes: _ButtonCodes) -> str | None:
        if self.config.btn_evdev_device:
            return self.config.btn_evdev_device
        for path in sorted(list_devices()):
            try:
                device = InputDevice(path)
            except Exception:
                continue
            if self._has_all_button_codes(device, button_codes):
                return path
        return None

    def _spawn_reader(
        self,
        path: str,
        *,
        control: ControlName | None,
        kind: str,
        button_codes: _ButtonCodes,
    ) -> None:
        try:
            device = InputDevice(path)
        except Exception as exc:
            LOGGER.warning("evdev_open_failed path=%s error=%s", path, exc)
            return
        LOGGER.info("evdev_bound kind=%s path=%s name=%s", kind, path, device.name)
        self._tasks.append(
            asyncio.create_task(
                self._read_device(device, control=control, kind=kind, button_codes=button_codes),
                name=f"evdev-{kind}-{path.rsplit('/', 1)[-1]}",
            )
        )

    async def _read_device(
        self,
        device: InputDevice,
        *,
        control: ControlName | None,
        kind: str,
        button_codes: _ButtonCodes,
    ) -> None:
        async for event in device.async_read_loop():
            if kind == "encoder":
                if event.type == ecodes.EV_REL and event.code in self._encoder_rel_codes() and event.value:
                    mapped = self._consume_encoder_delta(control or ControlName.ENC_MAIN, int(event.value))
                    if mapped is None:
                        continue
                    await self._queue.put(mapped)
            elif kind == "buttons":
                if event.type != ecodes.EV_KEY or event.value != 1:
                    continue
                mapped = self._map_button_code(event.code, button_codes)
                if mapped is None:
                    continue
                await self._queue.put(
                    InputEvent(
                        control=mapped,
                        control_type=ControlType.BUTTON,
                        event_type=EventType.PRESS,
                        value=1,
                    )
                )

    @staticmethod
    def _map_button_code(code: int, button_codes: _ButtonCodes) -> ControlName | None:
        if code == button_codes.left:
            return ControlName.BTN_LEFT
        if code == button_codes.enter:
            return ControlName.BTN_ENTER
        if code == button_codes.right:
            return ControlName.BTN_RIGHT
        return None

    @staticmethod
    def _has_relative_axis(device: InputDevice) -> bool:
        caps = device.capabilities()
        rel_codes = caps.get(ecodes.EV_REL, [])
        return bool(set(rel_codes) & FatesEvdevInput._encoder_rel_codes())

    @staticmethod
    def _encoder_rel_codes() -> set[int]:
        codes: set[int] = set()
        for name in ("REL_X", "REL_Y", "REL_DIAL", "REL_WHEEL"):
            value = getattr(ecodes, name, None)
            if isinstance(value, int):
                codes.add(value)
        return codes

    @staticmethod
    def _has_all_button_codes(device: InputDevice, button_codes: _ButtonCodes) -> bool:
        caps = device.capabilities()
        key_codes = set(caps.get(ecodes.EV_KEY, []))
        return (
            button_codes.left in key_codes
            and button_codes.enter in key_codes
            and button_codes.right in key_codes
        )

    def _consume_encoder_delta(self, control: ControlName, delta: int) -> InputEvent | None:
        if delta == 0:
            return None
        accumulator = self._encoder_accumulator.get(control, 0)
        if accumulator and ((accumulator > 0 > delta) or (accumulator < 0 < delta)):
            accumulator = 0
        accumulator += delta
        threshold = self._control_threshold(control)
        if abs(accumulator) < threshold:
            self._encoder_accumulator[control] = accumulator
            return None

        now_ms = int(time.monotonic() * 1000)
        min_interval_ms = self._control_min_interval_ms(control)
        last_emit = self._encoder_last_emit_ms.get(control, 0)
        self._encoder_accumulator[control] = 0
        if now_ms - last_emit < min_interval_ms:
            return None
        self._encoder_last_emit_ms[control] = now_ms
        return InputEvent(
            control=control,
            control_type=ControlType.ENCODER,
            event_type=EventType.ROTATE,
            value=1 if accumulator > 0 else -1,
        )

    def _control_threshold(self, control: ControlName) -> int:
        base = max(1, self.config.controls_encoders.steps_per_detent)
        if control == ControlName.ENC_LEFT:
            # View paging is especially sensitive to encoder noise.
            return max(base * 2, 4)
        return base

    def _control_min_interval_ms(self, control: ControlName) -> int:
        base = max(8, self.config.controls_encoders.accel_window_ms // 4)
        if control == ControlName.ENC_LEFT:
            return max(base * 3, 180)
        return base

    async def events(self):
        while True:
            yield await self._queue.get()
