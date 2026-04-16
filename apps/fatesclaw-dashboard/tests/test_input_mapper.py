from __future__ import annotations

import json
import os
import unittest
from unittest.mock import patch

from fatesclaw_dashboard.input.events import ControlName, ControlType, EventType, InputEvent
from fatesclaw_dashboard.input.mapper import InputMapper
from fatesclaw_dashboard.state import AppState, ApprovalRequest, ViewName


class FakeGatewayClient:
    def __init__(self) -> None:
        self.raw_payloads: list[str] = []
        self.json_payloads: list[dict] = []

    async def send_raw(self, payload: str) -> None:
        self.raw_payloads.append(payload)

    async def send_json(self, payload: dict) -> None:
        self.json_payloads.append(payload)


class InputMapperTests(unittest.IsolatedAsyncioTestCase):
    async def test_btn_right_opens_and_runs_home_quick_action(self) -> None:
        state = AppState()
        sender = FakeGatewayClient()
        mapper = InputMapper(state, sender, on_select=self._noop, on_back=self._noop, view_turn_cooldown_ms=0)

        await mapper.handle(InputEvent(ControlName.BTN_RIGHT, ControlType.BUTTON, EventType.PRESS, value=1))
        snap = await state.snapshot()
        self.assertTrue(snap.quick_menu.open)
        self.assertEqual(snap.quick_menu.items[0], "sessions.list")

        await mapper.handle(InputEvent(ControlName.BTN_ENTER, ControlType.BUTTON, EventType.PRESS, value=1))

        self.assertEqual(sender.json_payloads, [{"type": "sessions.list"}])
        snap = await state.snapshot()
        self.assertFalse(snap.quick_menu.open)

    async def test_encoder_left_cycles_views(self) -> None:
        state = AppState()
        sender = FakeGatewayClient()
        mapper = InputMapper(state, sender, on_select=self._noop, on_back=self._noop, view_turn_cooldown_ms=0)

        await mapper.handle(InputEvent(ControlName.ENC_LEFT, ControlType.ENCODER, EventType.ROTATE, value=1))
        snap = await state.snapshot()
        self.assertEqual(snap.current_view, ViewName.CHAT)

        await mapper.handle(InputEvent(ControlName.ENC_LEFT, ControlType.ENCODER, EventType.ROTATE, value=-1))
        snap = await state.snapshot()
        self.assertEqual(snap.current_view, ViewName.HOME)

    async def test_encoder_left_respects_view_cooldown(self) -> None:
        state = AppState()
        sender = FakeGatewayClient()
        mapper = InputMapper(state, sender, on_select=self._noop, on_back=self._noop, view_turn_cooldown_ms=300)

        with patch("fatesclaw_dashboard.input.mapper.time.monotonic", side_effect=[1.0, 1.1, 1.5]):
            await mapper.handle(InputEvent(ControlName.ENC_LEFT, ControlType.ENCODER, EventType.ROTATE, value=1))
            await mapper.handle(InputEvent(ControlName.ENC_LEFT, ControlType.ENCODER, EventType.ROTATE, value=1))
            await mapper.handle(InputEvent(ControlName.ENC_LEFT, ControlType.ENCODER, EventType.ROTATE, value=1))

        snap = await state.snapshot()
        self.assertEqual(snap.current_view, ViewName.MIND)

    async def test_approvals_require_explicit_double_press(self) -> None:
        state = AppState()
        await state.replace_approvals([ApprovalRequest(request_id="apr-1", summary="Install package")])
        await state.cycle_view(5)  # home -> approvals

        sender = FakeGatewayClient()
        mapper = InputMapper(state, sender, on_select=self._noop, on_back=self._noop, view_turn_cooldown_ms=0)
        approve_event = InputEvent(ControlName.BTN_RIGHT, ControlType.BUTTON, EventType.PRESS, value=1)

        await mapper.handle(approve_event)
        snap = await state.snapshot()
        self.assertEqual(snap.approval_pending_decision, "approve")
        self.assertEqual(sender.raw_payloads, [])

        await mapper.handle(approve_event)
        self.assertEqual(len(sender.raw_payloads), 1)
        payload = json.loads(sender.raw_payloads[0])
        self.assertEqual(payload["type"], "approval.respond")
        self.assertEqual(payload["request_id"], "apr-1")
        self.assertTrue(payload["approved"])

    async def test_chat_enter_submits_typed_draft(self) -> None:
        state = AppState()
        await state.cycle_view(1)  # home -> chat
        await state.append_chat_input("hola agente")

        sender = FakeGatewayClient()
        mapper = InputMapper(state, sender, on_select=self._noop, on_back=self._noop, view_turn_cooldown_ms=0)
        previous_mode = os.environ.get("AGENT_PANEL_CHAT_SEND_MODE")
        os.environ["AGENT_PANEL_CHAT_SEND_MODE"] = "gateway"
        try:
            await mapper.handle(InputEvent(ControlName.BTN_ENTER, ControlType.BUTTON, EventType.PRESS, value=1))
        finally:
            if previous_mode is None:
                os.environ.pop("AGENT_PANEL_CHAT_SEND_MODE", None)
            else:
                os.environ["AGENT_PANEL_CHAT_SEND_MODE"] = previous_mode

        self.assertEqual(len(sender.json_payloads), 1)
        self.assertEqual(sender.json_payloads[0]["type"], "chat.send")
        self.assertEqual(sender.json_payloads[0]["text"], "hola agente")

        snap = await state.snapshot()
        self.assertEqual(snap.chat_input_draft, "")
        self.assertEqual(snap.chats[-1].role, "user")
        self.assertEqual(snap.chats[-1].text, "hola agente")

    async def test_system_text_commands_edit_chat_input(self) -> None:
        state = AppState()
        await state.cycle_view(1)  # home -> chat

        sender = FakeGatewayClient()
        mapper = InputMapper(state, sender, on_select=self._noop, on_back=self._noop, view_turn_cooldown_ms=0)
        await mapper.handle(
            InputEvent(ControlName.KEYBOARD, ControlType.SYSTEM, EventType.COMMAND, command="text_input:h")
        )
        await mapper.handle(
            InputEvent(ControlName.KEYBOARD, ControlType.SYSTEM, EventType.COMMAND, command="text_input:i")
        )
        await mapper.handle(
            InputEvent(ControlName.KEYBOARD, ControlType.SYSTEM, EventType.COMMAND, command="text_backspace")
        )

        snap = await state.snapshot()
        self.assertEqual(snap.chat_input_draft, "h")

    async def _noop(self) -> None:
        return None


if __name__ == "__main__":
    unittest.main()
