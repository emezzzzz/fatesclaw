from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


class KeyValueFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        base = f"{self.formatTime(record)} level={record.levelname} logger={record.name} msg={record.getMessage()}"
        if record.exc_info:
            return f"{base} exc={self.formatException(record.exc_info)}"
        return base


def configure_logging(log_dir: Path, level: str) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    formatter = KeyValueFormatter(datefmt="%Y-%m-%dT%H:%M:%S")
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()

    stream = logging.StreamHandler()
    stream.setFormatter(formatter)

    file_handler = RotatingFileHandler(log_dir / "fatesclaw-dashboard.log", maxBytes=2_000_000, backupCount=5)
    file_handler.setFormatter(formatter)

    root.addHandler(stream)
    root.addHandler(file_handler)
