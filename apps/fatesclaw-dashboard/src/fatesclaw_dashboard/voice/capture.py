from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class CapturedAudio:
    sample_rate: int
    channels: int
    frames: bytes


class AudioCapture:
    async def capture_once(self) -> CapturedAudio:
        raise NotImplementedError("Audio capture is not implemented in v1")

