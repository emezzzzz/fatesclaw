from __future__ import annotations

import asyncio
import logging
import string
import sys

from fatesclaw_dashboard.input.events import ControlName, ControlType, EventType, InputEvent

LOGGER = logging.getLogger(__name__)

try:
    from evdev import InputDevice, ecodes, list_devices
except ImportError:  # pragma: no cover
    InputDevice = None  # type: ignore[assignment]
    ecodes = None  # type: ignore[assignment]
    list_devices = None  # type: ignore[assignment]


STDIN_KEYMAP: dict[str, InputEvent] = {
    "h": InputEvent(ControlName.ENC_LEFT, ControlType.ENCODER, EventType.ROTATE, value=-1),
    "l": InputEvent(ControlName.ENC_LEFT, ControlType.ENCODER, EventType.ROTATE, value=1),
    "j": InputEvent(ControlName.ENC_MAIN, ControlType.ENCODER, EventType.ROTATE, value=1),
    "k": InputEvent(ControlName.ENC_MAIN, ControlType.ENCODER, EventType.ROTATE, value=-1),
    "u": InputEvent(ControlName.ENC_RIGHT, ControlType.ENCODER, EventType.ROTATE, value=-1),
    "o": InputEvent(ControlName.ENC_RIGHT, ControlType.ENCODER, EventType.ROTATE, value=1),
    "b": InputEvent(ControlName.BTN_LEFT, ControlType.BUTTON, EventType.PRESS, value=1),
    "m": InputEvent(ControlName.BTN_RIGHT, ControlType.BUTTON, EventType.PRESS, value=1),
    "\n": InputEvent(ControlName.BTN_ENTER, ControlType.BUTTON, EventType.PRESS, value=1),
    "\r": InputEvent(ControlName.BTN_ENTER, ControlType.BUTTON, EventType.PRESS, value=1),
    "H": InputEvent(ControlName.KEYBOARD, ControlType.SYSTEM, EventType.COMMAND, command="home"),
    "q": InputEvent(ControlName.KEYBOARD, ControlType.SYSTEM, EventType.COMMAND, command="quit"),
}


EVDEV_KEYMAP: dict[str, InputEvent] = {
    "KEY_LEFT": InputEvent(ControlName.ENC_LEFT, ControlType.ENCODER, EventType.ROTATE, value=-1),
    "KEY_RIGHT": InputEvent(ControlName.ENC_LEFT, ControlType.ENCODER, EventType.ROTATE, value=1),
    "KEY_DOWN": InputEvent(ControlName.ENC_MAIN, ControlType.ENCODER, EventType.ROTATE, value=1),
    "KEY_UP": InputEvent(ControlName.ENC_MAIN, ControlType.ENCODER, EventType.ROTATE, value=-1),
    "KEY_PAGEUP": InputEvent(ControlName.ENC_RIGHT, ControlType.ENCODER, EventType.ROTATE, value=-1),
    "KEY_PAGEDOWN": InputEvent(ControlName.ENC_RIGHT, ControlType.ENCODER, EventType.ROTATE, value=1),
    "KEY_ENTER": InputEvent(ControlName.BTN_ENTER, ControlType.BUTTON, EventType.PRESS, value=1),
    "KEY_ESC": InputEvent(ControlName.BTN_LEFT, ControlType.BUTTON, EventType.PRESS, value=1),
    "KEY_MENU": InputEvent(ControlName.BTN_RIGHT, ControlType.BUTTON, EventType.PRESS, value=1),
    "KEY_HOME": InputEvent(ControlName.KEYBOARD, ControlType.SYSTEM, EventType.COMMAND, command="home"),
}


EVDEV_TEXT_MAP: dict[str, str] = {
    **{f"KEY_{chr(code)}": chr(code + 32) for code in range(ord("A"), ord("Z") + 1)},
    "KEY_1": "1",
    "KEY_2": "2",
    "KEY_3": "3",
    "KEY_4": "4",
    "KEY_5": "5",
    "KEY_6": "6",
    "KEY_7": "7",
    "KEY_8": "8",
    "KEY_9": "9",
    "KEY_0": "0",
    "KEY_SPACE": " ",
    "KEY_MINUS": "-",
    "KEY_EQUAL": "=",
    "KEY_LEFTBRACE": "[",
    "KEY_RIGHTBRACE": "]",
    "KEY_BACKSLASH": "\\",
    "KEY_SEMICOLON": ";",
    "KEY_APOSTROPHE": "'",
    "KEY_GRAVE": "`",
    "KEY_COMMA": ",",
    "KEY_DOT": ".",
    "KEY_SLASH": "/",
}


EVDEV_TEXT_SHIFT_MAP: dict[str, str] = {
    **{f"KEY_{chr(code)}": chr(code) for code in range(ord("A"), ord("Z") + 1)},
    "KEY_1": "!",
    "KEY_2": "@",
    "KEY_3": "#",
    "KEY_4": "$",
    "KEY_5": "%",
    "KEY_6": "^",
    "KEY_7": "&",
    "KEY_8": "*",
    "KEY_9": "(",
    "KEY_0": ")",
    "KEY_MINUS": "_",
    "KEY_EQUAL": "+",
    "KEY_LEFTBRACE": "{",
    "KEY_RIGHTBRACE": "}",
    "KEY_BACKSLASH": "|",
    "KEY_SEMICOLON": ":",
    "KEY_APOSTROPHE": "\"",
    "KEY_GRAVE": "~",
    "KEY_COMMA": "<",
    "KEY_DOT": ">",
    "KEY_SLASH": "?",
}


class KeyboardInput:
    def __init__(self, device_path: str | None = None) -> None:
        self.device_path = device_path

    async def events(self):
        if InputDevice is not None and ecodes is not None:
            for device_path in self._candidate_evdev_paths():
                try:
                    async for event in self._events_from_evdev(device_path):
                        yield event
                    return
                except Exception as exc:
                    LOGGER.warning(
                        "keyboard_evdev_open_failed path=%s error=%s fallback=%s",
                        device_path,
                        exc,
                        "stdin" if sys.stdin.isatty() else "idle",
                    )
        if sys.stdin.isatty():
            async for event in self._events_from_stdin():
                yield event
            return
        while True:
            await asyncio.sleep(3600)

    def _candidate_evdev_paths(self) -> list[str]:
        paths: list[str] = []
        configured = (self.device_path or "").strip()
        if configured and not _is_placeholder_device_path(configured):
            paths.append(configured)
        auto = self._discover_evdev_keyboard_path(excluded=set(paths))
        if auto:
            paths.append(auto)
        return paths

    def _discover_evdev_keyboard_path(self, *, excluded: set[str]) -> str | None:
        if InputDevice is None or ecodes is None or list_devices is None:
            return None
        for path in sorted(list_devices()):
            if path in excluded:
                continue
            try:
                device = InputDevice(path)
            except Exception as exc:
                LOGGER.debug("keyboard_evdev_probe_failed path=%s error=%s", path, exc)
                continue
            try:
                if _is_keyboard_candidate(device):
                    LOGGER.info("keyboard_evdev_autodetected path=%s name=%s", path, device.name)
                    return path
            finally:
                try:
                    device.close()
                except Exception:
                    pass
        return None

    async def _events_from_stdin(self):
        loop = asyncio.get_running_loop()
        while True:
            char = await loop.run_in_executor(None, sys.stdin.read, 1)
            if char == "":
                await asyncio.sleep(0.2)
                continue
            event = STDIN_KEYMAP.get(char)
            if event:
                yield event
                continue
            if char in {"\x08", "\x7f"}:
                yield InputEvent(
                    ControlName.KEYBOARD,
                    ControlType.SYSTEM,
                    EventType.COMMAND,
                    command="text_backspace",
                )
                continue
            if _is_printable_text_char(char):
                yield InputEvent(
                    ControlName.KEYBOARD,
                    ControlType.SYSTEM,
                    EventType.COMMAND,
                    command=f"text_input:{char}",
                )

    async def _events_from_evdev(self, device_path: str):
        device = InputDevice(device_path)
        LOGGER.info("keyboard_evdev_open path=%s name=%s", device_path, device.name)
        shift_down = False
        async for event in device.async_read_loop():
            if event.type != ecodes.EV_KEY:
                continue
            key_name = ecodes.KEY[event.code]
            if key_name in {"KEY_LEFTSHIFT", "KEY_RIGHTSHIFT"}:
                if event.value == 1:
                    shift_down = True
                elif event.value == 0:
                    shift_down = False
                continue
            if event.value != 1:
                continue
            mapped = EVDEV_KEYMAP.get(key_name)
            if mapped:
                yield mapped
                continue
            if key_name == "KEY_BACKSPACE":
                yield InputEvent(
                    ControlName.KEYBOARD,
                    ControlType.SYSTEM,
                    EventType.COMMAND,
                    command="text_backspace",
                )
                continue
            text_char = _map_evdev_text_key(key_name, shift_down)
            if text_char:
                yield InputEvent(
                    ControlName.KEYBOARD,
                    ControlType.SYSTEM,
                    EventType.COMMAND,
                    command=f"text_input:{text_char}",
                )


def _map_evdev_text_key(key_name: str, shift_down: bool) -> str | None:
    if shift_down and key_name in EVDEV_TEXT_SHIFT_MAP:
        return EVDEV_TEXT_SHIFT_MAP[key_name]
    return EVDEV_TEXT_MAP.get(key_name)


def _is_placeholder_device_path(path: str) -> bool:
    lowered = path.strip().lower()
    return lowered.endswith("eventx") or lowered.endswith("eventn")


def _is_printable_text_char(char: str) -> bool:
    if len(char) != 1:
        return False
    if char in {"\r", "\n", "\t"}:
        return False
    return char in string.printable


def _is_keyboard_candidate(device: InputDevice) -> bool:
    if ecodes is None:
        return False
    try:
        caps = device.capabilities()
    except Exception:
        return False
    key_codes = caps.get(ecodes.EV_KEY, [])
    normalized: set[int] = set()
    for item in key_codes:
        if isinstance(item, int):
            normalized.add(item)
        elif isinstance(item, tuple) and item and isinstance(item[0], int):
            normalized.add(item[0])
    return (
        ecodes.KEY_A in normalized
        and ecodes.KEY_Z in normalized
        and ecodes.KEY_ENTER in normalized
    )
