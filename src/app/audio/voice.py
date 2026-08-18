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
        wake_factory: Callable[..., WakeWordEngine],
        *,
        sample_rate: int = 16000,
        record_duration: float = 12.0,
        follow_up_window: float = 4.0,
        device: int | None = None,
        audio_path: str | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._stt = stt
        self._wake_factory = wake_factory
        self._sample_rate = sample_rate
        self._duration = record_duration
        # Seconds Alana keeps listening for a follow-up after her last reply,
        # before reverting to wake-word activation.
        self._follow_up_window = max(0.5, float(follow_up_window))
        self._device = device
        self._audio_path = audio_path or str(
            Path(tempfile.gettempdir()) / "alana_voice_capture.wav"
        )
        Path(self._audio_path).parent.mkdir(parents=True, exist_ok=True)

        self._voice_enabled = False
        self._warmed = False
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
        enabled = bool(enabled)
        if enabled == self._voice_enabled:
            return
        self._voice_enabled = enabled
        if enabled:
            self._start_wake()
        else:
            self._stop_wake()
        self.stateChanged.emit("idle")

    @Slot()
    def listenPushToTalk(self) -> None:
        # With the wake listener armed it owns the mic, so ask it to capture
        # rather than opening a second device behind its back.
        if self._wake is not None and self._wake.trigger():
            return
        self._stop_wake()
        self._begin_capture()

    @Slot()
    def stopListening(self) -> None:
        """Stop *capturing*; wake listening survives while Voice Mode is on."""
        if not self._voice_enabled:
            self._stop_wake()

    @Slot(bool)
    def setMuted(self, muted: bool) -> None:
        """Deafen the wake listener (used while Alana is speaking)."""
        if self._wake is not None:
            self._wake.set_muted(bool(muted))

    @Slot()
    def beginFollowUp(self) -> None:
        """Arm a short hands-free window after Alana's last reply.

        While armed, any speech is treated as a follow-up command without the
        wake word. The engine reverts to wake-word mode after the window (or
        after one captured follow-up). Engines that support an in-loop window
        (``KeywordWake``) reuse the same microphone stream — zero extra cost;
        others fall back to one brief timed capture.
        """
        if not self._voice_enabled or self._capture_running:
            return
        if self._wake is not None:
            begin = getattr(self._wake, "begin_follow_up", None)
            if begin is not None and begin(self._follow_up_window):
                return
        # Engines without an in-loop follow-up: stop the listener, do one short
        # timed capture, and re-arm the listener afterwards.
        self._stop_wake()
        self._begin_capture(self._follow_up_window)

    # -- internals ------------------------------------------------------ #
    def _warmup_stt(self) -> None:
        warm = getattr(self._stt, "warmup", None)
        if warm is None or self._warmed:
            return
        self._warmed = True

        def run() -> None:
            try:
                warm()
            except Exception:
                pass

        threading.Thread(target=run, name="alana-stt-warm", daemon=True).start()

    def _start_wake(self) -> None:
        if self._wake is not None:
            return
        # The keyword engine transcribes to match; load the model off-thread
        # now so the very first "Alana" isn't swallowed by a cold start.
        self._warmup_stt()
        try:
            self._wake = self._wake_factory(self._on_wake, self._on_wake_state, self._stt)
            self._wake.start()
        except Exception as exc:  # pragma: no cover - hardware/device dependent
            self._wake = None
            self.errorOccurred.emit(f"Wake word unavailable: {exc}")

    def _on_wake_state(self, state: str) -> None:
        self.stateChanged.emit(state)

    def _on_wake(self, text: str = "") -> None:
        self.wakeDetected.emit()
        text = (text or "").strip()
        if text:
            # The wake engine already captured and transcribed the command.
            self.transcribed.emit(text)
            return
        self._begin_capture()

    def _stop_wake(self) -> None:
        if self._wake is not None:
            self._wake.stop()
            self._wake = None

    def _begin_capture(self, max_duration: float | None = None) -> None:
        with self._spawn_lock:
            if self._capture_running:
                return
            self._capture_running = True
        threading.Thread(
            target=self._capture_and_transcribe,
            args=(max_duration,),
            name="alana-voice",
            daemon=True,
        ).start()

    def _capture_and_transcribe(self, max_duration: float | None = None) -> None:
        try:
            from voice.record import record_push_to_talk

            self.stateChanged.emit("listening")
            record_push_to_talk(
                samplerate=self._sample_rate,
                output_path=self._audio_path,
                device=self._device,
                max_duration=max_duration or self._duration,
            )
            self.stateChanged.emit("thinking")
            text = self._stt.transcribe(self._audio_path).strip()
        except Exception as exc:  # pragma: no cover - hardware/device dependent
            self.errorOccurred.emit(str(exc))
            text = ""
        finally:
            self._capture_running = False
            # If voice mode is still on (wake-triggered), re-arm the listener.
            if self._voice_enabled:
                self._start_wake()

        if text:
            self.transcribed.emit(text)
        else:
            self.stateChanged.emit("idle")

    def shutdown(self) -> None:
        self._voice_enabled = False
        self._stop_wake()