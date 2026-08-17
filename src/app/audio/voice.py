"""Voice controller — Wake + capture + STT, kept off the GUI thread.

Listens for a wake word ONLY while Voice Mode is enabled, and only ever runs
the (model-bearing) speech recogniser *after* something has been captured.
Emits Qt signals the UI/orb react to: ``listening``/``thinking`` states and the
final ``transcribed`` text.
"""

from __future__ import annotations

import tempfile
import threading
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QObject, Signal, Slot

from .stt import STTEngine
from .wake import WakeWordEngine


class VoiceController(QObject):
    stateChanged = Signal(str)      # "idle" | "listening" | "thinking"
    transcribed = Signal(str)
    wakeDetected = Signal()
    errorOccurred = Signal(str)

    def __init__(
        self,
        stt: STTEngine,
        wake_factory: Callable[[Callable[[], None]], WakeWordEngine],
        *,
        sample_rate: int = 16000,
        record_duration: float = 12.0,
        device: int | None = None,
        audio_path: str | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._stt = stt
        self._wake_factory = wake_factory
        self._sample_rate = sample_rate
        self._duration = record_duration
        self._device = device
        self._audio_path = audio_path or str(
            Path(tempfile.gettempdir()) / "alana_voice_capture.wav"
        )
        Path(self._audio_path).parent.mkdir(parents=True, exist_ok=True)

        self._voice_enabled = False
        self._wake: WakeWordEngine | None = None
        self._spawn_lock = threading.Lock()
        # Only one capture thread may run at a time (wake is paused during it).
        self._capture_running = False

    # -- public state --------------------------------------------------- #
    def voice_enabled(self) -> bool:
        return self._voice_enabled

    # -- slots called from QML ------------------------------------------ #
    @Slot(bool)
    def setVoiceMode(self, enabled: bool) -> None:
        if enabled == self._voice_enabled:
            return
        self._voice_enabled = enabled
        if enabled:
            # Start the lightweight listener. Full STT model is NOT loaded here.
            self._wake = self._wake_factory(self._on_wake)
            self._wake.start()
            self.stateChanged.emit("idle")
        else:
            self._stop_wake()
            self.stateChanged.emit("idle")

    @Slot()
    def listenPushToTalk(self) -> None:
        # A manual "hold to talk" also pauses the wake listener while capturing.
        self._stop_wake()
        self._begin_capture()

    @Slot()
    def stopListening(self) -> None:
        self._stop_wake()

    # -- internals ------------------------------------------------------ #
    def _on_wake(self) -> None:
        self.wakeDetected.emit()
        self._begin_capture()

    def _stop_wake(self) -> None:
        if self._wake is not None:
            self._wake.stop()
            self._wake = None

    def _begin_capture(self) -> None:
        with self._spawn_lock:
            if self._capture_running:
                return
            self._capture_running = True
        threading.Thread(
            target=self._capture_and_transcribe,
            name="alana-voice",
            daemon=True,
        ).start()

    def _capture_and_transcribe(self) -> None:
        try:
            from voice.record import record_push_to_talk

            self.stateChanged.emit("listening")
            record_push_to_talk(
                samplerate=self._sample_rate,
                output_path=self._audio_path,
                device=self._device,
                max_duration=self._duration,
            )
            self.stateChanged.emit("thinking")
            text = self._stt.transcribe(self._audio_path).strip()
        except Exception as exc:  # pragma: no cover - hardware/device dependent
            self.errorOccurred.emit(str(exc))
            text = ""
        finally:
            self._capture_running = False
            # If voice mode is still on (wake-triggered), re-arm the listener.
            if self._voice_enabled and self._wake is None:
                self._wake = self._wake_factory(self._on_wake)
                self._wake.start()

        if text:
            self.transcribed.emit(text)
        else:
            self.stateChanged.emit("idle")

    def shutdown(self) -> None:
        self._voice_enabled = False
        self._stop_wake()