from __future__ import annotations

import unittest
from unittest.mock import patch

from fatesclaw_dashboard.config import Config
from fatesclaw_dashboard.input.events import ControlName
from fatesclaw_dashboard.input.fates_evdev import FatesEvdevInput, _ButtonCodes


class FatesEvdevMappingTests(unittest.TestCase):
    def test_button_code_mapping(self) -> None:
        codes = _ButtonCodes(left=1, enter=2, right=3)
        self.assertEqual(FatesEvdevInput._map_button_code(1, codes), ControlName.BTN_LEFT)
        self.assertEqual(FatesEvdevInput._map_button_code(2, codes), ControlName.BTN_ENTER)
        self.assertEqual(FatesEvdevInput._map_button_code(3, codes), ControlName.BTN_RIGHT)
        self.assertIsNone(FatesEvdevInput._map_button_code(99, codes))

    def test_encoder_left_requires_stricter_threshold(self) -> None:
        panel = FatesEvdevInput(Config())
        self.assertIsNone(panel._consume_encoder_delta(ControlName.ENC_LEFT, 1))
        self.assertIsNone(panel._consume_encoder_delta(ControlName.ENC_LEFT, 1))
        self.assertIsNone(panel._consume_encoder_delta(ControlName.ENC_LEFT, 1))
        with patch("fatesclaw_dashboard.input.fates_evdev.time.monotonic", return_value=1.0):
            event = panel._consume_encoder_delta(ControlName.ENC_LEFT, 1)
        self.assertIsNotNone(event)
        assert event is not None
        self.assertEqual(event.value, 1)

    def test_encoder_left_respects_min_emit_interval(self) -> None:
        panel = FatesEvdevInput(Config())
        # First detent emits.
        with patch("fatesclaw_dashboard.input.fates_evdev.time.monotonic", return_value=1.0):
            for _ in range(3):
                self.assertIsNone(panel._consume_encoder_delta(ControlName.ENC_LEFT, 1))
            self.assertIsNotNone(panel._consume_encoder_delta(ControlName.ENC_LEFT, 1))
        # Second detent arrives too quickly and is dropped.
        with patch("fatesclaw_dashboard.input.fates_evdev.time.monotonic", return_value=1.05):
            for _ in range(3):
                self.assertIsNone(panel._consume_encoder_delta(ControlName.ENC_LEFT, 1))
            self.assertIsNone(panel._consume_encoder_delta(ControlName.ENC_LEFT, 1))


if __name__ == "__main__":
    unittest.main()
