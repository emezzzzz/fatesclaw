from __future__ import annotations

import asyncio
import logging
import time

from fatesclaw_dashboard.config import EncoderConfig
from fatesclaw_dashboard.input.events import ControlName, ControlType, EventType, InputEvent

LOGGER = logging.getLogger(__name__)

try:
    from gpiozero import RotaryEncoder
except ImportError:  # pragma: no cover
    RotaryEncoder = None  # type: ignore[assignment]


class EncoderPanel:
    def __init__(self, config: EncoderConfig) -> None:
        self.config = config
        self._queue: asyncio.Queue[InputEvent] = asyncio.Queue()
        self._encoders: list[RotaryEncoder] = []
        self._last_turn: dict[ControlName, float] = {}

    def start(self) -> None:
        if RotaryEncoder is None:
            LOGGER.warning("encoder_panel_unavailable reason=gpiozero_missing")
            return
        bindings = (
            (ControlName.ENC_MAIN, self.config.main_pins, self.config.invert_main),
            (ControlName.ENC_LEFT, self.config.left_pins, self.config.invert_left),
            (ControlName.ENC_RIGHT, self.config.right_pins, self.config.invert_right),
        )
        if not any(pins is not None for _, pins, _ in bindings):
            LOGGER.info("encoder_panel_disabled reason=no_encoder_pins")
            return

        for control, pair, invert in bindings:
            if pair is None:
                continue
            if not isinstance(pair, (tuple, list)) or len(pair) != 2:
                LOGGER.warning("encoder_bind_skipped control=%s reason=invalid_pin_pair value=%r", control.value, pair)
                continue
            a_pin, b_pin = pair
            try:
                encoder = RotaryEncoder(
                    a_pin,
                    b_pin,
                    wrap=False,
                    max_steps=0,
                    threshold_steps=self.config.steps_per_detent,
                )
                encoder.when_rotated_clockwise = lambda control=control, invert=invert: self._emit(
                    control, -1 if invert else 1
                )
                encoder.when_rotated_counter_clockwise = lambda control=control, invert=invert: self._emit(
                    control, 1 if invert else -1
                )
                self._encoders.append(encoder)
                LOGGER.info(
                    "encoder_bound control=%s a=%s b=%s pull_up=%s invert=%s steps_per_detent=%s",
                    control.value,
                    a_pin,
                    b_pin,
                    self.config.pull_up,
                    invert,
                    self.config.steps_per_detent,
                )
            except Exception as exc:
                LOGGER.warning(
                    "encoder_bind_failed control=%s a=%s b=%s error=%s",
                    control.value,
                    a_pin,
                    b_pin,
                    exc,
                )

    def _emit(self, control: ControlName, direction: int) -> None:
        now = time.monotonic()
        last = self._last_turn.get(control)
        delta = direction
        if last is not None and (now - last) * 1000.0 <= self.config.accel_window_ms:
            delta *= self.config.accel_multiplier
        self._last_turn[control] = now
        self._queue.put_nowait(
            InputEvent(
                control=control,
                control_type=ControlType.ENCODER,
                event_type=EventType.ROTATE,
                value=delta,
            )
        )

    async def events(self):
        while True:
            yield await self._queue.get()
