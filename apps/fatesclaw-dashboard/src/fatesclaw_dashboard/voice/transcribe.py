from __future__ import annotations

from fatesclaw_dashboard.voice.capture import CapturedAudio


class TranscriptionAdapter:
    async def transcribe(self, audio: CapturedAudio) -> str:
        raise NotImplementedError("Transcription adapter is not implemented in v1")

