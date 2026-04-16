from __future__ import annotations

import asyncio
import logging

from fatesclaw_dashboard.config import Config
from fatesclaw_dashboard.state import AppState
from fatesclaw_dashboard.system.metrics import collect_system_snapshot

LOGGER = logging.getLogger(__name__)


async def run_system_monitor(state: AppState, config: Config) -> None:
    while True:
        snapshot = await state.snapshot()
        system_snapshot = collect_system_snapshot(config, snapshot.connection.connected)
        await state.set_system(system_snapshot)
        LOGGER.debug("system_snapshot host=%s load=%s", system_snapshot.hostname, system_snapshot.cpu_load)
        await asyncio.sleep(5)

