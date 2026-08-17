"""Playback bridges: reply TTS (edge-tts) and the local media player.

Both use ``QMediaPlayer``/``QAudioOutput`` which Qt requires to live on the
GUI thread; all heavy work (edge-tts synthesis streamed from the network,
file I/O) happens on worker threads that signal back here.
"""

from __future__ import annotations

import tempfile
import threading
from pathlib import Path

from PySide6.QtCore import Q_ARG, QMetaObject, QObject, Qt, QUrl, Signal, Slot
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

from .tts import TTSEngine


class TTSBridge(QObject):
    """Speak ALANA's replies aloud using the configured engine."""

    speakingChanged = Signal(bool)

    def __init__(self, engine: TTSEngine, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._engine = engine
        self._player = QMediaPlayer(self)
        self._audio = QAudioOutput(self)
        self._player.setAudioOutput(self._audio)
        self._player.mediaStatusChanged.connect(self._on_status)
        self._speaking = False

        self._workdir = Path(tempfile.gettempdir()) / "alana_tts"
        self._workdir.mkdir(parents=True, exist_ok=True)
        self._counter = 0

    def is_speaking(self) -> bool:
        return self._speaking

    @Slot(str)
    def speak(self, text: str) -> None:
        if not text or not text.strip():
            return
        self.stop()
        self._counter += 1
        out = self._workdir / f"tts_{self._counter}.mp3"
        threading.Thread(
            target=self._synthesize,
            args=(text, out),
            name="alana-tts",
            daemon=True,
        ).start()

    def _synthesize(self, text: str, out: Path) -> None:
        try:
            self._engine.synthesize(text, str(out))
            # Playback must occur on the GUI thread.
            QMetaObject.invokeMethod(
                self,
                "_play",
                Qt.ConnectionType.QueuedConnection,
                Q_ARG(str, str(out)),
            )
        except Exception:  # pragma: no cover - network/provider dependent
            pass

    @Slot(str)
    def _play(self, path: str) -> None:
        self._set_speaking(True)
        self._player.setSource(QUrl.fromLocalFile(path))
        self._player.play()

    @Slot()
    def stop(self) -> None:
        self._player.stop()
        self._set_speaking(False)

    def _on_status(self, status) -> None:
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self._set_speaking(False)

    def _set_speaking(self, value: bool) -> None:
        if value != self._speaking:
            self._speaking = value
            self.speakingChanged.emit(value)


class MediaBridge(QObject):
    """Minimal local media (audio/video) player surfaced to the UI."""

    mediaOpened = Signal()
    mediaChanged = Signal(str)  # display title
    playingChanged = Signal(bool)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._player = QMediaPlayer(self)
        self._audio = QAudioOutput(self)
        self._player.setAudioOutput(self._audio)
        self._player.mediaStatusChanged.connect(self._on_status)
        self._player.playbackStateChanged.connect(self._on_playback)
        self._title = ""
        self._playing = False

    # Exposed so QML can bind a VideoOutput for video files.
    @property
    def player(self) -> QMediaPlayer:
        return self._player

    @Slot(str)
    def openFile(self, path: str) -> None:
        p = Path(path)
        if not p.is_file():
            return
        self._title = p.name
        self._player.setSource(QUrl.fromLocalFile(str(p)))
        self.mediaChanged.emit(self._title)
        self.mediaOpened.emit()
        self._player.play()

    @Slot()
    def play(self) -> None:
        self._player.play()

    @Slot()
    def pause(self) -> None:
        self._player.pause()

    @Slot()
    def stop(self) -> None:
        self._player.stop()

    @Slot()
    def toggle(self) -> None:
        if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._player.pause()
        else:
            self._player.play()

    @Slot(float)
    def setVolume(self, volume: float) -> None:
        self._audio.setVolume(min(1.0, max(0.0, volume)))

    @Slot()
    def positionMs(self) -> int:
        return int(self._player.position())

    @Slot()
    def durationMs(self) -> int:
        return int(self._player.duration())

    @Slot()
    def title(self) -> str:
        return self._title

    @property
    def isPlaying(self) -> bool:
        return self._playing

    def _set_playing(self, value: bool) -> None:
        value = bool(value)
        if value != self._playing:
            self._playing = value
            self.playingChanged.emit(value)

    def _on_status(self, _status) -> None:
        pass

    def _on_playback(self, state) -> None:
        playing = state == QMediaPlayer.PlaybackState.PlayingState
        self._set_playing(playing)
