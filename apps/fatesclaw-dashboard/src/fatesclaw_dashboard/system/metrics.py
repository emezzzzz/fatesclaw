from __future__ import annotations

import os
import shutil
import socket
from pathlib import Path

from fatesclaw_dashboard.config import Config
from fatesclaw_dashboard.state import SystemSnapshot

try:
    import sounddevice
except ImportError:  # pragma: no cover
    sounddevice = None  # type: ignore[assignment]


def _format_bytes(value: int) -> str:
    gib = value / (1024 ** 3)
    return f"{gib:.1f}G"


def _read_meminfo() -> tuple[int, int]:
    total = 0
    available = 0
    with open("/proc/meminfo", "r", encoding="utf-8") as handle:
        for line in handle:
            if line.startswith("MemTotal:"):
                total = int(line.split()[1]) * 1024
            elif line.startswith("MemAvailable:"):
                available = int(line.split()[1]) * 1024
    return total, available


def _format_uptime() -> str:
    with open("/proc/uptime", "r", encoding="utf-8") as handle:
        seconds = int(float(handle.read().split()[0]))
    hours, remainder = divmod(seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}"


def audio_summary() -> str:
    if sounddevice is None:
        return "audio:n/a"
    try:
        default_input, default_output = sounddevice.default.device
        devices = sounddevice.query_devices()
        parts = []
        if default_input is not None and default_input >= 0:
            parts.append(f"in:{devices[default_input]['name'][:8]}")
        if default_output is not None and default_output >= 0:
            parts.append(f"out:{devices[default_output]['name'][:8]}")
        return " ".join(parts) if parts else "audio:unset"
    except Exception:
        return "audio:error"


def collect_system_snapshot(config: Config, gateway_reachable: bool) -> SystemSnapshot:
    total_mem, avail_mem = _read_meminfo()
    used_mem = total_mem - avail_mem
    disk = shutil.disk_usage(Path("/"))
    return SystemSnapshot(
        hostname=config.hostname_override or socket.gethostname(),
        uptime=_format_uptime(),
        cpu_load=" ".join(f"{value:.2f}" for value in os.getloadavg()),
        memory=f"{_format_bytes(used_mem)}/{_format_bytes(total_mem)}",
        disk=f"{_format_bytes(disk.used)}/{_format_bytes(disk.total)}",
        audio=audio_summary(),
        gateway_reachable=gateway_reachable,
    )

