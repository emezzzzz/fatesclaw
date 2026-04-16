from __future__ import annotations

from typing import Protocol


class JsonSender(Protocol):
    async def send_json(self, payload: dict) -> None: ...


async def request_jobs_refresh(sender: JsonSender) -> None:
    await sender.send_json({"type": "cron.list"})
