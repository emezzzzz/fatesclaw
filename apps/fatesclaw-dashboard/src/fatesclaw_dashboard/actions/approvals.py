from __future__ import annotations

from typing import Protocol

from fatesclaw_dashboard.gateway.protocol import build_approval_action
from fatesclaw_dashboard.state import AppState


class RawSender(Protocol):
    async def send_raw(self, payload: str) -> None: ...


async def respond_to_selected_approval(state: AppState, sender: RawSender, approved: bool) -> bool:
    snapshot = await state.snapshot()
    if not snapshot.approvals:
        return False
    current = snapshot.approvals[snapshot.selected_index]
    await sender.send_raw(build_approval_action(current.request_id, approved))
    await state.set_last_event(f"{'approved' if approved else 'rejected'} {current.request_id}")
    return True

