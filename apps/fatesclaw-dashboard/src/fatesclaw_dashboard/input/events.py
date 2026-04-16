from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ControlType(str, Enum):
    BUTTON = "button"
    ENCODER = "encoder"
    SYSTEM = "system"


class ControlName(str, Enum):
    BTN_ENTER = "btn_enter"
    BTN_LEFT = "btn_left"
    BTN_RIGHT = "btn_right"
    ENC_MAIN = "enc_main"
    ENC_LEFT = "enc_left"
    ENC_RIGHT = "enc_right"
    KEYBOARD = "keyboard"


class EventType(str, Enum):
    PRESS = "press"
    LONG_PRESS = "long_press"
    ROTATE = "rotate"
    COMMAND = "command"


@dataclass(slots=True)
class InputEvent:
    control: ControlName
    control_type: ControlType
    event_type: EventType
    value: int = 0
    command: str | None = None
