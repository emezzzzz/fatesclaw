from __future__ import annotations

import math

from PIL import ImageDraw

from fatesclaw_dashboard.oled.layout import clamp_text, window_lines, wrap_text_lines
from fatesclaw_dashboard.oled.theme import Theme
from fatesclaw_dashboard.oled.widgets import draw_header, draw_list_item, draw_quick_menu
from fatesclaw_dashboard.state import AppStateData, ViewName


def draw_view(
    draw: ImageDraw.ImageDraw,
    state: AppStateData,
    width: int,
    height: int,
    theme: Theme,
    *,
    frame_time: float,
) -> None:
    match state.current_view:
        case ViewName.HOME:
            draw_home(draw, state, width, height, theme, frame_time=frame_time)
        case ViewName.CHAT:
            draw_chat(draw, state, width, height, theme)
        case ViewName.MIND:
            draw_mind(draw, state, width, height, theme)
        case ViewName.AGENTS:
            draw_agents(draw, state, width, height, theme)
        case ViewName.JOBS:
            draw_jobs(draw, state, width, height, theme)
        case ViewName.APPROVALS:
            draw_approvals(draw, state, width, height, theme)
        case ViewName.SYSTEM:
            draw_system(draw, state, width, height, theme)
    if state.quick_menu.open and state.quick_menu.items:
        draw_quick_menu(
            draw,
            theme,
            width,
            height,
            title=state.quick_menu.title or "Actions",
            items=state.quick_menu.items,
            selected_index=state.quick_menu.selected_index,
        )


def draw_home(
    draw: ImageDraw.ImageDraw,
    state: AppStateData,
    width: int,
    height: int,
    theme: Theme,
    *,
    frame_time: float,
) -> None:
    subtitle = state.selected_agent or "-"
    context = state.view_cursors.get(ViewName.HOME)
    detail_index = context.context_index if context else 0
    line_width = max(12, (width - 6) // 6)
    draw_header(draw, theme, "HOME", subtitle, width)
    _draw_pulsing_heart(draw, x=108, y=26, state=state, frame_time=frame_time)
    draw.text((1, 17), "›" if state.selected_index == 0 else " ", fill=theme.accent if state.selected_index == 0 else theme.dim)
    draw.text(
        (8, 17),
        clamp_text(f"gateway: {'ON' if state.connection.connected else 'OFF'}", line_width),
        fill=theme.foreground,
    )
    draw.text((1, 31), "›" if state.selected_index == 1 else " ", fill=theme.accent if state.selected_index == 1 else theme.dim)
    draw.text((8, 31), clamp_text(f"mode: {state.agent_mode.value}", line_width), fill=theme.accent)
    draw.text((1, 43), "›" if state.selected_index == 2 else " ", fill=theme.accent if state.selected_index == 2 else theme.dim)
    details = [
        f"event: {state.last_event_summary}",
        f"session: {state.active_session or '-'}",
        f"model: {state.active_model or '-'}",
        f"said: {_latest_spoken(state) or '-'}",
    ]
    draw.text((8, 43), clamp_text(details[detail_index % len(details)], line_width), fill=theme.dim)


def draw_chat(draw: ImageDraw.ImageDraw, state: AppStateData, width: int, height: int, theme: Theme) -> None:
    draw_header(draw, theme, "CHAT", "said", width)
    entries: list[tuple[str, str]] = []
    for entry in state.chats:
        if not entry.text.strip():
            continue
        role = entry.role.lower().strip()
        prefix = "U:" if role == "user" else "A:"
        entries.append((prefix, entry.text))
    cursor = state.view_cursors.get(ViewName.CHAT)
    y_start = 14
    prompt_y = max(y_start + 10, height - 9)
    rows = max(1, (prompt_y - y_start) // 10)
    _draw_history_panel(
        draw,
        entries,
        selected_index=state.selected_index,
        context_index=cursor.context_index if cursor else 0,
        theme=theme,
        empty_message="No chat lines",
        y_start=y_start,
        rows=rows,
        width=width,
    )
    _draw_chat_prompt(draw, state.chat_input_draft, width=width, y=prompt_y, theme=theme)


def draw_mind(draw: ImageDraw.ImageDraw, state: AppStateData, width: int, height: int, theme: Theme) -> None:
    draw_header(draw, theme, "MIND", "thoughts", width)
    entries = [("T:", entry.text) for entry in state.thoughts if entry.text.strip()]
    cursor = state.view_cursors.get(ViewName.MIND)
    _draw_history_panel(
        draw,
        entries,
        selected_index=state.selected_index,
        context_index=cursor.context_index if cursor else 0,
        theme=theme,
        empty_message="No thought lines",
        y_start=14,
        rows=5,
        width=width,
    )


def draw_agents(draw: ImageDraw.ImageDraw, state: AppStateData, width: int, height: int, theme: Theme) -> None:
    draw_header(draw, theme, "AGENTS", state.selected_agent or "-", width)
    agents = state.available_agents
    if not agents:
        draw.text((3, 24), "No agents detected", fill=theme.dim)
        return
    rows = 5
    start = _window_start(state.selected_index, len(agents), rows)
    visible = window_lines(agents, start, rows)
    y = 14
    for offset, agent in enumerate(visible):
        absolute_index = start + offset
        focused = absolute_index == state.selected_index
        active = agent == state.selected_agent
        marker = "•" if focused else " "
        active_tag = " *" if active else ""
        draw.text((3, y), marker, fill=theme.accent if focused else theme.dim)
        draw.text((10, y), clamp_text(f"{agent}{active_tag}", 18), fill=theme.foreground if active else theme.dim)
        y += 10


def draw_jobs(draw: ImageDraw.ImageDraw, state: AppStateData, width: int, height: int, theme: Theme) -> None:
    context = state.view_cursors.get(ViewName.JOBS)
    draw_header(draw, theme, "JOBS", f"p{(context.context_index if context else 0) + 1}", width)
    if not state.jobs:
        draw.text((3, 22), "No jobs seen", fill=theme.dim)
    else:
        for index, job in enumerate(state.jobs[:4]):
            selected = index == state.selected_index
            text = f"{job.name[:10]} {job.status[:4]}"
            draw_list_item(draw, theme, 15 + (index * 10), width, text, selected)


def draw_approvals(draw: ImageDraw.ImageDraw, state: AppStateData, width: int, height: int, theme: Theme) -> None:
    draw_header(draw, theme, "APPROVE", f"{len(state.approvals):02d}", width)
    if not state.approvals:
        draw.text((3, 22), "No pending", fill=theme.dim)
        return
    for index, approval in enumerate(state.approvals[:4]):
        selected = index == state.selected_index
        draw_list_item(draw, theme, 15 + (index * 10), width, approval.summary, selected)
    if state.approval_pending_decision:
        emphasis = "RIGHT again=APPROVE" if state.approval_pending_decision == "approve" else "LEFT again=REJECT"
        draw.text((3, 46), clamp_text(emphasis, 21), fill=theme.warning)


def draw_system(draw: ImageDraw.ImageDraw, state: AppStateData, width: int, height: int, theme: Theme) -> None:
    context = state.view_cursors.get(ViewName.SYSTEM)
    draw_header(draw, theme, "SYSTEM", f"d{(context.context_index if context else 0) + 1}", width)
    draw.text((3, 15), f"up {state.system.uptime}", fill=theme.foreground)
    draw.text((3, 25), f"cpu {state.system.cpu_load}", fill=theme.foreground)
    draw.text((3, 35), f"mem {state.system.memory}", fill=theme.foreground)
    draw.text((3, 45), f"dsk {state.system.disk}", fill=theme.foreground)


def _draw_pulsing_heart(draw: ImageDraw.ImageDraw, x: int, y: int, state: AppStateData, frame_time: float) -> None:
    mode_rates = {
        "idle": 0.65,
        "listening": 0.9,
        "thinking": 1.15,
        "speaking": 1.0,
    }
    rate = mode_rates.get(state.agent_mode.value, 0.65)
    phase = frame_time * rate
    pulse = 0.5 + 0.5 * math.sin(phase * (2.0 * math.pi))
    radius = 4 + int(round(pulse * 2.0))
    brightness = 110 + int(pulse * 90)
    if state.agent_mode.value == "speaking":
        brightness = min(255, brightness + 20)

    left_center = (x - radius + 1, y)
    right_center = (x + radius - 1, y)
    bottom = y + radius + 5
    draw.ellipse(
        (left_center[0] - radius, left_center[1] - radius, left_center[0] + radius, left_center[1] + radius),
        fill=brightness,
        outline=brightness,
    )
    draw.ellipse(
        (right_center[0] - radius, right_center[1] - radius, right_center[0] + radius, right_center[1] + radius),
        fill=brightness,
        outline=brightness,
    )
    draw.polygon([(x - (radius * 2), y + 1), (x + (radius * 2), y + 1), (x, bottom)], fill=brightness)


def _draw_history_panel(
    draw: ImageDraw.ImageDraw,
    entries: list[tuple[str, str]],
    *,
    selected_index: int,
    context_index: int,
    theme: Theme,
    empty_message: str,
    y_start: int,
    rows: int,
    width: int,
) -> None:
    if not entries:
        draw.text((3, y_start + 10), empty_message, fill=theme.dim)
        return
    clamped_index = max(0, min(selected_index, len(entries) - 1))
    max_chars = max(10, (width - 2) // 6)
    wrapped_lines, line_entry_index, line_is_first = _flatten_history_entries(entries, max_chars=max_chars)
    if not wrapped_lines:
        draw.text((3, y_start + 10), empty_message, fill=theme.dim)
        return
    anchor = _entry_anchor_line(clamped_index, line_entry_index, line_is_first)
    anchor = min(len(wrapped_lines) - 1, max(0, anchor + max(0, context_index)))
    start = _window_start(anchor, len(wrapped_lines), rows)
    visible = window_lines(wrapped_lines, start, rows)
    y = y_start
    for offset, line in enumerate(visible):
        line_index = start + offset
        focused = line_entry_index[line_index] == clamped_index
        fill = theme.foreground if focused else theme.dim
        draw.text((1, y), clamp_text(line, max_chars), fill=fill)
        y += 10


def _window_start(selected_index: int, total: int, rows: int) -> int:
    if total <= rows:
        return 0
    return max(0, min(selected_index - (rows // 2), total - rows))


def _entry_anchor_line(selected_entry: int, line_entry_index: list[int], line_is_first: list[bool]) -> int:
    for index, (entry_index, first) in enumerate(zip(line_entry_index, line_is_first, strict=False)):
        if first and entry_index == selected_entry:
            return index
    for index, entry_index in enumerate(line_entry_index):
        if entry_index == selected_entry:
            return index
    return 0


def _draw_chat_prompt(draw: ImageDraw.ImageDraw, draft: str, *, width: int, y: int, theme: Theme) -> None:
    max_chars = max(2, (width - 2) // 6)
    prompt = _build_chat_prompt(draft, max_chars=max_chars)
    draw.text((1, y), prompt, fill=theme.accent)


def _build_chat_prompt(draft: str, *, max_chars: int) -> str:
    trimmed = draft
    if len(trimmed) > max_chars - 2:
        trimmed = trimmed[-(max_chars - 2) :]
    return "›" if not trimmed else f"› {trimmed}"


def _flatten_history_entries(
    entries: list[tuple[str, str]], *, max_chars: int
) -> tuple[list[str], list[int], list[bool]]:
    lines: list[str] = []
    line_entry_index: list[int] = []
    line_is_first: list[bool] = []
    for entry_index, (prefix, text) in enumerate(entries):
        wrapped = wrap_text_lines(text, max(4, max_chars - 3))
        if not wrapped:
            continue
        for part_index, chunk in enumerate(wrapped):
            lead = f"{prefix} " if part_index == 0 else "   "
            lines.append(f"{lead}{chunk}")
            line_entry_index.append(entry_index)
            line_is_first.append(part_index == 0)
    return lines, line_entry_index, line_is_first


def _latest_spoken(state: AppStateData) -> str:
    for entry in reversed(state.chats):
        if entry.role.lower() in {"assistant", "agent", "model", "system"}:
            return entry.text
    return state.chats[-1].text if state.chats else ""
