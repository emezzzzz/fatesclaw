from __future__ import annotations

import textwrap
from typing import Iterable


def clamp_text(text: str, width: int) -> str:
    if len(text) <= width:
        return text
    if width <= 1:
        return text[:width]
    return f"{text[: width - 1]}…"


def window_lines(lines: Iterable[str], offset: int, limit: int) -> list[str]:
    collected = list(lines)
    return collected[offset : offset + limit]


def wrap_text_lines(text: str, width: int) -> list[str]:
    cleaned = " ".join(text.split()).strip()
    if not cleaned:
        return []
    if width <= 1:
        return [cleaned[:1]]
    return textwrap.wrap(cleaned, width=width, break_long_words=True, break_on_hyphens=False)
