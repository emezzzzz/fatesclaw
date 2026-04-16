from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from fatesclaw_dashboard.gateway.events import GatewayEvent
from fatesclaw_dashboard.state import AgentMode


def normalize_message(raw: str) -> list[GatewayEvent]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return [GatewayEvent(category="raw", summary=raw[:80], payload={"text": raw})]
    return normalize_payload(data)


def normalize_payload(data: Any) -> list[GatewayEvent]:
    if isinstance(data, list):
        events: list[GatewayEvent] = []
        for item in data:
            events.extend(normalize_payload(item))
        return events

    if not isinstance(data, dict):
        return [GatewayEvent(category="raw", summary=str(data)[:80], payload={"value": data})]

    if str(data.get("type") or "").lower() == "res":
        error = data.get("error")
        if data.get("ok") is False and isinstance(error, dict) and isinstance(error.get("message"), str):
            return [
                GatewayEvent(
                    category="raw",
                    summary=str(error.get("message"))[:80],
                    payload=data,
                )
            ]
        return [GatewayEvent(category="raw", summary="response", payload=data)]

    if str(data.get("type") or "").lower() == "event" and "event" in data:
        event_name = str(data.get("event") or "event").lower()
        payload = data.get("payload")
        normalized = dict(payload) if isinstance(payload, dict) else {"value": payload}
        if "seq" in data:
            normalized.setdefault("seq", data.get("seq"))
        if "ts" in data:
            normalized.setdefault("ts", data.get("ts"))
        normalized.setdefault("event", event_name)
        summary = str(
            normalized.get("summary")
            or normalized.get("message")
            or normalized.get("text")
            or normalized.get("status")
            or event_name
        )[:80]
        return [GatewayEvent(category=infer_category(event_name, normalized), summary=summary, payload=normalized)]

    event_type = str(data.get("type") or data.get("event") or data.get("kind") or "unknown").lower()
    category = infer_category(event_type, data)
    summary = str(
        data.get("summary")
        or data.get("message")
        or data.get("text")
        or data.get("status")
        or event_type
    )[:80]
    return [GatewayEvent(category=category, summary=summary, payload=data)]


def infer_category(event_type: str, data: dict[str, Any]) -> str:
    if "approval" in event_type or "approval" in data:
        return "approval"
    if "cron" in event_type or "job" in event_type or "schedule" in event_type:
        return "job"
    if "chat" in event_type or "message" in event_type or "transcript" in event_type:
        return "chat"
    if "skill" in event_type or "command" in event_type:
        return "catalog"
    if "health" in event_type or "status" in event_type:
        return "health"
    if "session" in event_type or "agent" in event_type:
        return "session"
    return "raw"


@dataclass(slots=True, frozen=True)
class GatewayTextUpdate:
    kind: str
    text: str
    role: str = "assistant"
    streaming: bool = False


def extract_text_updates(category: str, payload: dict[str, Any]) -> list[GatewayTextUpdate]:
    event_name = str(payload.get("event") or payload.get("type") or "").lower()
    role = _extract_role(payload) or "assistant"
    streaming = _is_streaming(payload, event_name)

    updates: list[GatewayTextUpdate] = []

    thinking_text = _pick_text(payload, ("thinking", "reasoning", "analysis", "thought", "thoughts", "scratchpad"))
    if thinking_text:
        updates.append(GatewayTextUpdate(kind="thinking", text=thinking_text, role=role, streaming=streaming))

    spoken_text = _pick_text(
        payload,
        (
            "spoken",
            "utterance",
            "speech",
            "assistant_text",
            "output_text",
            "final_text",
            "transcript",
        ),
    )
    if spoken_text:
        updates.append(GatewayTextUpdate(kind="spoken", text=spoken_text, role=role, streaming=streaming))

    message = payload.get("message")
    if isinstance(message, dict):
        message_role = _extract_role(message) or role
        message_text = _pick_text(message, ("text", "delta", "content", "message", "chunk"))
        if message_text:
            updates.append(
                GatewayTextUpdate(
                    kind="thinking" if _is_thinking_role(message_role) else "spoken",
                    text=message_text,
                    role=message_role,
                    streaming=streaming,
                )
            )

    generic = _pick_text(payload, ("text", "delta", "content", "chunk", "message"))
    if generic and _can_treat_as_spoken(category, event_name, role):
        updates.append(GatewayTextUpdate(kind="spoken", text=generic, role=role, streaming=streaming))

    deduped: list[GatewayTextUpdate] = []
    seen: set[tuple[str, str, str, bool]] = set()
    for item in updates:
        key = (item.kind, item.role, item.text, item.streaming)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _extract_role(payload: dict[str, Any]) -> str | None:
    role = payload.get("role") or payload.get("sender") or payload.get("author")
    if not isinstance(role, str):
        return None
    cleaned = role.strip().lower()
    return cleaned or None


def _is_streaming(payload: dict[str, Any], event_name: str) -> bool:
    if payload.get("final") is True or payload.get("done") is True:
        return False
    if bool(payload.get("streaming")) or bool(payload.get("partial")) or bool(payload.get("is_delta")):
        return True
    return any(token in event_name for token in ("delta", "partial", "stream"))


def _is_thinking_role(role: str) -> bool:
    lowered = role.lower()
    return any(token in lowered for token in ("thinking", "reason", "analysis", "thought", "internal"))


def _can_treat_as_spoken(category: str, event_name: str, role: str) -> bool:
    lowered_role = role.lower()
    if lowered_role and lowered_role not in {"assistant", "agent", "model", "system"}:
        return False
    return (
        category == "chat"
        or "chat" in event_name
        or "session.message" in event_name
        or "transcript" in event_name
        or "speak" in event_name
    )


def _pick_text(payload: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        if key not in payload:
            continue
        text = _to_text(payload.get(key))
        if text:
            return text
    return None


def _to_text(value: Any) -> str | None:
    if isinstance(value, str):
        cleaned = " ".join(value.split()).strip()
        return cleaned or None
    if isinstance(value, list):
        parts = [_to_text(item) for item in value]
        merged = " ".join(part for part in parts if part)
        return merged.strip() or None
    if isinstance(value, dict):
        nested = _pick_text(value, ("text", "delta", "content", "message", "chunk"))
        if nested:
            return nested
    return None


def extract_agent_mode(payload: dict[str, Any]) -> AgentMode | None:
    value = str(
        payload.get("agent_state")
        or payload.get("state")
        or payload.get("mode")
        or payload.get("agentMode")
        or ""
    ).lower()
    if value in {mode.value for mode in AgentMode}:
        return AgentMode(value)
    return None


def build_approval_action(request_id: str, approved: bool) -> str:
    return json.dumps(
        {
            "type": "approval.respond",
            "request_id": request_id,
            "approved": approved,
        }
    )
