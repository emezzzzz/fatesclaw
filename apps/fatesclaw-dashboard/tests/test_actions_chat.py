from __future__ import annotations

import os
import unittest

from fatesclaw_dashboard.actions.chat import _chat_send_mode


class ChatActionTests(unittest.TestCase):
    def test_chat_send_mode_defaults_local(self) -> None:
        previous = os.environ.pop("AGENT_PANEL_CHAT_SEND_MODE", None)
        try:
            self.assertEqual(_chat_send_mode(), "local")
        finally:
            if previous is not None:
                os.environ["AGENT_PANEL_CHAT_SEND_MODE"] = previous

    def test_chat_send_mode_allows_known_values(self) -> None:
        previous = os.environ.get("AGENT_PANEL_CHAT_SEND_MODE")
        try:
            os.environ["AGENT_PANEL_CHAT_SEND_MODE"] = "gateway"
            self.assertEqual(_chat_send_mode(), "gateway")
            os.environ["AGENT_PANEL_CHAT_SEND_MODE"] = "auto"
            self.assertEqual(_chat_send_mode(), "auto")
            os.environ["AGENT_PANEL_CHAT_SEND_MODE"] = "LOCAL"
            self.assertEqual(_chat_send_mode(), "local")
        finally:
            if previous is None:
                os.environ.pop("AGENT_PANEL_CHAT_SEND_MODE", None)
            else:
                os.environ["AGENT_PANEL_CHAT_SEND_MODE"] = previous


if __name__ == "__main__":
    unittest.main()

