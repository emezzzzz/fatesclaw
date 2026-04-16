from __future__ import annotations

import asyncio
import logging
import os
import shlex
import shutil
from pathlib import Path
from typing import Protocol

LOGGER = logging.getLogger(__name__)


class RawSender(Protocol):
    async def send_raw(self, payload: str) -> None: ...


class JsonSender(Protocol):
    async def send_json(self, payload: dict) -> None: ...


async def request_transcript_refresh(sender: RawSender) -> None:
    await sender.send_raw('{"type":"chat.history"}')


async def send_chat_text(
    sender: JsonSender,
    text: str,
    *,
    agent: str | None = None,
    session: str | None = None,
) -> None:
    mode = _chat_send_mode()
    if mode in {"local", "auto"}:
        dispatched = await _dispatch_local_chat_send(text=text, agent=agent, session=session)
        if dispatched:
            return
        if mode == "local":
            LOGGER.warning("chat_send_local_unavailable fallback=gateway")

    payload: dict[str, str] = {
        "type": "chat.send",
        "text": text,
        "message": text,
    }
    if agent:
        payload["agent"] = agent
        payload["agentId"] = agent
    if session and session != "-":
        payload["session"] = session
        payload["session_id"] = session
    await sender.send_json(payload)


def _chat_send_mode() -> str:
    value = os.getenv("AGENT_PANEL_CHAT_SEND_MODE", "local").strip().lower()
    if value in {"local", "gateway", "auto"}:
        return value
    return "local"


def _resolve_openclaw_cli_path() -> str | None:
    from_path = shutil.which("openclaw")
    if from_path:
        return from_path
    fallback = Path.home() / ".npm-global" / "bin" / "openclaw"
    if fallback.exists():
        return str(fallback)
    return None


async def _dispatch_local_chat_send(*, text: str, agent: str | None, session: str | None) -> bool:
    cli = _resolve_openclaw_cli_path()
    if not cli:
        return False
    command = [cli, "agent", "--message", text]
    if agent:
        command.extend(["--agent", agent])
    if session and session != "-":
        command.extend(["--session-id", session])
    try:
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
    except Exception as exc:
        LOGGER.warning("chat_send_local_spawn_failed error=%s", exc)
        return False
    asyncio.create_task(_wait_local_chat_send(process), name="chat-send-local-cli")
    LOGGER.info("chat_send_local_spawned cmd=%s", " ".join(shlex.quote(part) for part in command[:3]))
    return True


async def _wait_local_chat_send(process: asyncio.subprocess.Process) -> None:
    stderr_data = ""
    if process.stderr:
        raw = await process.stderr.read()
        stderr_data = raw.decode("utf-8", errors="replace").strip()
    return_code = await process.wait()
    if return_code != 0:
        if stderr_data:
            LOGGER.warning("chat_send_local_failed code=%s error=%s", return_code, stderr_data[:240])
        else:
            LOGGER.warning("chat_send_local_failed code=%s", return_code)
