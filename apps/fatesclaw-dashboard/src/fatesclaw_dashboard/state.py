from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


class AgentMode(str, Enum):
    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"


class ViewName(str, Enum):
    HOME = "home"
    CHAT = "chat"
    MIND = "mind"
    AGENTS = "agents"
    JOBS = "jobs"
    APPROVALS = "approvals"
    SYSTEM = "system"


@dataclass(slots=True)
class ViewCursor:
    selected_index: int = 0
    scroll_offset: int = 0
    context_index: int = 0


@dataclass(slots=True)
class QuickMenu:
    open: bool = False
    title: str = ""
    items: list[str] = field(default_factory=list)
    selected_index: int = 0


@dataclass(slots=True)
class ConnectionState:
    connected: bool = False
    endpoint: str = ""
    reconnect_attempts: int = 0
    last_error: str | None = None
    last_seen: datetime | None = None


@dataclass(slots=True)
class ChatEntry:
    timestamp: datetime
    role: str
    text: str
    streaming: bool = False


@dataclass(slots=True)
class AgentConversation:
    chats: list[ChatEntry] = field(default_factory=list)
    thoughts: list[ChatEntry] = field(default_factory=list)
    live_spoken: str = ""
    live_thinking: str = ""
    draft: str = ""


@dataclass(slots=True)
class JobInfo:
    job_id: str
    name: str
    status: str = "unknown"
    last_run: str = "-"
    next_run: str = "-"


@dataclass(slots=True)
class ApprovalRequest:
    request_id: str
    summary: str
    detail: str = ""
    status: str = "pending"


@dataclass(slots=True)
class SystemSnapshot:
    hostname: str = "-"
    uptime: str = "-"
    cpu_load: str = "-"
    memory: str = "-"
    disk: str = "-"
    audio: str = "-"
    gateway_reachable: bool = False


@dataclass(slots=True)
class VoiceState:
    push_to_talk: bool = False
    listening: bool = False
    thinking: bool = False
    speaking: bool = False
    transcript_preview: str = ""


@dataclass(slots=True)
class AppStateData:
    connection: ConnectionState = field(default_factory=ConnectionState)
    current_view: ViewName = ViewName.HOME
    selected_index: int = 0
    view_cursors: dict[ViewName, ViewCursor] = field(default_factory=dict)
    active_model: str = "-"
    active_session: str = "-"
    selected_agent: str = "default"
    available_agents: list[str] = field(default_factory=lambda: ["default"])
    conversations: dict[str, AgentConversation] = field(default_factory=dict)
    agent_mode: AgentMode = AgentMode.IDLE
    last_event_summary: str = "startup"
    chats: list[ChatEntry] = field(default_factory=list)
    thoughts: list[ChatEntry] = field(default_factory=list)
    live_spoken: str = ""
    live_thinking: str = ""
    chat_input_draft: str = ""
    jobs: list[JobInfo] = field(default_factory=list)
    approvals: list[ApprovalRequest] = field(default_factory=list)
    commands: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    quick_menu: QuickMenu = field(default_factory=QuickMenu)
    approval_pending_decision: str | None = None
    system: SystemSnapshot = field(default_factory=SystemSnapshot)
    voice: VoiceState = field(default_factory=VoiceState)
    shutdown_requested: bool = False


class AppState:
    def __init__(self, default_agent: str = "default") -> None:
        self._data = AppStateData()
        normalized_default = _normalize_agent_name(default_agent) or "default"
        self._data.selected_agent = normalized_default
        self._data.available_agents = [normalized_default]
        self._data.view_cursors = {view: ViewCursor() for view in ViewName}
        self._ensure_conversation_locked(self._data.selected_agent)
        self._sync_active_from_conversation_locked()
        self._lock = asyncio.Lock()

    async def snapshot(self) -> AppStateData:
        async with self._lock:
            return AppStateData(
                connection=self._data.connection,
                current_view=self._data.current_view,
                selected_index=self._data.selected_index,
                view_cursors={
                    view: ViewCursor(
                        selected_index=cursor.selected_index,
                        scroll_offset=cursor.scroll_offset,
                        context_index=cursor.context_index,
                    )
                    for view, cursor in self._data.view_cursors.items()
                },
                active_model=self._data.active_model,
                active_session=self._data.active_session,
                selected_agent=self._data.selected_agent,
                available_agents=list(self._data.available_agents),
                conversations={
                    agent: AgentConversation(
                        chats=list(conversation.chats),
                        thoughts=list(conversation.thoughts),
                        live_spoken=conversation.live_spoken,
                        live_thinking=conversation.live_thinking,
                        draft=conversation.draft,
                    )
                    for agent, conversation in self._data.conversations.items()
                },
                agent_mode=self._data.agent_mode,
                last_event_summary=self._data.last_event_summary,
                chats=list(self._data.chats),
                thoughts=list(self._data.thoughts),
                live_spoken=self._data.live_spoken,
                live_thinking=self._data.live_thinking,
                chat_input_draft=self._data.chat_input_draft,
                jobs=list(self._data.jobs),
                approvals=list(self._data.approvals),
                commands=list(self._data.commands),
                skills=list(self._data.skills),
                quick_menu=QuickMenu(
                    open=self._data.quick_menu.open,
                    title=self._data.quick_menu.title,
                    items=list(self._data.quick_menu.items),
                    selected_index=self._data.quick_menu.selected_index,
                ),
                approval_pending_decision=self._data.approval_pending_decision,
                system=self._data.system,
                voice=self._data.voice,
                shutdown_requested=self._data.shutdown_requested,
            )

    async def mutate(self, fn: Any) -> None:
        async with self._lock:
            fn(self._data)

    async def set_connection(
        self,
        *,
        connected: bool,
        endpoint: str,
        reconnect_attempts: int = 0,
        last_error: str | None = None,
    ) -> None:
        async with self._lock:
            self._data.connection.connected = connected
            self._data.connection.endpoint = endpoint
            self._data.connection.reconnect_attempts = reconnect_attempts
            self._data.connection.last_error = last_error
            self._data.connection.last_seen = datetime.now(UTC)
            self._data.system.gateway_reachable = connected

    async def set_last_event(self, summary: str) -> None:
        async with self._lock:
            self._data.last_event_summary = summary[:80]

    async def update_session(
        self,
        session: str | None,
        model: str | None,
        mode: AgentMode | None,
        *,
        agent: str | None = None,
    ) -> None:
        async with self._lock:
            normalized = _normalize_agent_name(agent) if agent else None
            if normalized and normalized != self._data.selected_agent:
                return
            if session:
                self._data.active_session = session
            if model:
                self._data.active_model = model
            if mode:
                self._data.agent_mode = mode

    async def add_chat(
        self,
        role: str,
        text: str,
        streaming: bool = False,
        *,
        agent: str | None = None,
    ) -> None:
        async with self._lock:
            cleaned = _clean_text(text)
            if not cleaned:
                return
            agent_name = self._resolve_target_agent_locked(agent)
            conversation = self._ensure_conversation_locked(agent_name)
            before_count = len(conversation.chats)
            _append_spoken(conversation, role=role, text=cleaned, streaming=streaming)
            if agent_name == self._data.selected_agent:
                self._sync_active_from_conversation_locked()
                self._maybe_follow_chat_tail_locked(before_count, len(conversation.chats))

    async def update_spoken(
        self,
        text: str,
        *,
        role: str = "assistant",
        streaming: bool = False,
        agent: str | None = None,
    ) -> None:
        async with self._lock:
            cleaned = _clean_text(text)
            if not cleaned:
                return
            agent_name = self._resolve_target_agent_locked(agent)
            conversation = self._ensure_conversation_locked(agent_name)
            before_count = len(conversation.chats)
            _append_spoken(conversation, role=role, text=cleaned, streaming=streaming)
            if agent_name == self._data.selected_agent:
                self._sync_active_from_conversation_locked()
                self._maybe_follow_chat_tail_locked(before_count, len(conversation.chats))

    async def update_thinking(
        self,
        text: str,
        *,
        streaming: bool = False,
        agent: str | None = None,
    ) -> None:
        async with self._lock:
            cleaned = _clean_text(text)
            if not cleaned:
                return
            agent_name = self._resolve_target_agent_locked(agent)
            conversation = self._ensure_conversation_locked(agent_name)
            before_count = len(conversation.thoughts)
            _append_thinking(conversation, text=cleaned, streaming=streaming)
            if agent_name == self._data.selected_agent:
                self._sync_active_from_conversation_locked()
                self._maybe_follow_thought_tail_locked(before_count, len(conversation.thoughts))

    async def replace_jobs(self, jobs: list[JobInfo]) -> None:
        async with self._lock:
            self._data.jobs = jobs

    async def replace_approvals(self, approvals: list[ApprovalRequest]) -> None:
        async with self._lock:
            self._data.approvals = approvals
            max_index = max(len(approvals) - 1, 0)
            self._data.selected_index = min(self._data.selected_index, max_index)

    async def set_commands_and_skills(self, commands: list[str], skills: list[str]) -> None:
        async with self._lock:
            self._data.commands = commands
            self._data.skills = skills

    async def set_system(self, snapshot: SystemSnapshot) -> None:
        async with self._lock:
            self._data.system = snapshot

    async def set_voice(self, voice: VoiceState) -> None:
        async with self._lock:
            self._data.voice = voice
            if voice.listening:
                self._data.agent_mode = AgentMode.LISTENING
            elif voice.thinking:
                self._data.agent_mode = AgentMode.THINKING
            elif voice.speaking:
                self._data.agent_mode = AgentMode.SPEAKING
            elif not voice.push_to_talk:
                self._data.agent_mode = AgentMode.IDLE

    async def set_available_agents(self, agents: list[str]) -> None:
        async with self._lock:
            normalized = [_normalize_agent_name(agent) for agent in agents]
            deduped: list[str] = []
            for agent in normalized:
                if agent and agent not in deduped:
                    deduped.append(agent)
            if not deduped:
                deduped = ["main"]
            self._data.available_agents = deduped
            for agent in deduped:
                self._ensure_conversation_locked(agent)
            if self._data.selected_agent not in deduped:
                self._data.selected_agent = deduped[0]
                self._sync_active_from_conversation_locked()
            if self._data.current_view == ViewName.AGENTS:
                self._set_agent_selection_locked(self._data.selected_agent)

    async def select_agent(self, agent: str) -> bool:
        async with self._lock:
            normalized = _normalize_agent_name(agent)
            if normalized not in self._data.available_agents:
                return False
            self._data.selected_agent = normalized
            self._ensure_conversation_locked(normalized)
            self._sync_active_from_conversation_locked()
            if self._data.current_view == ViewName.AGENTS:
                self._set_agent_selection_locked(normalized)
            return True

    async def select_focused_agent(self) -> str | None:
        async with self._lock:
            if not self._data.available_agents:
                return None
            index = max(0, min(self._data.selected_index, len(self._data.available_agents) - 1))
            agent = self._data.available_agents[index]
            self._data.selected_agent = agent
            self._ensure_conversation_locked(agent)
            self._sync_active_from_conversation_locked()
            self._set_agent_selection_locked(agent)
            return agent

    async def append_chat_input(self, text: str, *, agent: str | None = None) -> str:
        async with self._lock:
            if not text:
                return self._data.chat_input_draft
            agent_name = self._resolve_target_agent_locked(agent)
            conversation = self._ensure_conversation_locked(agent_name)
            conversation.draft = (conversation.draft + text)[:180]
            if agent_name == self._data.selected_agent:
                self._sync_active_from_conversation_locked()
            return conversation.draft

    async def backspace_chat_input(self, *, agent: str | None = None) -> str:
        async with self._lock:
            agent_name = self._resolve_target_agent_locked(agent)
            conversation = self._ensure_conversation_locked(agent_name)
            conversation.draft = conversation.draft[:-1]
            if agent_name == self._data.selected_agent:
                self._sync_active_from_conversation_locked()
            return conversation.draft

    async def clear_chat_input(self, *, agent: str | None = None) -> None:
        async with self._lock:
            agent_name = self._resolve_target_agent_locked(agent)
            conversation = self._ensure_conversation_locked(agent_name)
            conversation.draft = ""
            if agent_name == self._data.selected_agent:
                self._sync_active_from_conversation_locked()

    async def consume_chat_input(self, *, agent: str | None = None) -> str:
        async with self._lock:
            agent_name = self._resolve_target_agent_locked(agent)
            conversation = self._ensure_conversation_locked(agent_name)
            draft = conversation.draft.strip()
            conversation.draft = ""
            if agent_name == self._data.selected_agent:
                self._sync_active_from_conversation_locked()
            return draft

    async def cycle_view(self, delta: int) -> None:
        order = list(ViewName)
        async with self._lock:
            index = order.index(self._data.current_view)
            self._data.current_view = order[(index + delta) % len(order)]
            self._data.selected_index = self._data.view_cursors[self._data.current_view].selected_index
            if self._data.current_view == ViewName.AGENTS:
                self._set_agent_selection_locked(self._data.selected_agent)
            self._data.approval_pending_decision = None
            self._data.quick_menu.open = False

    async def select_home(self) -> None:
        async with self._lock:
            self._data.current_view = ViewName.HOME
            self._data.selected_index = self._data.view_cursors[self._data.current_view].selected_index
            self._data.approval_pending_decision = None
            self._data.quick_menu.open = False

    async def move_selection(self, delta: int) -> None:
        async with self._lock:
            if self._data.current_view == ViewName.APPROVALS and self._data.approvals:
                max_index = len(self._data.approvals) - 1
            elif self._data.current_view == ViewName.JOBS and self._data.jobs:
                max_index = len(self._data.jobs) - 1
            elif self._data.current_view == ViewName.CHAT and self._data.chats:
                max_index = len(self._data.chats) - 1
            elif self._data.current_view == ViewName.MIND and self._data.thoughts:
                max_index = len(self._data.thoughts) - 1
            elif self._data.current_view == ViewName.AGENTS and self._data.available_agents:
                max_index = len(self._data.available_agents) - 1
            elif self._data.current_view == ViewName.HOME:
                max_index = 2
            elif self._data.current_view == ViewName.SYSTEM:
                max_index = 3
            else:
                max_index = 0
            self._data.selected_index = max(0, min(max_index, self._data.selected_index + delta))
            self._data.view_cursors[self._data.current_view].selected_index = self._data.selected_index
            self._data.approval_pending_decision = None

    async def adjust_context(self, delta: int) -> int:
        async with self._lock:
            cursor = self._data.view_cursors[self._data.current_view]
            limits = {
                ViewName.HOME: 4,
                ViewName.CHAT: 12,
                ViewName.MIND: 12,
                ViewName.AGENTS: 1,
                ViewName.JOBS: 2,
                ViewName.APPROVALS: 1,
                ViewName.SYSTEM: 3,
            }
            max_index = limits.get(self._data.current_view, 1)
            cursor.context_index = (cursor.context_index + delta) % max_index
            return cursor.context_index

    async def get_context_index(self) -> int:
        async with self._lock:
            return self._data.view_cursors[self._data.current_view].context_index

    async def open_quick_menu(self, title: str, items: list[str]) -> None:
        async with self._lock:
            self._data.quick_menu.open = bool(items)
            self._data.quick_menu.title = title[:18]
            self._data.quick_menu.items = [item[:22] for item in items]
            self._data.quick_menu.selected_index = 0

    async def close_quick_menu(self) -> None:
        async with self._lock:
            self._data.quick_menu.open = False
            self._data.quick_menu.title = ""
            self._data.quick_menu.items = []
            self._data.quick_menu.selected_index = 0

    async def cycle_quick_menu(self, delta: int) -> str | None:
        async with self._lock:
            if not self._data.quick_menu.open or not self._data.quick_menu.items:
                return None
            size = len(self._data.quick_menu.items)
            self._data.quick_menu.selected_index = (self._data.quick_menu.selected_index + delta) % size
            return self._data.quick_menu.items[self._data.quick_menu.selected_index]

    async def selected_quick_menu_item(self) -> str | None:
        async with self._lock:
            if not self._data.quick_menu.open or not self._data.quick_menu.items:
                return None
            return self._data.quick_menu.items[self._data.quick_menu.selected_index]

    async def arm_approval_decision(self, decision: str) -> bool:
        async with self._lock:
            decision = decision.lower()
            if decision not in {"approve", "reject"}:
                return False
            if self._data.approval_pending_decision == decision:
                self._data.approval_pending_decision = None
                return True
            self._data.approval_pending_decision = decision
            return False

    async def clear_approval_decision(self) -> None:
        async with self._lock:
            self._data.approval_pending_decision = None

    async def request_shutdown(self) -> None:
        async with self._lock:
            self._data.shutdown_requested = True

    def _resolve_target_agent_locked(self, agent: str | None) -> str:
        if agent:
            normalized = _normalize_agent_name(agent)
            if normalized:
                return normalized
        return self._data.selected_agent

    def _ensure_conversation_locked(self, agent: str) -> AgentConversation:
        conversation = self._data.conversations.get(agent)
        if conversation is None:
            conversation = AgentConversation()
            self._data.conversations[agent] = conversation
        if agent not in self._data.available_agents:
            self._data.available_agents.append(agent)
        return conversation

    def _sync_active_from_conversation_locked(self) -> None:
        conversation = self._ensure_conversation_locked(self._data.selected_agent)
        self._data.chats = list(conversation.chats)
        self._data.thoughts = list(conversation.thoughts)
        self._data.live_spoken = conversation.live_spoken
        self._data.live_thinking = conversation.live_thinking
        self._data.chat_input_draft = conversation.draft

    def _set_agent_selection_locked(self, agent: str) -> None:
        if agent not in self._data.available_agents:
            return
        index = self._data.available_agents.index(agent)
        self._data.selected_index = index
        self._data.view_cursors[ViewName.AGENTS].selected_index = index

    def _maybe_follow_chat_tail_locked(self, previous_count: int, new_count: int) -> None:
        if new_count <= 0:
            return
        cursor = self._data.view_cursors[ViewName.CHAT]
        should_follow = self._data.current_view != ViewName.CHAT or self._data.selected_index >= max(
            0, previous_count - 1
        )
        if not should_follow:
            return
        cursor.selected_index = new_count - 1
        if self._data.current_view == ViewName.CHAT:
            self._data.selected_index = cursor.selected_index

    def _maybe_follow_thought_tail_locked(self, previous_count: int, new_count: int) -> None:
        if new_count <= 0:
            return
        cursor = self._data.view_cursors[ViewName.MIND]
        should_follow = self._data.current_view != ViewName.MIND or self._data.selected_index >= max(
            0, previous_count - 1
        )
        if not should_follow:
            return
        cursor.selected_index = new_count - 1
        if self._data.current_view == ViewName.MIND:
            self._data.selected_index = cursor.selected_index


def _clean_text(text: str) -> str:
    return " ".join(text.split()).strip()


def _merge_stream_text(current: str, incoming: str) -> str:
    if not current:
        return incoming
    if incoming.startswith(current):
        return incoming
    if current.startswith(incoming):
        return current
    if incoming in current:
        return current
    if current.endswith(incoming):
        return current
    if incoming in {".", ",", "!", "?", ":", ";"}:
        return f"{current}{incoming}"
    if current.endswith((" ", "\n")) or incoming.startswith((" ", "\n")):
        return f"{current}{incoming}".strip()
    return f"{current} {incoming}".strip()


def _is_duplicate_chat(entries: list[ChatEntry], role: str, text: str) -> bool:
    if not entries:
        return False
    last = entries[-1]
    return last.role == role and last.text == text


def _append_spoken(conversation: AgentConversation, *, role: str, text: str, streaming: bool) -> None:
    role_lower = role.lower().strip()
    assistant_role = role_lower in {"assistant", "agent", "model", "system"}
    if assistant_role:
        if streaming:
            entry_text = _merge_stream_text(conversation.live_spoken, text)
        elif _looks_like_stream_continuation(conversation.live_spoken, text):
            entry_text = _merge_stream_text(conversation.live_spoken, text)
        else:
            entry_text = text
        conversation.live_spoken = entry_text
    else:
        entry_text = text
    if streaming:
        return
    if not _is_duplicate_chat(conversation.chats, role, entry_text):
        conversation.chats.append(ChatEntry(timestamp=datetime.now(UTC), role=role, text=entry_text, streaming=False))
        conversation.chats = conversation.chats[-50:]


def _append_thinking(conversation: AgentConversation, *, text: str, streaming: bool) -> None:
    if streaming:
        merged = _merge_stream_text(conversation.live_thinking, text)
    elif _looks_like_stream_continuation(conversation.live_thinking, text):
        merged = _merge_stream_text(conversation.live_thinking, text)
    else:
        merged = text
    conversation.live_thinking = merged
    if streaming:
        return
    if not _is_duplicate_chat(conversation.thoughts, "thought", merged):
        conversation.thoughts.append(
            ChatEntry(timestamp=datetime.now(UTC), role="thought", text=merged, streaming=False)
        )
        conversation.thoughts = conversation.thoughts[-50:]


def _normalize_agent_name(value: str) -> str:
    cleaned = value.strip()
    return cleaned or "main"


def _looks_like_stream_continuation(previous: str, current: str) -> bool:
    if not previous:
        return False
    return (
        current.startswith(previous)
        or previous.startswith(current)
        or current in previous
        or previous in current
    )
