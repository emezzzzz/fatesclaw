from __future__ import annotations


class TextToSpeechAdapter:
    async def synthesize(self, text: str) -> bytes:
        raise NotImplementedError("TTS adapter is not implemented in v1")

    async def play(self, audio: bytes) -> None:
        raise NotImplementedError("Audio playback is not implemented in v1")

