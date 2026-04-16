from __future__ import annotations

from typing import Protocol


class JsonSender(Protocol):
    async def send_json(self, payload: dict) -> None: ...


async def send_command(sender: JsonSender, command: str) -> None:
    await sender.send_json({"type": "command.run", "command": command})

