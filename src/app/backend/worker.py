"""Off-main-thread executor for backend requests.

The GUI thread must never block on Alana's (Ollama-driven) Brain. A single
daemon worker thread pulls user turns off a queue and emits results back on
Qt signals, which are delivered to the GUI thread via queued connections.
"""

from __future__ import annotations

import queue
import threading

from PySide6.QtCore import QObject, Signal, Slot


class BackendWorker(QObject):
    responseReady = Signal(dict)
    errorOccurred = Signal(str)

    def __init__(self, client, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._client = client
        self._queue: queue.Queue[str | None] = queue.Queue()
        self._stop = threading.Event()
        self._thread = threading.Thread(
            target=self._run_loop,
            name="alana-backend",
            daemon=True,
        )
        self._thread.start()

    @Slot(str)
    def submit(self, user_text: str) -> None:
        if user_text and user_text.strip():
            self._queue.put(user_text.strip())

    def shutdown(self) -> None:
        self._stop.set()
        self._queue.put(None)

    def _run_loop(self) -> None:
        while not self._stop.is_set():
            try:
                item = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue
            if item is None:
                break
            try:
                result = self._client.roundtrip(item)
                self.responseReady.emit(dict(result))
            except Exception as exc:  # pragma: no cover - defensive
                self.errorOccurred.emit(str(exc))