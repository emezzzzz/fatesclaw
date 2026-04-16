from __future__ import annotations

import asyncio


async def is_process_running(name: str) -> bool:
    process = await asyncio.create_subprocess_exec(
        "pgrep",
        "-f",
        name,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    return await process.wait() == 0

