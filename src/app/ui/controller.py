"""QML-facing controller for the ALANA desktop UI.

This is the single bridge between the Qt Quick interface and every Python
service: backend worker, voice pipeline, TTS and the media player. It owns no
visuals; it only exposes state and actions QML can bind to.
"""

from __future__ import annotations

import math
from typing import Any

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

from ..audio import make_stt, make_tts, make_wake, playback
from ..audio.voice import VoiceController
from ..backend.client import make_client
from ..backend.worker import BackendWorker
from .orb_state import OrbState, STATE_INTENSITY


class AppController(QObject):
    # -- exposed to QML -------------------------------------------------- #
    orbStateChanged = Signal(str)
    orbEnergyChanged = Signal(float)
    conversationAppended = Signal(object)   # {"role": str, "text": str}
    voiceModeChanged = Signal(bool)
    voiceAvailableChanged = Signal(bool)
    miniChanged = Signal(bool)
        
    quitRequested = Signal()
    backendError = Signal(str)
    wakeDetected = Signal()
    mediaOpenChanged = Signal(bool)
    mediaPlayingChanged = Signal(bool)

    def __init__(self, settings, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._settings = settings
        self._orb_state = OrbState.IDLE
        self._orb_energy = 0.0
        self._voice_mode = False
        self._mini = False
        self._media_open = False
        self._media_playing = False
        self._media_pos = 0

        # Backend worker (in-process by default). Brain loads lazily on demand.
        self._client = make_client(settings)
        self._worker = BackendWorker(self._client, parent=self)
        self._worker.responseReady.connect(self._on_backend_result)
        self._worker.errorOccurred.connect(self._on_backend_error)

        # TTS + media (both must live on the GUI thread).
        self._tts_bridge: playback.TTSBridge | None = None
        self._media: playback.MediaBridge | None = None
        try:
            tts_engine = make_tts(settings)
            self._tts_bridge = playback.TTSBridge(tts_engine, parent=self)
            self._tts_bridge.speakingChanged.connect(self._on_speaking_changed)
        except Exception:
            self._tts_bridge = None
        try:
            self._media = playback.MediaBridge(parent=self)
            self._media.mediaOpened.connect(self._on_media_opened)
            self._media.playingChanged.connect(self._on_media_playing)
        except Exception:
            self._media = None

        # Voice pipeline (optional-capable: no mic or missing deps -> disabled).
        self._voice: VoiceController | None = None
        self._voice_available = False
        try:
            stt = make_stt(settings)
            voice = VoiceController(
                stt,
                lambda on_wake: make_wake(settings, on_wake),
                sample_rate=settings.stt.sample_rate,
                record_duration=settings.stt.record_duration,
                device=settings.stt.device,
            )
            voice.stateChanged.connect(self._on_voice_state)
            voice.transcribed.connect(self._on_transcribed)
            voice.errorOccurred.connect(self._on_voice_error)
            voice.wakeDetected.connect(self.wakeDetected)
            self._voice = voice
            self._voice_available = True
        except Exception:
            self._voice = None
            self._voice_available = False

        # Lightweight energy driver: only active while speaking/listening.
        self._energy_timer = QTimer(self)
        self._energy_timer.setInterval(40)  # ~25 Hz, tiny cost
        self._energy_timer.timeout.connect(self._pump_energy)
        self._energy_phase = 0.0

    # -- QML properties ------------------------------------------------- #
    def _get_orb_state(self) -> str:
        return self._orb_state

    def _get_orb_energy(self) -> float:
        return self._orb_energy

    def _get_voice_mode(self) -> bool:
        return self._voice_mode

    def _get_voice_available(self) -> bool:
        return self._voice_available

    def _get_mini(self) -> bool:
        return self._mini

    def _get_media_open(self) -> bool:
        return self._media_open

    def _get_media_playing(self) -> bool:
        return self._media_playing

    orbState = Property(str, _get_orb_state, notify=orbStateChanged)
    orbEnergy = Property(float, _get_orb_energy, notify=orbEnergyChanged)
    voiceMode = Property(bool, _get_voice_mode, notify=voiceModeChanged)
    voiceAvailable = Property(bool, _get_voice_available, notify=voiceAvailableChanged)
    mini = Property(bool, _get_mini, notify=miniChanged)
    mediaOpen = Property(bool, _get_media_open, notify=mediaOpenChanged)
    mediaPlaying = Property(bool, _get_media_playing, notify=mediaPlayingChanged)

    # -- internal state helpers ----------------------------------------- #
    def _set_orb_state(self, state: str) -> None:
        if state == self._orb_state:
            return
        self._orb_state = state
        self.orbStateChanged.emit(state)
        if state in (OrbState.SPEAKING, OrbState.LISTENING, OrbState.EXECUTING):
            if not self._energy_timer.isActive():
                self._energy_timer.start()
        else:
            if self._energy_timer.isActive():
                self._energy_timer.stop()
            if self._orb_energy != 0.0:
                self._orb_energy = 0.0
                self.orbEnergyChanged.emit(0.0)

    def _pump_energy(self) -> None:
        """Smooth talking pulse; listening gets a low restless motion; executing gets focused bursts."""
        self._energy_phase += 0.18
        if self._orb_state == OrbState.SPEAKING:
            level = 0.5 + 0.5 * math.sin(self._energy_phase)
        elif self._orb_state == OrbState.LISTENING:
            level = 0.25 + 0.2 * abs(math.sin(self._energy_phase * 0.7))
        elif self._orb_state == OrbState.EXECUTING:
            level = 0.3 + 0.35 * abs(math.sin(self._energy_phase * 2.5))
        else:
            self._energy_timer.stop()
            level = 0.0
        if abs(level - self._orb_energy) > 0.005:
            self._orb_energy = level
            self.orbEnergyChanged.emit(level)
# -- slots called from QML ------------------------------------------ #
    @Slot(str)
    def send(self, text: str) -> None:
        text = (text or "").strip()
        if not text:
            return
        self._append_conversation("user", text)
        self.voice_stop()
        self._set_orb_state(OrbState.THINKING)
        self._worker.submit(text)

    @Slot(str)
    def setTyping(self, typing: str) -> None:
        """Input changed: 'typing' while text exists, 'idle' when cleared."""
        if typing == "typing":
            if self._orb_state == OrbState.IDLE:
                self._set_orb_state(OrbState.TYPING)
        else:
            if self._orb_state in (OrbState.TYPING, OrbState.IDLE):
                self._set_orb_state(OrbState.IDLE)

    @Slot()
    def markIdle(self) -> None:
        if self._orb_state in (OrbState.TYPING, OrbState.IDLE):
            self._set_orb_state(OrbState.IDLE)

    @Slot(bool)
    def setVoiceMode(self, enabled: bool) -> None:
        if self._voice is None:
            self.backendError.emit("Voice input is not available on this system.")
            return
        enabled = bool(enabled)
        if enabled:
            # Wake-word listening starts (lightweight; STT model not loaded).
            self._voice.setVoiceMode(True)
        else:
            self._voice.setVoiceMode(False)
            self.voice_stop()
        self._voice_mode = enabled
        self.voiceModeChanged.emit(enabled)

    @Slot()
    def toggleVoice(self) -> None:
        if self._voice is None:
            self.backendError.emit("Voice input is not available on this system.")
            return
        self.setVoiceMode(not self._voice_mode)

    @Slot()
    def listenPushToTalk(self) -> None:
        if self._voice is not None:
            self._set_orb_state(OrbState.LISTENING)
            self._voice.listenPushToTalk()

    @Slot()
    def stopSpeaking(self) -> None:
        if self._tts_bridge is not None:
            self._tts_bridge.stop()

    @Slot(bool)
    def setMini(self, mini: bool) -> None:
        self._mini = bool(mini)
        self.miniChanged.emit(self._mini)

    @Slot()
    def quit(self) -> None:
        self.quitRequested.emit()

    # -- media ---------------------------------------------------------- #
    @Slot(str)
    def openMedia(self, path: str) -> None:
        if self._media is None:
            return
        local = path
        if path and str(path).lower().startswith("file:"):
            from PySide6.QtCore import QUrl
            local = QUrl(path).toLocalFile()
        if local:
            self._media.openFile(local)

    @Slot()
    def toggleMedia(self) -> None:
        if self._media is not None:
            self._media.toggle()

    @Slot(float)
    def setMediaVolume(self, volume: float) -> None:
        if self._media is not None:
            self._media.setVolume(volume)

    @Slot(result=int)
    def mediaPosition(self) -> int:
        return self._media.positionMs() if self._media is not None else 0

    @Slot(result=int)
    def mediaDuration(self) -> int:
        return self._media.durationMs() if self._media is not None else 0

    @Slot(result=str)
    def mediaTitle(self) -> str:
        return self._media.title() if self._media is not None else ""
# -- backend results ------------------------------------------------ #
    def _on_backend_result(self, result: dict[str, Any]) -> None:
        kind = result.get("kind", "chat")
        if kind == "error":
            self.backendError.emit(result.get("text", "unknown error"))
            self._set_orb_state(OrbState.ERROR)
            # Auto-return to IDLE after brief error flash
            QTimer.singleShot(1500, lambda: self._set_orb_state(OrbState.IDLE))
            return

        text = result.get("text") or ""
        if kind == "action":
            # Flash EXECUTING state for actions
            self._set_orb_state(OrbState.EXECUTING)
            if not result.get("handled"):
                text = text or "Done."
            elif not text:
                text = "Done."
        elif kind == "answer" and not text:
            text = "I couldn't find a reliable answer for that, Sir."
        self._append_conversation("alana", text)
        self._present_reply(text)

    def _on_backend_error(self, message: str) -> None:
        self.backendError.emit(message)
        self._set_orb_state(OrbState.ERROR)
        QTimer.singleShot(1500, lambda: self._set_orb_state(OrbState.IDLE))

    def _present_reply(self, text: str) -> None:
        if self._tts_bridge is not None and self._settings.tts.enabled:
            if text and text != "Done.":
                self._tts_bridge.speak(text)
                return
        self._set_orb_state(OrbState.IDLE)

    def _on_speaking_changed(self, speaking: bool) -> None:
        if speaking:
            self._set_orb_state(OrbState.SPEAKING)
        else:
            self._set_orb_state(OrbState.IDLE)

    def _on_media_opened(self) -> None:
        self._media_open = True
        self.mediaOpenChanged.emit(True)
        self._media_playing = True
        self.mediaPlayingChanged.emit(True)

    def _on_media_playing(self, playing: bool) -> None:
        self._media_playing = bool(playing)
        self.mediaPlayingChanged.emit(self._media_playing)

    # -- voice ---------------------------------------------------------- #
    def _on_voice_state(self, state: str) -> None:
        if state in ("listening", "thinking"):
            self._set_orb_state(state)
        elif state == "idle":
            if self._orb_state in (OrbState.LISTENING, OrbState.THINKING):
                self._set_orb_state(OrbState.IDLE)

    def _on_transcribed(self, text: str) -> None:
        self.send(text)

    def _on_voice_error(self, message: str) -> None:
        self.backendError.emit(message)
        self._set_orb_state(OrbState.ERROR)
        QTimer.singleShot(1500, lambda: self._set_orb_state(OrbState.IDLE))

    @Slot()
    def voice_stop(self) -> None:
        if self._voice is not None:
            self._voice.stopListening()

    # -- misc ----------------------------------------------------------- #
    def _append_conversation(self, role: str, text: str) -> None:
        if not text:
            return
        self.conversationAppended.emit({"role": role, "text": text})

    def shutdown(self) -> None:
        self._energy_timer.stop()
        if self._voice is not None:
            self._voice.shutdown()
        if self._tts_bridge is not None:
            self._tts_bridge.stop()
        if self._media is not None:
            self._media.stop()
        self._worker.shutdown()