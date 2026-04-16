from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections.abc import AsyncIterator
from typing import Any

from fatesclaw_dashboard.config import GatewayAuth
from fatesclaw_dashboard.gateway.events import GatewayEvent
from fatesclaw_dashboard.gateway.protocol import normalize_message, normalize_payload

LOGGER = logging.getLogger(__name__)

try:
    import websockets
except ImportError:  # pragma: no cover
    websockets = None  # type: ignore[assignment]


class GatewayClient:
    def __init__(self, url: str, auth: GatewayAuth | None = None) -> None:
        self.url = url
        self.auth = auth or GatewayAuth()
        self._send_queue: asyncio.Queue[str] = asyncio.Queue()

    async def events(self) -> AsyncIterator[GatewayEvent]:
        if websockets is None:
            raise RuntimeError("websockets dependency is not installed")

        backoff = 1
        while True:
            try:
                LOGGER.info("gateway_connecting url=%s", self.url)
                async with websockets.connect(self.url, ping_interval=20, ping_timeout=20) as ws:
                    hello = await self._authenticate(ws)
                    LOGGER.info(
                        "gateway_connected url=%s auth_mode=%s auth_source=%s",
                        self.url,
                        self.auth.mode or "none",
                        self.auth.source,
                    )
                    yield GatewayEvent(category="health", summary="gateway connected", payload=hello)
                    backoff = 1
                    sender = asyncio.create_task(self._drain_send_queue(ws))
                    try:
                        async for message in ws:
                            decoded = self._decode_message(message)
                            for event in normalize_message(decoded):
                                yield event
                    finally:
                        sender.cancel()
                        await asyncio.gather(sender, return_exceptions=True)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                LOGGER.warning("gateway_disconnected url=%s error=%s", self.url, exc)
                yield GatewayEvent(category="health", summary=f"gateway error: {exc}", payload={"error": str(exc)})
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30)

    async def send_json(self, payload: dict[str, Any]) -> None:
        await self._send_queue.put(json.dumps(payload))

    async def send_raw(self, payload: str) -> None:
        await self._send_queue.put(payload)

    async def _drain_send_queue(self, ws: Any) -> None:
        while True:
            payload = await self._send_queue.get()
            await ws.send(self._prepare_outbound_payload(payload))

    async def _authenticate(self, ws: Any) -> dict[str, Any]:
        connect_request_id: str | None = None
        while True:
            message = self._decode_message(await ws.recv())
            frame = self._parse_frame(message)
            if not isinstance(frame, dict):
                continue

            if frame.get("type") == "event" and frame.get("event") == "connect.challenge":
                self._extract_nonce(frame)
                connect_request_id = str(uuid.uuid4())
                await ws.send(json.dumps(self._build_connect_request(connect_request_id)))
                continue

            if frame.get("type") == "res" and frame.get("id") == connect_request_id:
                if frame.get("ok") is True:
                    payload = frame.get("payload")
                    return payload if isinstance(payload, dict) else {}
                raise RuntimeError(self._format_gateway_error(frame.get("error")))

    def _build_connect_request(self, request_id: str) -> dict[str, Any]:
        auth: dict[str, str] | None = None
        if self.auth.enabled:
            auth = {self.auth.mode: self.auth.secret}
        params: dict[str, Any] = {
            "minProtocol": 3,
            "maxProtocol": 3,
            "client": {
                "id": "gateway-client",
                "displayName": "fatesclaw-dashboard",
                "version": "0.1.0",
                "platform": "python",
                "mode": "backend",
            },
            "caps": [],
            "role": "operator",
            "scopes": ["operator.read", "operator.write", "operator.admin"],
        }
        if auth:
            params["auth"] = auth
        return {
            "type": "req",
            "id": request_id,
            "method": "connect",
            "params": params,
        }

    def _decode_message(self, message: Any) -> str:
        if isinstance(message, bytes):
            return message.decode("utf-8", errors="replace")
        return str(message)

    def _prepare_outbound_payload(self, payload: str) -> str:
        frame = self._parse_frame(payload)
        if not isinstance(frame, dict):
            return payload
        if frame.get("type") == "req" and isinstance(frame.get("method"), str):
            return payload
        method = frame.get("type")
        if not isinstance(method, str) or not method.strip():
            return payload
        params = {key: value for key, value in frame.items() if key != "type"}
        normalized = {
            "type": "req",
            "id": str(uuid.uuid4()),
            "method": method.strip(),
            "params": params,
        }
        LOGGER.debug("gateway_send_wrapped method=%s params_keys=%s", normalized["method"], sorted(params.keys()))
        return json.dumps(normalized)

    def _parse_frame(self, raw: str) -> dict[str, Any] | None:
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None

    def _extract_nonce(self, frame: dict[str, Any]) -> str:
        payload = frame.get("payload")
        nonce = payload.get("nonce") if isinstance(payload, dict) else None
        if not isinstance(nonce, str) or not nonce.strip():
            raise RuntimeError("gateway connect challenge missing nonce")
        return nonce.strip()

    def _format_gateway_error(self, error: Any) -> str:
        if isinstance(error, dict):
            message = error.get("message")
            code = error.get("code")
            if isinstance(message, str) and isinstance(code, str):
                return f"{code}: {message}"
            if isinstance(message, str):
                return message
        return "gateway connect failed"


class MockGatewayClient:
    def __init__(self) -> None:
        self._counter = 0

    async def events(self) -> AsyncIterator[GatewayEvent]:
        approvals = [
            {"request_id": "apr-101", "summary": "Allow package install", "detail": "apt install request"},
            {"request_id": "apr-102", "summary": "Run outbound sync", "detail": "networked command"},
        ]
        jobs = [
            {"job_id": "cron-1", "name": "nightly sync", "status": "ok", "last_run": "00:10", "next_run": "24h"},
            {"job_id": "cron-2", "name": "report sweep", "status": "pending", "last_run": "never", "next_run": "08:00"},
        ]
        while True:
            self._counter += 1
            batches = [
                {
                    "type": "session.state",
                    "session": f"session-{(self._counter % 3) + 1}",
                    "model": "gpt-5.4-mini",
                    "state": ["idle", "thinking", "speaking"][self._counter % 3],
                    "summary": f"heartbeat {self._counter}",
                },
                {
                    "type": "chat.message",
                    "role": "assistant" if self._counter % 2 else "user",
                    "text": f"mock transcript line {self._counter}",
                    "streaming": bool(self._counter % 2),
                },
                {"type": "cron.snapshot", "jobs": jobs, "summary": "cron snapshot"},
                {
                    "type": "approval.snapshot",
                    "approvals": approvals[: 1 + (self._counter % 2)],
                    "summary": "approval queue",
                },
                {
                    "type": "catalog.snapshot",
                    "commands": ["resume", "stop", "sync"],
                    "skills": ["ops", "voice", "review"],
                    "summary": "capabilities updated",
                },
            ]
            for batch in batches:
                for event in normalize_payload(batch):
                    yield event
            await asyncio.sleep(2)

    async def send_json(self, payload: dict[str, Any]) -> None:
        LOGGER.info("mock_gateway_send payload=%s", payload)

    async def send_raw(self, payload: str) -> None:
        LOGGER.info("mock_gateway_send_raw payload=%s", payload)
