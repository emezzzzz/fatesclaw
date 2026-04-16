from __future__ import annotations

import asyncio
import logging

from fatesclaw_dashboard.config import ButtonConfig
from fatesclaw_dashboard.input.events import ControlName, ControlType, EventType, InputEvent

LOGGER = logging.getLogger(__name__)

try:
    from gpiozero import Button
except ImportError:  # pragma: no cover
    Button = None  # type: ignore[assignment]


class ButtonPanel:
    def __init__(self, config: ButtonConfig) -> None:
        self.config = config
        self._queue: asyncio.Queue[InputEvent] = asyncio.Queue()
        self._buttons: list[Button] = []

    def start(self) -> None:
        if Button is None:
            LOGGER.warning("button_panel_unavailable reason=gpiozero_missing")
            return
        bindings = (
            (ControlName.BTN_LEFT, self.config.left_pin),
            (ControlName.BTN_ENTER, self.config.enter_pin),
            (ControlName.BTN_RIGHT, self.config.right_pin),
        )
        if not any(pin is not None for _, pin in bindings):
            LOGGER.info("button_panel_disabled reason=no_button_pins")
            return

        for control, pin in bindings:
            if pin is None:
                continue
            try:
                button = Button(
                    pin,
                    pull_up=self.config.pull_up,
                    bounce_time=self.config.bounce_ms / 1000.0,
                    hold_time=self.config.hold_ms / 1000.0,
                )
                button.when_pressed = lambda control=control: self._emit(control, EventType.PRESS)
                button.when_held = lambda control=control: self._emit(control, EventType.LONG_PRESS)
                self._buttons.append(button)
                LOGGER.info(
                    "button_bound control=%s pin=%s pull_up=%s debounce_ms=%s hold_ms=%s",
                    control.value,
                    pin,
                    self.config.pull_up,
                    self.config.bounce_ms,
                    self.config.hold_ms,
                )
            except Exception as exc:
                LOGGER.warning("button_bind_failed control=%s pin=%s error=%s", control.value, pin, exc)

    def _emit(self, control: ControlName, event_type: EventType) -> None:
        self._queue.put_nowait(
            InputEvent(
                control=control,
                control_type=ControlType.BUTTON,
                event_type=event_type,
                value=1,
            )
        )

    async def events(self):
        while True:
            yield await self._queue.get()
