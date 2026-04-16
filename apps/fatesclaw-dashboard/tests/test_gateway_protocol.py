from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from fatesclaw_dashboard.config import GatewayAuth
from fatesclaw_dashboard.gateway.client import GatewayClient
from fatesclaw_dashboard.gateway.protocol import extract_text_updates, normalize_payload


class FakeWebSocket:
    def __init__(self, messages: list[str]) -> None:
        self._messages = list(messages)
        self.sent: list[str] = []

    async def recv(self) -> str:
        if not self._messages:
            raise AssertionError("no more fake gateway messages queued")
        return self._messages.pop(0)

    async def send(self, payload: str) -> None:
        self.sent.append(payload)


class GatewayClientHandshakeTests(unittest.IsolatedAsyncioTestCase):
    async def test_authenticate_uses_request_response_connect_handshake(self) -> None:
        ws = FakeWebSocket(
            [
                json.dumps({"type": "event", "event": "connect.challenge", "payload": {"nonce": "nonce-123"}}),
                json.dumps(
                    {
                        "type": "res",
                        "id": "req-1",
                        "ok": True,
                        "payload": {"protocol": 3, "server": {"version": "1.0.0", "connId": "abc"}},
                    }
                ),
            ]
        )
        client = GatewayClient("ws://127.0.0.1:18789/ws", auth=GatewayAuth(mode="token", secret="token-value"))

        with patch("fatesclaw_dashboard.gateway.client.uuid.uuid4", return_value="req-1"):
            hello = await client._authenticate(ws)

        self.assertEqual(hello["protocol"], 3)
        self.assertEqual(len(ws.sent), 1)
        frame = json.loads(ws.sent[0])
        self.assertEqual(frame["type"], "req")
        self.assertEqual(frame["id"], "req-1")
        self.assertEqual(frame["method"], "connect")
        self.assertEqual(frame["params"]["client"]["id"], "gateway-client")
        self.assertEqual(frame["params"]["auth"], {"token": "token-value"})
        self.assertEqual(frame["params"]["caps"], [])
        self.assertNotIn("nonce", frame["params"])

    async def test_authenticate_omits_auth_when_not_configured(self) -> None:
        client = GatewayClient("ws://127.0.0.1:18789/ws")

        frame = client._build_connect_request("req-2")

        self.assertEqual(frame["params"]["client"]["id"], "gateway-client")
        self.assertEqual(frame["params"]["caps"], [])
        self.assertNotIn("auth", frame["params"])


class GatewayProtocolNormalizationTests(unittest.TestCase):
    def test_event_frames_use_inner_event_name_and_payload(self) -> None:
        events = normalize_payload(
            {
                "type": "event",
                "event": "session.state",
                "seq": 42,
                "ts": 1712345678,
                "payload": {
                    "summary": "assistant thinking",
                    "state": "thinking",
                    "session": "session-1",
                },
            }
        )

        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event.category, "session")
        self.assertEqual(event.summary, "assistant thinking")
        self.assertEqual(event.payload["event"], "session.state")
        self.assertEqual(event.payload["seq"], 42)
        self.assertEqual(event.payload["ts"], 1712345678)
        self.assertEqual(event.payload["state"], "thinking")

    def test_extract_text_updates_separates_spoken_and_thinking(self) -> None:
        payload = {
            "event": "chat",
            "role": "assistant",
            "streaming": True,
            "text": "hola",
            "thinking": "evaluating request",
        }

        updates = extract_text_updates("chat", payload)

        self.assertEqual(len(updates), 2)
        self.assertEqual(updates[0].kind, "thinking")
        self.assertEqual(updates[0].text, "evaluating request")
        self.assertTrue(updates[0].streaming)
        self.assertEqual(updates[1].kind, "spoken")
        self.assertEqual(updates[1].text, "hola")
        self.assertEqual(updates[1].role, "assistant")

    def test_extract_text_updates_uses_nested_message_role(self) -> None:
        payload = {
            "event": "session.message.delta",
            "message": {
                "role": "assistant",
                "delta": "stream chunk",
            },
        }

        updates = extract_text_updates("chat", payload)

        self.assertEqual(len(updates), 1)
        self.assertEqual(updates[0].kind, "spoken")
        self.assertEqual(updates[0].text, "stream chunk")
        self.assertTrue(updates[0].streaming)

    def test_extract_text_updates_ignores_non_assistant_generic_text(self) -> None:
        payload = {
            "event": "chat",
            "role": "user",
            "text": "hello from user",
        }

        updates = extract_text_updates("chat", payload)

        self.assertEqual(updates, [])


class GatewayOutboundFramesTests(unittest.TestCase):
    def test_prepare_outbound_wraps_legacy_type_frame(self) -> None:
        client = GatewayClient("ws://127.0.0.1:18789/ws")
        wrapped = client._prepare_outbound_payload('{"type":"sessions.list"}')
        frame = json.loads(wrapped)

        self.assertEqual(frame["type"], "req")
        self.assertEqual(frame["method"], "sessions.list")
        self.assertEqual(frame["params"], {})
        self.assertIsInstance(frame["id"], str)

    def test_prepare_outbound_keeps_request_frame(self) -> None:
        client = GatewayClient("ws://127.0.0.1:18789/ws")
        payload = '{"type":"req","id":"req-1","method":"health","params":{}}'

        wrapped = client._prepare_outbound_payload(payload)

        self.assertEqual(wrapped, payload)


if __name__ == "__main__":
    unittest.main()
