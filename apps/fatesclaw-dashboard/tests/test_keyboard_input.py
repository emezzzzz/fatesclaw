from __future__ import annotations

import asyncio
import unittest
from unittest.mock import patch

from fatesclaw_dashboard.input.keyboard import (
    KeyboardInput,
    _is_placeholder_device_path,
    _map_evdev_text_key,
)


class KeyboardInputTests(unittest.TestCase):
    def test_maps_plain_keys(self) -> None:
        self.assertEqual(_map_evdev_text_key("KEY_A", False), "a")
        self.assertEqual(_map_evdev_text_key("KEY_1", False), "1")
        self.assertEqual(_map_evdev_text_key("KEY_SPACE", False), " ")

    def test_maps_shifted_keys(self) -> None:
        self.assertEqual(_map_evdev_text_key("KEY_A", True), "A")
        self.assertEqual(_map_evdev_text_key("KEY_1", True), "!")
        self.assertEqual(_map_evdev_text_key("KEY_SLASH", True), "?")


class KeyboardInputFallbackTests(unittest.IsolatedAsyncioTestCase):
    async def test_invalid_evdev_path_does_not_crash(self) -> None:
        keyboard = KeyboardInput("/dev/input/eventX")
        with patch("fatesclaw_dashboard.input.keyboard.InputDevice", side_effect=FileNotFoundError("no device")):
            with patch("fatesclaw_dashboard.input.keyboard.sys.stdin.isatty", return_value=False):
                stream = keyboard.events()
                with self.assertRaises(asyncio.TimeoutError):
                    await asyncio.wait_for(anext(stream), timeout=0.15)

    def test_placeholder_device_path_detection(self) -> None:
        self.assertTrue(_is_placeholder_device_path("/dev/input/eventX"))
        self.assertTrue(_is_placeholder_device_path("/dev/input/eventN"))
        self.assertFalse(_is_placeholder_device_path("/dev/input/event7"))


if __name__ == "__main__":
    unittest.main()
