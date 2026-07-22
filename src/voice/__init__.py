"""ALANA voice input package — record audio and transcribe to text.

Public API
----------
listen()
    Record from the microphone and return the transcribed text in one call.
record_voice()
    Record audio and save it to a WAV file.
transcribe_audio()
    Transcribe a WAV file to text using Whisper.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from voice.record import record_push_to_talk, record_voice
from voice.transcribe import transcribe_audio
from voice.transcribe import warm_up as _warm_up_model

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SETTINGS_FILE = PROJECT_ROOT / "config" / "settings.json"

DEFAULTS: dict[str, Any] = {
    "model": "small",
    "record_duration": 15,
    "sample_rate": 16000,
    "language": "en",
    "output_path": "voice.wav",
    "device": None,
}


def _load_stt_settings() -> dict[str, Any]:
    """Load STT settings from config/settings.json, falling back to defaults."""
    try:
        with SETTINGS_FILE.open(encoding="utf-8") as handle:
            settings = json.load(handle)
        stt = settings.get("stt", {})
        return {key: stt.get(key, default) for key, default in DEFAULTS.items()}
    except (OSError, json.JSONDecodeError):
        return dict(DEFAULTS)


def listen(
    duration: float | None = None,
    samplerate: int | None = None,
    output_path: str | None = None,
    model_name: str | None = None,
    language: str | None = None,
) -> str:
    """Record from the microphone and transcribe in one call.

    Any parameter left as ``None`` is filled in from
    ``config/settings.json`` (with sensible defaults).

    Returns
    -------
    str
        The transcribed text, or an empty string on failure.
    """
    settings = _load_stt_settings()

    duration = duration if duration is not None else settings["record_duration"]
    samplerate = samplerate if samplerate is not None else settings["sample_rate"]
    output_path = output_path or settings["output_path"]
    model_name = model_name or settings["model"]
    language = language or settings["language"]

    device = settings["device"]

    try:
        record_voice(
            duration=duration,
            samplerate=samplerate,
            output_path=output_path,
            device=device,
        )
        text = transcribe_audio(
            audio_path=output_path,
            model_name=model_name,
            language=language,
        )
        return text
    except Exception as exc:
        print(f"Voice input failed: {exc}")
        return ""


def listen_push_to_talk(
    samplerate: int | None = None,
    output_path: str | None = None,
    model_name: str | None = None,
    language: str | None = None,
) -> str:
    """Push-to-talk variant of :func:`listen`.

    Records immediately (the caller already asked to talk) and stops on a
    keypress or trailing silence, then transcribes. Any parameter left as
    ``None`` is filled in from ``config/settings.json``.
    """
    settings = _load_stt_settings()

    samplerate = samplerate if samplerate is not None else settings["sample_rate"]
    output_path = output_path or settings["output_path"]
    model_name = model_name or settings["model"]
    language = language or settings["language"]
    device = settings["device"]

    try:
        record_push_to_talk(
            samplerate=samplerate,
            output_path=output_path,
            device=device,
        )
        return transcribe_audio(
            audio_path=output_path,
            model_name=model_name,
            language=language,
        )
    except Exception as exc:
        print(f"Voice input failed: {exc}")
        return ""


def warm_up() -> None:
    """Preload the Whisper model so the first transcription is fast."""
    _warm_up_model(_load_stt_settings()["model"])


__all__ = [
    "listen",
    "listen_push_to_talk",
    "record_voice",
    "record_push_to_talk",
    "transcribe_audio",
    "warm_up",
]
