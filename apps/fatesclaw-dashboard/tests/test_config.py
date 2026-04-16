from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fatesclaw_dashboard import config as config_module


class ConfigFromEnvTests(unittest.TestCase):
    def test_override_requires_explicit_auth(self) -> None:
        with patch.dict("os.environ", {"AGENT_PANEL_GATEWAY_URL": "ws://gateway.example/ws"}, clear=True):
            with self.assertRaisesRegex(ValueError, "explicit gateway auth is required"):
                config_module.Config.from_env()

    def test_token_is_preferred_over_password(self) -> None:
        env = {
            "AGENT_PANEL_GATEWAY_URL": "ws://gateway.example/ws",
            "OPENCLAW_GATEWAY_TOKEN": "token-value",
            "OPENCLAW_GATEWAY_PASSWORD": "password-value",
        }
        with patch.dict("os.environ", env, clear=True):
            config = config_module.Config.from_env()

        self.assertEqual(config.gateway_auth.mode, "token")
        self.assertEqual(config.gateway_auth.secret, "token-value")
        self.assertEqual(config.gateway_auth.source, "env")

    def test_default_gateway_uses_local_openclaw_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "openclaw.json"
            config_path.write_text(
                json.dumps({"gateway": {"port": 18789, "auth": {"mode": "token", "token": "local-token"}}}),
                encoding="utf-8",
            )
            with patch.object(config_module, "OPENCLAW_CONFIG_PATH", config_path):
                with patch.dict("os.environ", {}, clear=True):
                    config = config_module.Config.from_env()

        self.assertEqual(config.gateway_url, "ws://127.0.0.1:18789/ws")
        self.assertEqual(config.gateway_auth.mode, "token")
        self.assertEqual(config.gateway_auth.secret, "local-token")
        self.assertEqual(config.gateway_auth.source, "openclaw-config")

    def test_mock_mode_skips_override_auth_requirement(self) -> None:
        env = {
            "AGENT_PANEL_GATEWAY_URL": "ws://gateway.example/ws",
            "AGENT_PANEL_MOCK_GATEWAY": "1",
        }
        with patch.dict("os.environ", env, clear=True):
            config = config_module.Config.from_env()

        self.assertTrue(config.use_mock_gateway)
        self.assertFalse(config.gateway_auth.enabled)

    def test_ssd1322_defaults_match_fates_overlay(self) -> None:
        env = {
            "AGENT_PANEL_OLED_MODE": "ssd1322",
            "AGENT_PANEL_MOCK_GATEWAY": "1",
        }
        with patch.dict("os.environ", env, clear=True):
            config = config_module.Config.from_env()

        self.assertEqual(config.oled_port, "spi")
        self.assertEqual(config.oled_width, 128)
        self.assertEqual(config.oled_height, 64)
        self.assertEqual(config.oled_rotation, 2)
        self.assertEqual(config.oled_dc_pin, 17)
        self.assertEqual(config.oled_reset_pin, 4)

    def test_oled_rotation_accepts_degrees(self) -> None:
        env = {
            "AGENT_PANEL_OLED_MODE": "ssd1322",
            "AGENT_PANEL_MOCK_GATEWAY": "1",
            "AGENT_PANEL_OLED_ROTATION": "180",
        }
        with patch.dict("os.environ", env, clear=True):
            config = config_module.Config.from_env()

        self.assertEqual(config.oled_rotation, 2)

    def test_logical_controls_fallback_to_legacy_pin_lists(self) -> None:
        env = {
            "AGENT_PANEL_MOCK_GATEWAY": "1",
            "AGENT_PANEL_BUTTON_PINS": "5,6,13",
            "AGENT_PANEL_ENCODER_PINS": "17:27;22:23;24:25",
        }
        with patch.dict("os.environ", env, clear=True):
            config = config_module.Config.from_env()

        self.assertEqual(config.controls_buttons.left_pin, 5)
        self.assertEqual(config.controls_buttons.enter_pin, 6)
        self.assertEqual(config.controls_buttons.right_pin, 13)
        self.assertEqual(config.controls_encoders.main_pins, (17, 27))
        self.assertEqual(config.controls_encoders.left_pins, (22, 23))
        self.assertEqual(config.controls_encoders.right_pins, (24, 25))

    def test_logical_control_env_overrides_legacy_lists(self) -> None:
        env = {
            "AGENT_PANEL_MOCK_GATEWAY": "1",
            "AGENT_PANEL_BUTTON_PINS": "5,6,13",
            "AGENT_PANEL_ENCODER_PINS": "17:27;22:23;24:25",
            "AGENT_PANEL_BTN_ENTER_PIN": "26",
            "AGENT_PANEL_BTN_LEFT_PIN": "16",
            "AGENT_PANEL_BTN_RIGHT_PIN": "20",
            "AGENT_PANEL_ENC_MAIN_PINS": "6:12",
            "AGENT_PANEL_ENC_LEFT_PINS": "13:19",
            "AGENT_PANEL_ENC_RIGHT_PINS": "21:22",
            "AGENT_PANEL_ENC_RIGHT_INVERT": "1",
        }
        with patch.dict("os.environ", env, clear=True):
            config = config_module.Config.from_env()

        self.assertEqual(config.controls_buttons.left_pin, 16)
        self.assertEqual(config.controls_buttons.enter_pin, 26)
        self.assertEqual(config.controls_buttons.right_pin, 20)
        self.assertEqual(config.controls_encoders.main_pins, (6, 12))
        self.assertEqual(config.controls_encoders.left_pins, (13, 19))
        self.assertEqual(config.controls_encoders.right_pins, (21, 22))
        self.assertTrue(config.controls_encoders.invert_right)

    def test_evdev_control_defaults(self) -> None:
        env = {"AGENT_PANEL_MOCK_GATEWAY": "1"}
        with patch.dict("os.environ", env, clear=True):
            config = config_module.Config.from_env()

        self.assertTrue(config.use_evdev_controls)
        self.assertEqual(config.btn_left_keycode, 1)
        self.assertEqual(config.btn_enter_keycode, 2)
        self.assertEqual(config.btn_right_keycode, 3)


if __name__ == "__main__":
    unittest.main()
