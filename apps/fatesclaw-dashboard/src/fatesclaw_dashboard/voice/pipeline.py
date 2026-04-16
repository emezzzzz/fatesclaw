from __future__ import annotations

import logging

from fatesclaw_dashboard.state import AppState, VoiceState
from fatesclaw_dashboard.voice.capture import AudioCapture
from fatesclaw_dashboard.voice.transcribe import TranscriptionAdapter
from fatesclaw_dashboard.voice.tts import TextToSpeechAdapter
from fatesclaw_dashboard.voice.vad import VoiceActivityDetector

LOGGER = logging.getLogger(__name__)


class VoicePipeline:
    def __init__(
        self,
        state: AppState,
        capture: AudioCapture | None = None,
        transcriber: TranscriptionAdapter | None = None,
        tts: TextToSpeechAdapter | None = None,
        vad: VoiceActivityDetector | None = None,
    ) -> None:
        self.state = state
        self.capture = capture
        self.transcriber = transcriber
        self.tts = tts
        self.vad = vad or VoiceActivityDetector()

    async def set_overlay(self, *, listening: bool = False, thinking: bool = False, speaking: bool = False, preview: str = "") -> None:
        current = await self.state.snapshot()
        await self.state.set_voice(
            VoiceState(
                push_to_talk=current.voice.push_to_talk,
                listening=listening,
                thinking=thinking,
                speaking=speaking,
                transcript_preview=preview,
            )
        )

    async def push_to_talk(self) -> None:
        LOGGER.info("voice_push_to_talk_requested")
        await self.state.set_last_event("voice push-to-talk not yet enabled")

