from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Theme:
    background: int = 0
    foreground: int = 255
    dim: int = 120
    accent: int = 200
    warning: int = 180
    padding: int = 4


DEFAULT_THEME = Theme()

