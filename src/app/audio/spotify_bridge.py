"""Spotify bridge for the ALANA desktop UI.

Owns a single daemon thread that — only while the music panel is visible —
polls the Spotify Web API every ``poll_interval`` seconds for the current
track and exposes play/pause/next/previous/search controls to QML. When the
panel is hidden the thread blocks on an event with no timer running and makes
zero network calls, keeping idle resources minimal.
"""

from __future__ import annotations

import threading

from PySide6.QtCore import QObject, Signal, Slot


class SpotifyBridge(QObject):
    # title, artist, artwork-url emitted whenever the now-playing track changes.
    trackChanged = Signal(str, str, str)
    playingChanged = Signal(bool)
    errorOccurred = Signal(str)

    def __init__(self, poll_interval: float = 3.0, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._poll_interval = max(1.0, float(poll_interval))
        self._active = False
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._poll_enabled = threading.Event()
        self._last_snapshot: dict | None = None
        self._thread = threading.Thread(target=self._run, name="alana-spotify", daemon=True)
        self._thread.start()

    # -- slots for QML --------------------------------------------------- #
    @Slot(bool)
    def setActive(self, active: bool) -> None:
        active = bool(active)
        if active == self._active:
            return
        self._active = active
        if active:
            self._poll_enabled.set()
            self.refresh()
        else:
            self._poll_enabled.clear()

    @Slot()
    def refresh(self) -> None:
        """Wake the poller immediately (used after a control action)."""
        self._wake.set()

    @Slot()
    def play(self) -> None:
        self._invoke_async(self._control, "resume_song")

    @Slot()
    def pause(self) -> None:
        self._invoke_async(self._control, "pause_song")

    @Slot()
    def toggle(self) -> None:
        snapshot = self._last_snapshot
        if snapshot and snapshot.get("playing"):
            self.pause()
        else:
            self.play()

    @Slot()
    def next(self) -> None:
        self._invoke_async(self._control, "next_song")

    @Slot()
    def previous(self) -> None:
        self._invoke_async(self._control, "previous_song")

    @Slot(str)
    def searchAndPlay(self, query: str) -> None:
        def run() -> None:
            from actions.spotify import play_song

            play_song(query)
            self._wake.set()

        threading.Thread(target=run, name="alana-spotify-action", daemon=True).start()

    def shutdown(self) -> None:
        self._poll_enabled.clear()
        self._stop.set()
        self._wake.set()

    # -- internals ------------------------------------------------------- #
    @staticmethod
    def _invoke_async(fn, *args) -> None:
        threading.Thread(target=fn, args=args, name="alana-spotify-action", daemon=True).start()

    @staticmethod
    def _control(action: str) -> None:
        from actions import spotify as spotify_actions

        handler = getattr(spotify_actions, action, None)
        if handler is not None:
            handler()

    def _run(self) -> None:
        self._wake.clear()
        while not self._stop.is_set():
            if self._poll_enabled.is_set():
                self._poll_once()
                self._wake.wait(self._poll_interval)
                self._wake.clear()
            else:
                # Inactive: block until activated, refreshed, or stopped.
                self._wake.wait()
                self._wake.clear()

    def _poll_once(self) -> None:
        try:
            from actions.spotify import get_playback_state

            snapshot = get_playback_state()
        except Exception:
            snapshot = None
        if snapshot is None:
            return
        if self._last_snapshot == snapshot:
            return
        self._last_snapshot = snapshot
        self.trackChanged.emit(
            snapshot.get("title") or "",
            snapshot.get("artist") or "",
            snapshot.get("artwork") or "",
        )
        self.playingChanged.emit(bool(snapshot.get("playing")))
