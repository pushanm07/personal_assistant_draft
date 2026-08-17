"""Wake-word detection.

Priority: *never* run a heavy speech model continuously. The default engine
is a lightweight amplitude/VAD gate that costs a tiny fraction of a CPU core
and only wakes full speech recognition when sound above a threshold arrives.
It still runs ONLY while Voice Mode is enabled.

``engine="porcupine"`` (configure ``access_key``/``model_path``) swaps in a
real keyword detector behind the same interface.
"""

from __future__ import annotations

import math
import threading
from typing import Callable, Protocol

import numpy as np
import sounddevice as sd


class WakeWordEngine(Protocol):
    is_running: bool

    def start(self) -> None: ...

    def stop(self) -> None: ...


def _rms(block: np.ndarray) -> float:
    if block.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(block.astype(np.float64) ** 2)))


class EnergyWake:
    """Low-cost amplitude gate. No model, just RMS over small audio blocks."""

    def __init__(
        self,
        threshold: float = 0.045,
        min_active_blocks: int = 2,
        block_ms: int = 40,
        sample_rate: int = 16000,
        device: int | None = None,
        on_wake: Callable[[], None] | None = None,
    ) -> None:
        self.threshold = threshold
        self.min_active_blocks = max(1, min_active_blocks)
        self.block_ms = block_ms
        self.sample_rate = sample_rate
        self.device = device
        self.on_wake = on_wake
        self.is_running = False
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self.is_running:
            return
        self.is_running = True
        self._stop.clear()
        self._thread = threading.Thread(target=self._listen, name="alana-wake", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self.is_running = False
        self._stop.set()

    def _listen(self) -> None:
        blocksize = max(1, int(self.sample_rate * self.block_ms / 1000))
        active = 0
        try:
            with sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype="float32",
                blocksize=blocksize,
                device=self.device,
            ) as stream:
                while not self._stop.is_set():
                    block, _overflowed = stream.read(blocksize)
                    level = _rms(block.reshape(-1))
                    if level >= self.threshold:
                        active += 1
                        if active >= self.min_active_blocks:
                            self.stop()
                            if self.on_wake is not None:
                                self.on_wake()
                            return
                    else:
                        active = 0
        except Exception:
            self.stop()


class PorcupineWake:
    """Optional real wake word via Picovoice Porcupine (pip install pvporcupine)."""

    def __init__(
        self,
        access_key: str,
        keywords: list[str] | None = None,
        model_path: str = "",
        on_wake: Callable[[], None] | None = None,
        device: int | None = None,
    ) -> None:
        if not access_key:
            raise ValueError("PorcupineWake requires a Picovoice access key.")
        import pvporcupine

        self._pv = pvporcupine
        self.access_key = access_key
        self.keywords = keywords or ["alana"]
        self.model_path = model_path
        self.on_wake = on_wake
        self.device = device
        self.is_running = False
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self.is_running:
            return
        import sounddevice as sd  # noqa: F401  (validates availability)

        self.is_running = True
        self._stop.clear()
        self._thread = threading.Thread(target=self._listen, name="alana-wake", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self.is_running = False
        self._stop.set()

    def _listen(self) -> None:
        kwargs = {} if not self.model_path else {"model_path": self.model_path}
        porcupine = self._pv.create(
            access_key=self.access_key,
            keywords=self.keywords,
            **kwargs,
        )
        try:
            with sd.InputStream(
                samplerate=porcupine.sample_rate,
                channels=1,
                dtype="int16",
                blocksize=porcupine.frame_length,
                device=self.device,
            ) as stream:
                while not self._stop.is_set():
                    block, _overflowed = stream.read(porcupine.frame_length)
                    index = porcupine.process(block.reshape(-1))
                    if index >= 0:
                        self.stop()
                        if self.on_wake is not None:
                            self.on_wake()
                        return
        except Exception:
            pass
        finally:
            porcupine.delete()


def make_wake(settings, on_wake: Callable[[], None]) -> WakeWordEngine:
    """Build the wake engine selected by config/desktop.json."""
    wake = settings.wake
    if wake.engine == "porcupine":
        return PorcupineWake(
            access_key=wake.access_key,
            keywords=wake.keywords,
            model_path=wake.model_path,
            on_wake=on_wake,
            device=settings.stt.device,
        )
    if wake.engine == "energy":
        return EnergyWake(
            threshold=wake.threshold,
            min_active_blocks=wake.min_active_blocks,
            block_ms=wake.block_ms,
            sample_rate=settings.stt.sample_rate,
            device=settings.stt.device,
            on_wake=on_wake,
        )
    raise ValueError(f"Unknown wake engine: {wake.engine!r}")