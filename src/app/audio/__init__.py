"""Audio services for the desktop app (STT, wake word, TTS).

Each subsystem sits behind a small Protocol so the implementation can be
swapped (Whisper -> another STT, edge-tts -> another TTS, energy wake ->
Porcupine) without touching Brain or the UI.
"""

from __future__ import annotations

from .stt import STTEngine, WhisperSTT, make_stt
from .tts import TTSEngine, EdgeTTSEngine, make_tts
from .wake import WakeWordEngine, EnergyWake, PorcupineWake, make_wake
from .voice import VoiceController

__all__ = [
    "STTEngine",
    "WhisperSTT",
    "make_stt",
    "TTSEngine",
    "EdgeTTSEngine",
    "make_tts",
    "WakeWordEngine",
    "EnergyWake",
    "PorcupineWake",
    "make_wake",
    "VoiceController",
]