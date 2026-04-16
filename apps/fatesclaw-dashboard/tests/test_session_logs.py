from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from fatesclaw_dashboard.gateway.session_logs import _candidate_session_files, _extract_message_updates, _resolve_session_file


class SessionLogsTests(unittest.TestCase):
    def test_resolve_session_file_prefers_latest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            sessions_dir = base / "sessions"
            sessions_dir.mkdir(parents=True)
            index_path = sessions_dir / "sessions.json"
            index_path.write_text(
                json.dumps(
                    {
                        "agent:alpha:older": {
                            "updatedAt": 10,
                            "sessionFile": "/tmp/older.jsonl",
                        },
                        "agent:alpha:newer": {
                            "updatedAt": 20,
                            "sessionId": "newer",
                        },
                    }
                ),
                encoding="utf-8",
            )

            key, path = _resolve_session_file(index_path)
            self.assertEqual(key, "agent:alpha:newer")
            self.assertEqual(path, sessions_dir / "newer.jsonl")

    def test_extract_message_updates_parses_spoken_and_thinking(self) -> None:
        message = {
            "role": "assistant",
            "content": [
                {"type": "thinking", "thinking": "plan step by step"},
                {"type": "text", "text": "Hello there"},
            ],
        }
        spoken, thinking = _extract_message_updates(message, role="assistant")
        self.assertEqual(spoken, ["Hello there"])
        self.assertEqual(thinking, ["plan step by step"])

    def test_extract_message_updates_strips_sender_metadata(self) -> None:
        message = {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": (
                        "Sender (untrusted metadata):\\n```json\\n{\\n  \\\"label\\\": \\\"openclaw-tui\\\"\\n}\\n```\\n\\n"
                        "[Thu 2026-04-16 12:28 GMT-5] hola"
                    ),
                }
            ],
        }
        spoken, thinking = _extract_message_updates(message, role="user")
        self.assertEqual(spoken, ["hola"])
        self.assertEqual(thinking, [])

    def test_candidate_session_files_prefers_selected_then_recent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            preferred = base / "a.jsonl"
            other1 = base / "b.jsonl"
            other2 = base / "c.jsonl"
            preferred.write_text("", encoding="utf-8")
            other1.write_text("", encoding="utf-8")
            other2.write_text("", encoding="utf-8")

            paths = _candidate_session_files(base, preferred=preferred, max_files=2)
            self.assertEqual(paths[0], preferred)
            self.assertEqual(len(paths), 2)


if __name__ == "__main__":
    unittest.main()
