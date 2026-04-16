from __future__ import annotations

import asyncio
import json
import logging
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fatesclaw_dashboard.state import AppState

LOGGER = logging.getLogger(__name__)

OPENCLAW_AGENTS_DIR = Path.home() / ".openclaw" / "agents"


@dataclass(slots=True)
class _TailCursor:
    offset: int = 0
    initialized: bool = False


class SessionLogPoller:
    def __init__(self, state: AppState, poll_seconds: float = 0.8, bootstrap_messages: int = 24) -> None:
        self.state = state
        self.poll_seconds = max(0.2, poll_seconds)
        self.bootstrap_messages = max(1, bootstrap_messages)
        self._cursors: dict[str, _TailCursor] = {}

    async def run(self) -> None:
        while True:
            snapshot = await self.state.snapshot()
            agents = snapshot.available_agents or [snapshot.selected_agent]
            active_for_selected = snapshot.active_session if snapshot.active_session.startswith("agent:") else None
            for agent in agents:
                preferred = active_for_selected if agent == snapshot.selected_agent else None
                await self._poll_agent(agent, preferred_session=preferred)
            await asyncio.sleep(self.poll_seconds)

    async def _poll_agent(self, agent: str, *, preferred_session: str | None = None) -> None:
        index_path = OPENCLAW_AGENTS_DIR / agent / "sessions" / "sessions.json"
        session_key, session_file = _resolve_session_file(index_path, preferred_session=preferred_session)
        if session_key:
            await self.state.update_session(session=session_key, model=None, mode=None, agent=agent)
        candidate_files = _candidate_session_files(index_path.parent, preferred=session_file, max_files=4)
        for idx, path in enumerate(candidate_files):
            await self._tail_session_file(agent, path, bootstrap=(idx == 0))

    async def _tail_session_file(self, agent: str, session_file: Path, *, bootstrap: bool) -> None:
        key = str(session_file)
        cursor = self._cursors.setdefault(key, _TailCursor())
        try:
            file_size = session_file.stat().st_size
        except OSError:
            return

        if not cursor.initialized:
            if bootstrap:
                for record in _load_recent_message_records(session_file, self.bootstrap_messages):
                    await _apply_session_record(self.state, agent, record)
            cursor.offset = file_size
            cursor.initialized = True
            return

        if file_size < cursor.offset:
            cursor.offset = 0
        if file_size == cursor.offset:
            return

        try:
            with session_file.open("r", encoding="utf-8") as handle:
                handle.seek(cursor.offset)
                for line in handle:
                    record = _parse_json_line(line)
                    if record is None:
                        continue
                    await _apply_session_record(self.state, agent, record)
                cursor.offset = handle.tell()
        except OSError as exc:
            LOGGER.debug("session_log_tail_failed path=%s error=%s", session_file, exc)


def _resolve_session_file(index_path: Path, *, preferred_session: str | None = None) -> tuple[str | None, Path | None]:
    try:
        data = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None, None
    if not isinstance(data, dict):
        return None, None

    entries: list[tuple[str, dict[str, Any]]] = [
        (key, value) for key, value in data.items() if isinstance(key, str) and isinstance(value, dict)
    ]
    if not entries:
        return None, None

    chosen: tuple[str, dict[str, Any]] | None = None
    if preferred_session:
        chosen = next((item for item in entries if item[0] == preferred_session), None)
    if chosen is None:
        chosen = max(entries, key=lambda item: _updated_at(item[1]))
    session_key, metadata = chosen
    session_file = _session_file_from_metadata(metadata, index_path.parent)
    return session_key, session_file


def _candidate_session_files(sessions_dir: Path, *, preferred: Path | None, max_files: int) -> list[Path]:
    deduped: list[Path] = []
    if preferred:
        deduped.append(preferred)
    try:
        discovered = sorted(
            sessions_dir.glob("*.jsonl"),
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        )
    except OSError:
        discovered = []
    for path in discovered:
        if path in deduped:
            continue
        deduped.append(path)
        if len(deduped) >= max_files:
            break
    return deduped[:max_files]


def _updated_at(metadata: dict[str, Any]) -> int:
    value = metadata.get("updatedAt")
    if isinstance(value, int):
        return value
    return 0


def _session_file_from_metadata(metadata: dict[str, Any], sessions_dir: Path) -> Path | None:
    explicit = metadata.get("sessionFile")
    if isinstance(explicit, str) and explicit.strip():
        path = Path(explicit.strip())
        return path if path.is_absolute() else sessions_dir / path
    session_id = metadata.get("sessionId")
    if isinstance(session_id, str) and session_id.strip():
        return sessions_dir / f"{session_id.strip()}.jsonl"
    return None


def _load_recent_message_records(path: Path, limit: int) -> list[dict[str, Any]]:
    recent: deque[dict[str, Any]] = deque(maxlen=limit)
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                record = _parse_json_line(line)
                if record and record.get("type") == "message":
                    recent.append(record)
    except OSError:
        return []
    return list(recent)


def _parse_json_line(line: str) -> dict[str, Any] | None:
    line = line.strip()
    if not line:
        return None
    try:
        record = json.loads(line)
    except json.JSONDecodeError:
        return None
    return record if isinstance(record, dict) else None


async def _apply_session_record(state: AppState, agent: str, record: dict[str, Any]) -> None:
    if record.get("type") != "message":
        return
    message = record.get("message")
    if not isinstance(message, dict):
        return
    role = str(message.get("role") or "assistant").strip().lower() or "assistant"
    spoken_updates, thinking_updates = _extract_message_updates(message, role=role)

    for thought in thinking_updates:
        await state.update_thinking(thought, streaming=False, agent=agent)
    for spoken in spoken_updates:
        await state.add_chat(role=role, text=spoken, streaming=False, agent=agent)

    error_message = message.get("errorMessage")
    if isinstance(error_message, str) and error_message.strip() and not spoken_updates and role == "assistant":
        compact_error = _sanitize_error_message(error_message)
        await state.add_chat(role="assistant", text=f"error: {compact_error}", streaming=False, agent=agent)


def _extract_message_updates(message: dict[str, Any], *, role: str) -> tuple[list[str], list[str]]:
    spoken_updates: list[str] = []
    thinking_updates: list[str] = []
    content = message.get("content")

    if isinstance(content, str):
        cleaned = _sanitize_spoken_text(content, role=role)
        if cleaned:
            spoken_updates.append(cleaned)
        return spoken_updates, thinking_updates

    if not isinstance(content, list):
        return spoken_updates, thinking_updates

    for block in content:
        if not isinstance(block, dict):
            continue
        block_type = str(block.get("type") or "").strip().lower()
        if block_type in {"thinking", "reasoning", "analysis", "thought"}:
            thought = _sanitize_text(block.get("thinking") or block.get("text") or block.get("content"))
            if thought:
                thinking_updates.append(thought)
            continue
        spoken = _sanitize_spoken_text(block.get("text") or block.get("content"), role=role)
        if spoken:
            spoken_updates.append(spoken)
    return spoken_updates, thinking_updates


def _sanitize_spoken_text(value: Any, *, role: str) -> str | None:
    text = _sanitize_text(value)
    if not text:
        return None
    if role == "user" and text.startswith("Sender (untrusted metadata):"):
        text = _strip_sender_metadata(text)
    return text or None


def _sanitize_text(value: Any) -> str | None:
    if isinstance(value, str):
        cleaned = " ".join(value.split()).strip()
        return cleaned or None
    if isinstance(value, list):
        parts = [_sanitize_text(item) for item in value]
        merged = " ".join(part for part in parts if part)
        return merged.strip() or None
    if isinstance(value, dict):
        nested = _sanitize_text(value.get("text") or value.get("content"))
        return nested
    return None


def _strip_sender_metadata(text: str) -> str:
    if "] " in text:
        candidate = text.rsplit("] ", 1)[1]
        return " ".join(candidate.split()).strip()
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return ""
    candidate = lines[-1]
    if candidate.startswith("[") and "] " in candidate:
        candidate = candidate.split("] ", 1)[1]
    return " ".join(candidate.split()).strip()


def _sanitize_error_message(value: str) -> str:
    cleaned = " ".join(value.split()).strip()
    lowered = cleaned.lower()
    if "connection error" in lowered:
        return "Connection error."
    if "<html" in lowered:
        return "Upstream HTML error."
    return cleaned[:160]
