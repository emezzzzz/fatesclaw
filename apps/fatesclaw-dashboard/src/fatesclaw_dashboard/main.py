from __future__ import annotations

import asyncio
import logging
import signal
from contextlib import suppress

from fatesclaw_dashboard.config import Config
from fatesclaw_dashboard.gateway.client import GatewayClient, MockGatewayClient
from fatesclaw_dashboard.gateway.protocol import extract_agent_mode, extract_text_updates
from fatesclaw_dashboard.gateway.session_logs import SessionLogPoller
from fatesclaw_dashboard.input.buttons import ButtonPanel
from fatesclaw_dashboard.input.encoders import EncoderPanel
from fatesclaw_dashboard.input.fates_evdev import FatesEvdevInput
from fatesclaw_dashboard.input.keyboard import KeyboardInput
from fatesclaw_dashboard.input.mapper import InputMapper
from fatesclaw_dashboard.logging_setup import configure_logging
from fatesclaw_dashboard.oled.device import create_oled_target
from fatesclaw_dashboard.oled.renderer import OledRenderer
from fatesclaw_dashboard.state import AppState, ApprovalRequest, JobInfo, ViewName
from fatesclaw_dashboard.system.health import run_system_monitor
from fatesclaw_dashboard.voice.pipeline import VoicePipeline

LOGGER = logging.getLogger(__name__)


async def apply_gateway_event(state: AppState, event) -> None:
    await state.set_last_event(event.summary)
    payload = event.payload
    discovered_agents = _extract_available_agents(payload)
    if discovered_agents:
        await state.set_available_agents(discovered_agents)
    event_agent = _extract_event_agent(payload)
    text_updates = extract_text_updates(event.category, payload)
    for update in text_updates:
        if update.kind == "thinking":
            await state.update_thinking(update.text, streaming=update.streaming, agent=event_agent)
        else:
            await state.update_spoken(update.text, role=update.role, streaming=update.streaming, agent=event_agent)

    if event.category == "chat":
        if not text_updates:
            role = str(payload.get("role") or "assistant")
            text = str(payload.get("text") or payload.get("message") or "").strip()
            if text and role.lower() in {"assistant", "agent", "model"}:
                await state.update_spoken(
                    text,
                    role=role.lower(),
                    streaming=bool(payload.get("streaming", False)),
                    agent=event_agent,
                )
    elif event.category == "job":
        jobs = payload.get("jobs")
        if isinstance(jobs, list):
            await state.replace_jobs(
                [
                    JobInfo(
                        job_id=str(item.get("job_id") or item.get("id") or f"job-{index}"),
                        name=str(item.get("name") or item.get("job") or f"job-{index}"),
                        status=str(item.get("status", "unknown")),
                        last_run=str(item.get("last_run", "-")),
                        next_run=str(item.get("next_run", "-")),
                    )
                    for index, item in enumerate(jobs)
                    if isinstance(item, dict)
                ]
            )
    elif event.category == "approval":
        approvals = payload.get("approvals")
        if isinstance(approvals, list):
            await state.replace_approvals(
                [
                    ApprovalRequest(
                        request_id=str(item.get("request_id") or item.get("id") or f"approval-{index}"),
                        summary=str(item.get("summary") or item.get("title") or f"approval-{index}"),
                        detail=str(item.get("detail") or item.get("description") or ""),
                        status=str(item.get("status", "pending")),
                    )
                    for index, item in enumerate(approvals)
                    if isinstance(item, dict)
                ]
            )
    elif event.category == "catalog":
        commands = [str(item) for item in payload.get("commands", [])]
        skills = [str(item) for item in payload.get("skills", [])]
        await state.set_commands_and_skills(commands, skills)
    elif event.category == "raw":
        if payload.get("type") == "res" and payload.get("ok") is False:
            error = payload.get("error")
            if isinstance(error, dict) and isinstance(error.get("message"), str):
                await state.set_last_event(str(error.get("message")))
    elif event.category in {"session", "health", "raw"}:
        await state.update_session(
            session=str(payload.get("session") or payload.get("session_id") or "") or None,
            model=str(payload.get("model") or payload.get("active_model") or "") or None,
            mode=extract_agent_mode(payload),
            agent=event_agent,
        )


async def run_gateway_loop(state: AppState, client) -> None:
    reconnect_attempts = 0
    await state.set_connection(connected=False, endpoint=getattr(client, "url", "mock"))
    async for event in client.events():
        reconnect_attempts += 1
        if event.category == "health" and "error" in event.payload:
            await state.set_connection(
                connected=False,
                endpoint=getattr(client, "url", "mock"),
                reconnect_attempts=reconnect_attempts,
                last_error=str(event.payload.get("error")),
            )
        else:
            await state.set_connection(
                connected=True,
                endpoint=getattr(client, "url", "mock"),
                reconnect_attempts=0,
            )
        await apply_gateway_event(state, event)


async def run_input_source(source, mapper: InputMapper) -> None:
    async for event in source.events():
        await mapper.handle(event)


async def handle_select(state: AppState, gateway_client) -> None:
    snapshot = await state.snapshot()
    if snapshot.current_view == ViewName.APPROVALS:
        if snapshot.approvals:
            selected = snapshot.approvals[snapshot.selected_index]
            await state.set_last_event(f"approval: {selected.summary}")
        else:
            await state.set_last_event("no approvals")
    elif snapshot.current_view == ViewName.AGENTS:
        selected_agent = await state.select_focused_agent()
        if selected_agent:
            await state.set_last_event(f"agent selected: {selected_agent}")
        else:
            await state.set_last_event("no agents available")
    else:
        await state.set_last_event(f"select on {snapshot.current_view.value}")


async def handle_back(state: AppState, gateway_client) -> None:
    await state.select_home()


async def monitor_shutdown(state: AppState) -> None:
    while True:
        snapshot = await state.snapshot()
        if snapshot.shutdown_requested:
            return
        await asyncio.sleep(0.2)


async def async_main() -> None:
    config = Config.from_env()
    configure_logging(config.log_dir, config.log_level)
    LOGGER.info(
        "agent_panel_start config_gateway=%s gateway_override=%s gateway_auth_mode=%s "
        "gateway_auth_source=%s mock_gateway=%s oled_mode=%s",
        config.gateway_url,
        config.gateway_url_overridden,
        config.gateway_auth.mode or "none",
        config.gateway_auth.source,
        config.use_mock_gateway,
        config.oled_mode,
    )

    state = AppState(default_agent=config.default_agent)
    voice = VoicePipeline(state)
    session_logs = SessionLogPoller(state, poll_seconds=config.session_log_poll_seconds)
    gateway_client = (
        MockGatewayClient()
        if config.use_mock_gateway
        else GatewayClient(config.gateway_url, auth=config.gateway_auth)
    )
    oled_target = create_oled_target(config)
    renderer = OledRenderer(
        state,
        oled_target,
        refresh_hz=config.refresh_hz,
        home_animation_speed=config.home_animation_speed,
    )

    keyboard = KeyboardInput(config.keyboard_device)
    fates_evdev = FatesEvdevInput(config)
    buttons = ButtonPanel(config.controls_buttons)
    encoders = EncoderPanel(config.controls_encoders)
    fates_evdev.start()
    buttons.start()
    encoders.start()

    mapper = InputMapper(
        state,
        gateway_client,
        on_select=lambda: handle_select(state, gateway_client),
        on_back=lambda: handle_back(state, gateway_client),
        view_turn_cooldown_ms=max(120, config.controls_encoders.accel_window_ms * 2),
    )

    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with suppress(NotImplementedError):
            loop.add_signal_handler(sig, stop_event.set)

    tasks = [
        asyncio.create_task(run_gateway_loop(state, gateway_client), name="gateway"),
        asyncio.create_task(run_system_monitor(state, config), name="system"),
        asyncio.create_task(renderer.run(), name="oled"),
        asyncio.create_task(run_input_source(keyboard, mapper), name="keyboard"),
        asyncio.create_task(run_input_source(fates_evdev, mapper), name="fates_evdev"),
        asyncio.create_task(run_input_source(buttons, mapper), name="buttons"),
        asyncio.create_task(run_input_source(encoders, mapper), name="encoders"),
        asyncio.create_task(session_logs.run(), name="session_logs"),
        asyncio.create_task(monitor_shutdown(state), name="shutdown"),
    ]

    done, pending = await asyncio.wait(
        [*tasks, asyncio.create_task(stop_event.wait(), name="signal")],
        return_when=asyncio.FIRST_COMPLETED,
    )
    LOGGER.info("agent_panel_stopping completed=%s", [task.get_name() for task in done])

    await voice.set_overlay()

    for task in pending:
        task.cancel()
    await asyncio.gather(*pending, return_exceptions=True)
    for task in done:
        if task.cancelled():
            continue
        exception = task.exception()
        if exception:
            LOGGER.exception(
                "agent_panel_task_failed task=%s",
                task.get_name(),
                exc_info=(type(exception), exception, exception.__traceback__),
            )
            raise exception


def run() -> None:
    asyncio.run(async_main())


def _extract_event_agent(payload: dict) -> str | None:
    for key in ("agent", "agent_id", "agentId", "agent_name", "agentName"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, dict):
            nested = value.get("agentId") or value.get("agent_id") or value.get("name")
            if isinstance(nested, str) and nested.strip():
                return nested.strip()
    session = payload.get("session") or payload.get("session_id")
    if isinstance(session, str):
        parsed = _agent_from_session_key(session)
        if parsed:
            return parsed
    message = payload.get("message")
    if isinstance(message, dict):
        nested = _extract_event_agent(message)
        if nested:
            return nested
    return None


def _extract_available_agents(payload: dict) -> list[str]:
    candidates: list[str] = []
    for block in (
        payload.get("agents"),
        ((payload.get("snapshot") or {}).get("health") or {}).get("agents"),
    ):
        if isinstance(block, list):
            for item in block:
                if isinstance(item, dict):
                    agent = item.get("agentId") or item.get("agent_id") or item.get("name")
                    if isinstance(agent, str) and agent.strip():
                        candidates.append(agent.strip())
                elif isinstance(item, str) and item.strip():
                    candidates.append(item.strip())
    for scalar in (
        ((payload.get("snapshot") or {}).get("sessionDefaults") or {}).get("defaultAgentId"),
        payload.get("defaultAgentId"),
        payload.get("agentId"),
    ):
        if isinstance(scalar, str) and scalar.strip():
            candidates.append(scalar.strip())
    return _dedupe_agents(candidates)


def _agent_from_session_key(value: str) -> str | None:
    cleaned = value.strip()
    if not cleaned:
        return None
    if cleaned.startswith("agent:"):
        parts = cleaned.split(":")
        if len(parts) >= 3 and parts[1].strip():
            return parts[1].strip()
    return None


def _dedupe_agents(values: list[str]) -> list[str]:
    deduped: list[str] = []
    for value in values:
        cleaned = value.strip()
        if cleaned and cleaned not in deduped:
            deduped.append(cleaned)
    return deduped


if __name__ == "__main__":
    run()
