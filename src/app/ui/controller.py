"""QML-facing controller for the ALANA desktop UI.

This is the single bridge between the Qt Quick interface and every Python
service: backend worker, voice pipeline, TTS and the media player. It owns no
visuals; it only exposes state and actions QML can bind to.
"""

from __future__ import annotations

import math
from typing import Any
import threading

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

from ..audio import make_stt, make_tts, make_wake, playback
from ..audio.voice import VoiceController
from ..audio.spotify_bridge import SpotifyBridge
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
# Spotify music panel
    spotifyVisibleChanged = Signal(bool)
    spotifyTitleChanged = Signal(str)
    spotifyArtistChanged = Signal(str)
    spotifyArtworkChanged = Signal(str)
    spotifyPlayingChanged = Signal(bool)

    # Email confirmation dialog
    emailPendingChanged = Signal(bool)
    emailRecipientChanged = Signal(str)
    emailSubjectChanged = Signal(str)
    emailBodyChanged = Signal(str)

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
        self._spotify_visible = False
        self._spotify_title = ""
        self._spotify_artist = ""
        self._spotify_artwork = ""
        self._spotify_playing = False
        self._email_pending = False
        self._pending_email: dict | None = None
        self._email_approved = False
        self._email_response: threading.Event | None = None
        self._email_confirm_timer: QTimer | None = None

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
            self._tts_bridge.finished.connect(self._on_reply_finished)
        except Exception:
            self._tts_bridge = None
        try:
            self._media = playback.MediaBridge(parent=self)
            self._media.mediaOpened.connect(self._on_media_opened)
            self._media.playingChanged.connect(self._on_media_playing)
        except Exception:
            self._media = None

        # Spotify bridge: polls the Web API only while the music panel is open.
        self._spotify_bridge: SpotifyBridge | None = None
        try:
            self._spotify_bridge = SpotifyBridge(
                poll_interval=getattr(settings.spotify, "poll_interval", 3.0),
                parent=self,
            )
            self._spotify_bridge.trackChanged.connect(self._on_spotify_track)
            self._spotify_bridge.playingChanged.connect(self._on_spotify_playing)
        except Exception:
            self._spotify_bridge = None

        # Desktop email confirmation dialog overrides the console prompt.
        if hasattr(self._client, "set_email_confirmation"):
            self._client.set_email_confirmation(self._request_email_confirmation)

        # Voice pipeline (optional-capable: no mic or missing deps -> disabled).
        self._voice: VoiceController | None = None
        self._voice_available = False
        try:
            stt = make_stt(settings)
            voice = VoiceController(
                stt,
                lambda on_wake, on_state=None, engine=None: make_wake(
                    settings, on_wake, on_state, engine
                ),
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
        self._energy_timer.setInterval(66)  # ~15 Hz, tiny cost
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
# -- spotify music panel ---------------------------------------------- #
    @Slot()
    def spotifyTogglePanel(self) -> None:
        self.setSpotifyVisible(not self._spotify_visible)

    @Slot(bool)
    def setSpotifyVisible(self, visible: bool) -> None:
        visible = bool(visible)
        if visible == self._spotify_visible:
            return
        self._spotify_visible = visible
        self.spotifyVisibleChanged.emit(visible)
        if self._spotify_bridge is not None:
            self._spotify_bridge.setActive(visible)
        if visible:
            self._set_orb_state(OrbState.IDLE)

    @Slot(result=bool)
    def spotifyAvailable(self) -> bool:
        return self._spotify_bridge is not None

    @Slot()
    def spotifyPlay(self) -> None:
        if self._spotify_bridge is not None:
            self._spotify_bridge.play()

    @Slot()
    def spotifyPause(self) -> None:
        if self._spotify_bridge is not None:
            self._spotify_bridge.pause()

    @Slot()
    def spotifyToggle(self) -> None:
        if self._spotify_bridge is not None:
            self._spotify_bridge.toggle()

    @Slot()
    def spotifyNext(self) -> None:
        if self._spotify_bridge is not None:
            self._spotify_bridge.next()

    @Slot()
    def spotifyPrevious(self) -> None:
        if self._spotify_bridge is not None:
            self._spotify_bridge.previous()

    @Slot(str)
    def spotifySearch(self, query: str) -> None:
        if self._spotify_bridge is not None and query and query.strip():
            self._spotify_bridge.searchAndPlay(query.strip())

    def _on_spotify_track(self, title: str, artist: str, artwork: str) -> None:
        self._spotify_title = title or ""
        self._spotify_artist = artist or ""
        self._spotify_artwork = artwork or ""
        self.spotifyTitleChanged.emit(self._spotify_title)
        self.spotifyArtistChanged.emit(self._spotify_artist)
        self.spotifyArtworkChanged.emit(self._spotify_artwork)

    def _on_spotify_playing(self, playing: bool) -> None:
        self._spotify_playing = bool(playing)
        self.spotifyPlayingChanged.emit(self._spotify_playing)

    # -- email confirmation dialog ---------------------------------------- #
    def _request_email_confirmation(self, payload: dict) -> bool:
        """Blocking hook called from the worker thread before any email goes out."""
        self._pending_email = dict(payload)
        self._email_approved = False
        self._email_response = threading.Event()
        self._email_pending = True
        self.emailPendingChanged.emit(True)
        self.emailRecipientChanged.emit(str(payload.get("recipient", "")))
        self.emailSubjectChanged.emit(str(payload.get("subject", "")))
        self.emailBodyChanged.emit(str(payload.get("body", "")))
        if self._email_confirm_timer is None:
            self._email_confirm_timer = QTimer(self)
            self._email_confirm_timer.setSingleShot(True)
            self._email_confirm_timer.setInterval(60_000)
            self._email_confirm_timer.timeout.connect(self._auto_reject_email)
        self._email_confirm_timer.start()
        self._email_response.wait()
        return self._email_approved

    def _auto_reject_email(self) -> None:
        self._email_pending = False
        self.emailPendingChanged.emit(False)
        if self._email_response is not None:
            self._email_approved = False
            self._email_response.set()

    @Slot()
    def confirmEmailSend(self) -> None:
        if self._email_response is not None and self._email_pending:
            self._approve_email(True)

    @Slot()
    def cancelEmailSend(self) -> None:
        if self._email_response is not None and self._email_pending:
            self._approve_email(False)

    def _approve_email(self, approved: bool) -> None:
        self._email_pending = False
        self.emailPendingChanged.emit(False)
        if self._email_confirm_timer is not None:
            self._email_confirm_timer.stop()
        self._email_approved = bool(approved)
        if self._email_response is not None:
            self._email_response.set()
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
        self._arm_follow_up()

    def _on_speaking_changed(self, speaking: bool) -> None:
        # Deafen the wake listener while she talks, or she answers herself.
        if self._voice is not None:
            self._voice.setMuted(speaking)
        if speaking:
            self._set_orb_state(OrbState.SPEAKING)
        else:
            self._set_orb_state(OrbState.IDLE)

    def _on_reply_finished(self) -> None:
        """Alana is truly done talking — open the follow-up window."""
        self._set_orb_state(OrbState.IDLE)
        self._arm_follow_up()

    def _arm_follow_up(self) -> None:
        """Open a short hands-free window after her reply, then back to wake."""
        if not getattr(self._settings.wake, "follow_up_enabled", True):
            return
        if not self._voice_mode:
            return
        if self._voice is not None:
            self._voice.beginFollowUp()

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
        self._auto_reject_email()
        if self._spotify_bridge is not None:
            self._spotify_bridge.shutdown()
        if self._voice is not None:
            self._voice.shutdown()
        if self._tts_bridge is not None:
            self._tts_bridge.stop()
        if self._media is not None:
            self._media.stop()
        self._worker.shutdown()
# -- QML properties ------------------------------------------------------ #
    # Spotify panel
    spotifyVisible = Property(bool, lambda self: self._spotify_visible, notify=spotifyVisibleChanged)
    spotifyTitle = Property(str, lambda self: self._spotify_title, notify=spotifyTitleChanged)
    spotifyArtist = Property(str, lambda self: self._spotify_artist, notify=spotifyArtistChanged)
    spotifyArtwork = Property(str, lambda self: self._spotify_artwork, notify=spotifyArtworkChanged)
    spotifyPlaying = Property(bool, lambda self: self._spotify_playing, notify=spotifyPlayingChanged)
    # Email confirmation dialog
    emailPending = Property(bool, lambda self: self._email_pending, notify=emailPendingChanged)
    emailRecipient = Property(str, lambda self: str(self._pending_email.get("recipient", "")) if self._pending_email else "", notify=emailRecipientChanged)
    emailSubject = Property(str, lambda self: str(self._pending_email.get("subject", "")) if self._pending_email else "", notify=emailSubjectChanged)
    emailBody = Property(str, lambda self: str(self._pending_email.get("body", "")) if self._pending_email else "", notify=emailBodyChanged)
