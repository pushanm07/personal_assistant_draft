"""Text-to-speech.

``EdgeTTSEngine`` uses Microsoft's edge-tts (online; a configured MP3 is
streamed and saved to a temp file before playback). Voice, rate and pitch come
from config so the voice can change without touching Brain or the UI.

Note: edge-tts is not fully offline — it requires network access to
Microsoft's Edge TTS service. The protocol seam makes a local engine easy to
drop in later.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Protocol


class TTSEngine(Protocol):
    def synthesize(self, text: str, output_path: str) -> None:
        """Synthesize *text* into an audio file at *output_path*."""
        ...


class EdgeTTSEngine:
    def __init__(self, voice: str = "en-US-JennyNeural", rate: str = "+12%", pitch: str = "+0Hz") -> None:
        self.voice = voice
        self.rate = rate
        self.pitch = pitch

    def synthesize(self, text: str, output_path: str) -> None:
        import asyncio

        import edge_tts

        communicate = edge_tts.Communicate(
            text,
            self.voice,
            rate=self.rate,
            pitch=self.pitch,
        )
        asyncio.run(communicate.save(output_path))


def make_tts(settings) -> TTSEngine:
    """Build the TTS engine selected by config/desktop.json."""
    provider = settings.tts.provider
    if provider == "edge-tts":
        return EdgeTTSEngine(
            voice=settings.tts.voice,
            rate=settings.tts.rate,
            pitch=settings.tts.pitch,
        )
    raise ValueError(f"Unknown TTS provider: {provider!r}")