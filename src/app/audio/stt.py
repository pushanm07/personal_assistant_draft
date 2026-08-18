"""Speech-to-text.

``WhisperSTT`` is a thin wrapper over Alana's existing ``voice.transcribe`` so
the desktop reuses the same engine and model cache. The model loads lazily on
the first transcription only — never at startup — keeping idle RAM low. The
``STTEngine`` protocol is the seam where a different provider can plug in.
"""

from __future__ import annotations

from typing import Protocol


class STTEngine(Protocol):
    def transcribe(self, audio_path: str) -> str:
        """Transcribe a WAV file and return its text (never blocks the GUI)."""
        ...

    def close(self) -> None:
        """Release any heavyweight resources (model, connections)."""
        ...


class WhisperSTT:
    def __init__(self, model: str = "tiny", language: str = "en") -> None:
        self.model = model
        self.language = language
        self._closed = False

    def warmup(self) -> None:
        """Preload the model so the first wake word isn't lost to a cold start."""
        if self._closed:
            return
        from voice.transcribe import warm_up

        warm_up(self.model)

    def transcribe(self, audio_path: str) -> str:
        if self._closed:
            return ""
        # First call loads the (module-cached) Whisper model. Cheap thereafter.
        from voice.transcribe import transcribe_audio

        return transcribe_audio(
            audio_path,
            model_name=self.model,
            language=self.language,
        )

    def close(self) -> None:
        self._closed = True


def make_stt(settings) -> STTEngine:
    """Build the STT engine selected by config/desktop.json."""
    engine = settings.stt.engine
    if engine == "whisper":
        return WhisperSTT(
            model=settings.stt.model,
            language=settings.stt.language,
        )
    raise ValueError(f"Unknown STT engine: {engine!r}")