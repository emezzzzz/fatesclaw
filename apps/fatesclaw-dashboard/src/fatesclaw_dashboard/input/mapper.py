from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable

from fatesclaw_dashboard.actions.approvals import respond_to_selected_approval
from fatesclaw_dashboard.actions.chat import request_transcript_refresh, send_chat_text
from fatesclaw_dashboard.actions.cron import request_jobs_refresh
from fatesclaw_dashboard.actions.sessions import request_session_refresh
from fatesclaw_dashboard.input.events import ControlName, ControlType, EventType, InputEvent
from fatesclaw_dashboard.state import AppState, ViewName

LOGGER = logging.getLogger(__name__)


ActionFn = Callable[[], Awaitable[None]]


class InputMapper:
    def __init__(
        self,
        state: AppState,
        gateway_client,
        on_select: Callable[[], Awaitable[None]],
        on_back: Callable[[], Awaitable[None]],
        *,
        view_turn_cooldown_ms: int = 300,
    ) -> None:
        self.state = state
        self.gateway_client = gateway_client
        self.on_select = on_select
        self.on_back = on_back
        self.view_turn_cooldown_ms = max(0, view_turn_cooldown_ms)
        self._last_view_turn_ms = 0

    async def handle(self, event: InputEvent) -> None:
        LOGGER.debug(
            "input control=%s type=%s event=%s value=%s command=%s",
            event.control.value,
            event.control_type.value,
            event.event_type.value,
            event.value,
            event.command,
        )
        if event.control_type == ControlType.SYSTEM:
            await self._handle_system_command(event.command)
            return

        if event.control_type == ControlType.ENCODER and event.event_type == EventType.ROTATE:
            await self._handle_encoder_turn(event.control, event.value)
            return

        if event.control_type == ControlType.BUTTON and event.event_type in {EventType.PRESS, EventType.LONG_PRESS}:
            await self._handle_button(event.control, event.event_type)

    async def _handle_system_command(self, command: str | None) -> None:
        if not command:
            return
        if command == "quit":
            await self.state.request_shutdown()
            return
        if command == "home":
            await self.state.select_home()
            return
        if command.startswith("text_input:"):
            char = command.split(":", 1)[1]
            snapshot = await self.state.snapshot()
            if snapshot.current_view == ViewName.CHAT:
                await self.state.append_chat_input(char, agent=snapshot.selected_agent)
            return
        if command == "text_backspace":
            snapshot = await self.state.snapshot()
            if snapshot.current_view == ViewName.CHAT:
                await self.state.backspace_chat_input(agent=snapshot.selected_agent)
            return
        if command == "text_clear":
            snapshot = await self.state.snapshot()
            if snapshot.current_view == ViewName.CHAT:
                await self.state.clear_chat_input(agent=snapshot.selected_agent)
            return
        if command == "text_submit":
            await self._submit_chat_input()
            return

    async def _handle_encoder_turn(self, control: ControlName, delta: int) -> None:
        if delta == 0:
            return
        step = 1 if delta > 0 else -1
        magnitude = abs(delta)
        snapshot = await self.state.snapshot()
        if snapshot.quick_menu.open:
            await self.state.cycle_quick_menu(step)
            return

        if control == ControlName.ENC_LEFT:
            now_ms = int(time.monotonic() * 1000)
            if now_ms - self._last_view_turn_ms < self.view_turn_cooldown_ms:
                return
            self._last_view_turn_ms = now_ms
            await self.state.cycle_view(step)
            return

        if control == ControlName.ENC_MAIN:
            await self.state.move_selection(step * magnitude)
            return

        if control == ControlName.ENC_RIGHT:
            before = snapshot.view_cursors.get(snapshot.current_view)
            before_index = before.context_index if before else 0
            after_index = await self.state.adjust_context(step)
            if after_index != before_index:
                await self.state.set_last_event(f"context {step:+d} on {snapshot.current_view.value}")

    async def _handle_button(self, control: ControlName, event_type: EventType) -> None:
        snapshot = await self.state.snapshot()
        if event_type == EventType.LONG_PRESS and control == ControlName.BTN_ENTER:
            await self.state.select_home()
            return

        if snapshot.quick_menu.open:
            await self._handle_quick_menu_button(control)
            return

        if control == ControlName.BTN_LEFT:
            if snapshot.current_view == ViewName.APPROVALS and snapshot.approvals:
                await self._handle_approval_decision(approved=False)
                return
            await self.on_back()
            return

        if control == ControlName.BTN_ENTER:
            if await self._submit_chat_input():
                return
            await self.on_select()
            return

        if control == ControlName.BTN_RIGHT:
            if snapshot.current_view == ViewName.APPROVALS and snapshot.approvals:
                await self._handle_approval_decision(approved=True)
                return
            await self._open_quick_actions(snapshot.current_view)

    async def _handle_quick_menu_button(self, control: ControlName) -> None:
        if control == ControlName.BTN_LEFT:
            await self.state.close_quick_menu()
            await self.state.set_last_event("menu closed")
            return
        if control == ControlName.BTN_RIGHT:
            await self._run_selected_quick_action()
            return
        if control == ControlName.BTN_ENTER:
            await self._run_selected_quick_action()

    async def _handle_approval_decision(self, *, approved: bool) -> None:
        decision = "approve" if approved else "reject"
        confirmed = await self.state.arm_approval_decision(decision)
        if not confirmed:
            await self.state.set_last_event(f"{decision} armed; press again to confirm")
            return
        ok = await respond_to_selected_approval(self.state, self.gateway_client, approved=approved)
        if ok:
            await self.state.set_last_event(f"{decision}d selected approval")
        else:
            await self.state.set_last_event("no approval selected")

    async def _open_quick_actions(self, view: ViewName) -> None:
        items: list[str]
        if view == ViewName.CHAT:
            items = ["chat.history", "sessions.list"]
        elif view == ViewName.MIND:
            items = ["chat.history", "sessions.list"]
        elif view == ViewName.AGENTS:
            items = ["sessions.list"]
        elif view == ViewName.JOBS:
            items = ["cron.list", "sessions.list"]
        elif view == ViewName.SYSTEM:
            items = ["sessions.list", "cron.list", "chat.history"]
        elif view == ViewName.HOME:
            items = ["sessions.list", "cron.list", "chat.history"]
        elif view == ViewName.APPROVALS:
            items = ["chat.history", "sessions.list"]
        else:
            items = []
        await self.state.open_quick_menu("Actions", items)
        if items:
            await self.state.set_last_event("menu opened")

    async def _run_selected_quick_action(self) -> None:
        action = await self.state.selected_quick_menu_item()
        if not action:
            await self.state.close_quick_menu()
            return
        if action == "chat.history":
            await request_transcript_refresh(self.gateway_client)
        elif action == "cron.list":
            await request_jobs_refresh(self.gateway_client)
        elif action == "sessions.list":
            await request_session_refresh(self.gateway_client)
        await self.state.close_quick_menu()
        await self.state.set_last_event(f"ran {action}")

    async def _submit_chat_input(self) -> bool:
        snapshot = await self.state.snapshot()
        if snapshot.current_view != ViewName.CHAT:
            return False
        draft = snapshot.chat_input_draft.strip()
        if not draft:
            return False
        await send_chat_text(
            self.gateway_client,
            draft,
            agent=snapshot.selected_agent,
            session=snapshot.active_session,
        )
        await self.state.add_chat(
            role="user",
            text=draft,
            streaming=False,
            agent=snapshot.selected_agent,
        )
        await self.state.clear_chat_input(agent=snapshot.selected_agent)
        await self.state.set_last_event(f"sent: {draft[:40]}")
        return True
