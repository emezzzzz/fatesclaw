from __future__ import annotations

from PIL import ImageDraw

from fatesclaw_dashboard.oled.layout import clamp_text
from fatesclaw_dashboard.oled.theme import Theme


def draw_header(draw: ImageDraw.ImageDraw, theme: Theme, title: str, subtitle: str, width: int) -> None:
    draw.rectangle((0, 0, width, 12), outline=theme.foreground, fill=0)
    draw.text((3, 1), clamp_text(title, 18), fill=theme.foreground)
    draw.text((60, 1), clamp_text(subtitle, 11), fill=theme.dim)


def draw_footer(draw: ImageDraw.ImageDraw, theme: Theme, text: str, width: int, height: int) -> None:
    draw.line((0, height - 11, width, height - 11), fill=theme.dim)
    draw.text((3, height - 10), clamp_text(text, 22), fill=theme.dim)


def draw_list_item(
    draw: ImageDraw.ImageDraw,
    theme: Theme,
    y: int,
    width: int,
    text: str,
    selected: bool = False,
) -> None:
    if selected:
        draw.rectangle((0, y - 1, width, y + 9), outline=theme.foreground, fill=0)
    draw.text((3, y), clamp_text(text, 22), fill=theme.foreground if selected else theme.dim)


def draw_soft_labels(
    draw: ImageDraw.ImageDraw,
    theme: Theme,
    width: int,
    height: int,
    left: str,
    center: str,
    right: str,
) -> None:
    y = height - 10
    draw.line((0, y - 1, width, y - 1), fill=theme.dim)
    draw.text((2, y), clamp_text(left, 8), fill=theme.dim)
    center_text = clamp_text(center, 8)
    center_x = max(0, (width - (len(center_text) * 6)) // 2)
    draw.text((center_x, y), center_text, fill=theme.dim)
    right_text = clamp_text(right, 8)
    right_x = max(0, width - (len(right_text) * 6) - 2)
    draw.text((right_x, y), right_text, fill=theme.dim)


def draw_quick_menu(
    draw: ImageDraw.ImageDraw,
    theme: Theme,
    width: int,
    height: int,
    title: str,
    items: list[str],
    selected_index: int,
) -> None:
    if not items:
        return
    rows = 4
    clamped_index = max(0, min(selected_index, len(items) - 1))
    start = 0 if len(items) <= rows else max(0, min(clamped_index - (rows // 2), len(items) - rows))
    visible_items = items[start : start + rows]
    box_w = min(118, width - 8)
    box_h = min(height - 8, 16 + (len(visible_items) * 11))
    x0 = (width - box_w) // 2
    y0 = (height - box_h) // 2
    x1 = x0 + box_w
    y1 = y0 + box_h
    draw.rectangle((x0, y0, x1, y1), outline=theme.foreground, fill=0)
    draw.text((x0 + 3, y0 + 2), clamp_text(title, 16), fill=theme.foreground)
    y = y0 + 12
    for offset, item in enumerate(visible_items):
        absolute_index = start + offset
        selected = absolute_index == clamped_index
        if selected:
            draw.line((x0 + 4, y + 1, x0 + 4, y + 7), fill=theme.accent)
            draw.ellipse((x0 + 6, y + 3, x0 + 8, y + 5), fill=theme.accent, outline=theme.accent)
        draw.text((x0 + 12, y), clamp_text(item, 15), fill=theme.foreground if selected else theme.dim)
        y += 11
