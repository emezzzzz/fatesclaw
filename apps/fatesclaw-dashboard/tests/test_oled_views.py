from __future__ import annotations

import unittest

from fatesclaw_dashboard.oled.views import _build_chat_prompt, _flatten_history_entries


class OledViewsTests(unittest.TestCase):
    def test_build_chat_prompt_shows_symbol_when_empty(self) -> None:
        self.assertEqual(_build_chat_prompt("", max_chars=20), "›")

    def test_build_chat_prompt_keeps_tail_when_overflowing(self) -> None:
        prompt = _build_chat_prompt("abcdefghijklmnopqrstuvwxyz", max_chars=10)
        self.assertEqual(prompt, "› stuvwxyz")

    def test_flatten_history_wraps_to_full_width(self) -> None:
        lines, line_entry_index, line_is_first = _flatten_history_entries(
            [("A:", "one two three four five six seven eight nine ten")],
            max_chars=10,
        )
        self.assertTrue(lines)
        self.assertTrue(all(len(line) <= 10 for line in lines))
        self.assertTrue(lines[0].startswith("A: "))
        self.assertEqual(line_entry_index, [0] * len(lines))
        self.assertTrue(line_is_first[0])


if __name__ == "__main__":
    unittest.main()
