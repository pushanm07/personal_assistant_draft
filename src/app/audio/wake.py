"""Wake-word detection.

Runs ONLY while Voice Mode is enabled. Nothing here is armed until
``VoiceController.setVoiceMode(True)`` builds an engine.

The default ``engine="keyword"`` (:class:`KeywordWake`) owns *one* microphone
stream for the whole session: a cheap RMS gate decides when somebody is
talking, that short utterance alone goes through the small Whisper model, and
the wake word is matched against the text. Because the stream is never
reopened, waking straight into the command capture loses no audio and can't
collide with PortAudio on Windows.

``engine="porcupine"`` (configure ``access_key``/``model_path``) swaps in a
real keyword detector, and ``engine="energy"`` is the bare amplitude gate.
Both hand back an empty string, meaning "capture the command yourself".
"""

from __future__ import annotations

import difflib
import re
import tempfile
import threading
from collections import deque
from pathlib import Path
from typing import Callable, Protocol

import numpy as np
import sounddevice as sd


class WakeWordEngine(Protocol):
    is_running: bool

    def start(self) -> None: ...

    def stop(self) -> None: ...

    def set_muted(self, muted: bool) -> None: ...

    def trigger(self) -> bool: ...


def _rms(block: np.ndarray) -> float:
    if block.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(block.astype(np.float64) ** 2)))


# Whisper-tiny spells the name a dozen ways; treat all of them as a hit.
_WAKE_VARIANTS = (
    "alana", "alanna", "alaina", "alena", "allana", "elana", "elena",
    "ilana", "ulana", "lana", "alonna", "alarna",
)
_WORD_RE = re.compile(r"[A-Za-z0-9']+")


def _match_wake(text: str, variants: tuple[str, ...]) -> int | None:
    """Return the char offset just past the wake word, or None if absent.

    Words are joined in pairs as well as singly so a transcript that splits
    the name ("a lana", "uh lana") still matches.
    """
    tokens = list(_WORD_RE.finditer(text))
    lowered = [t.group(0).lower() for t in tokens]
    for i in range(len(tokens)):
        for span in (1, 2):
            if i + span > len(tokens):
                continue
            candidate = "".join(lowered[i : i + span])
            if len(candidate) < 4:
                continue
            for variant in variants:
                if candidate == variant or (
                    # Short variants ("lana") only ever match exactly — fuzzing
                    # them turns "plan a" into a wake word.
                    len(variant) >= 5
                    and abs(len(candidate) - len(variant)) <= 2
                    and difflib.SequenceMatcher(None, candidate, variant).ratio() >= 0.87
                ):
                    return tokens[i + span - 1].end()
    return None


class EnergyWake:
    """Low-cost amplitude gate. No model, just RMS over small audio blocks."""

    def __init__(
        self,
        threshold: float = 0.045,
        min_active_blocks: int = 2,
        block_ms: int = 40,
        sample_rate: int = 16000,
        device: int | None = None,
        on_wake: Callable[[str], None] | None = None,
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

    def set_muted(self, muted: bool) -> None:
        """No-op: this engine stops itself on every wake."""

    def trigger(self) -> bool:
        return False

    def _listen(self) -> None:
        blocksize = max(1, int(self.sample_rate * self.block_ms / 1000))
        active = 0
        fired = False
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
                            fired = True
                            break
                    else:
                        active = 0
        except Exception:
            self.stop()
        # Fired only once the stream is closed: the capture that follows opens
        # its own device and must not race this one.
        if fired and self.on_wake is not None:
            self.on_wake("")


class PorcupineWake:
    """Optional real wake word via Picovoice Porcupine (pip install pvporcupine)."""

    def __init__(
        self,
        access_key: str,
        keywords: list[str] | None = None,
        model_path: str = "",
        on_wake: Callable[[str], None] | None = None,
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

    def set_muted(self, muted: bool) -> None:
        """No-op: this engine stops itself on every wake."""

    def trigger(self) -> bool:
        return False

    def _listen(self) -> None:
        kwargs = {} if not self.model_path else {"model_path": self.model_path}
        porcupine = self._pv.create(
            access_key=self.access_key,
            keywords=self.keywords,
            **kwargs,
        )
        fired = False
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
                        fired = True
                        break
        except Exception:
            pass
        finally:
            porcupine.delete()
        if fired and self.on_wake is not None:
            self.on_wake("")


class KeywordWake:
    """Wake word by transcript match, on a single long-lived mic stream.

    Cheap loop: an RMS gate finds the boundaries of an utterance, and only
    that utterance (typically under two seconds) is handed to the small
    Whisper model. No model runs on silence.

    Once the wake word lands, the *same* stream keeps recording the command,
    so nothing is clipped while a second device is opened. If the wake word
    and the command arrive together ("Alana, what's the weather") the tail of
    the transcript is used directly and no second capture is needed.
    """

    def __init__(
        self,
        stt,
        *,
        keywords: list[str] | None = None,
        threshold: float = 500.0,        # RMS on the int16 scale
        block_ms: int = 32,
        min_active_blocks: int = 2,
        sample_rate: int = 16000,
        device: int | None = None,
        utterance_max: float = 6.0,      # cap on a wake-phrase capture
        command_max: float = 12.0,       # cap on a command capture
        command_timeout: float = 6.0,    # how long we wait for the command
        trailing_silence: float = 0.9,
        on_wake: Callable[[str], None] | None = None,
        on_state: Callable[[str], None] | None = None,
    ) -> None:
        self._stt = stt
        self.keywords = tuple(
            dict.fromkeys(
                [k.lower() for k in (keywords or []) if k] + list(_WAKE_VARIANTS)
            )
        )
        self.threshold = threshold
        self.block_ms = block_ms
        self.min_active_blocks = max(1, min_active_blocks)
        self.sample_rate = sample_rate
        self.device = device
        self.utterance_max = utterance_max
        self.command_max = command_max
        self.command_timeout = command_timeout
        self.trailing_silence = trailing_silence
        self.on_wake = on_wake
        self.on_state = on_state

        self.is_running = False
        self._stop = threading.Event()
        self._muted = threading.Event()
        self._triggered = threading.Event()
        # Hands-free follow-up window armed right after Alana finishes a reply.
        self._follow_up = threading.Event()
        self._follow_up_duration = 4.0
        self._thread: threading.Thread | None = None
        self._clip = str(Path(tempfile.gettempdir()) / "alana_wake_clip.wav")

    # -- lifecycle ------------------------------------------------------ #
    def start(self) -> None:
        if self.is_running:
            return
        self.is_running = True
        self._stop.clear()
        self._muted.clear()
        self._triggered.clear()
        self._follow_up.clear()
        self._thread = threading.Thread(target=self._run, name="alana-wake", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self.is_running = False
        self._stop.set()

    def set_muted(self, muted: bool) -> None:
        """Deafen the loop while Alana is speaking, so she can't wake herself."""
        if muted:
            self._muted.set()
        else:
            self._muted.clear()

    def trigger(self) -> bool:
        """Jump straight to a command capture (push-to-talk). True if armed."""
        if not self.is_running:
            return False
        self._triggered.set()
        return True

    def begin_follow_up(self, duration: float = 4.0) -> bool:
        """Open a short hands-free listening window after a reply.

        Any speech inside the window is transcribed and fired as a command
        *without* requiring the wake word. The window self-expires after
        ``duration`` seconds of silence and the engine falls back to
        wake-word mode. No extra stream or model is spun up — it reuses the
        same RMS gate + single long-lived microphone already owned here.

        Returns True when armed (engine running), False otherwise.
        """
        if not self.is_running:
            return False
        self._follow_up_duration = max(0.5, float(duration))
        self._follow_up.set()
        return True

    # -- internals ------------------------------------------------------ #
    def _emit(self, state: str) -> None:
        if self.on_state is not None:
            self.on_state(state)

    def _run(self) -> None:
        blocksize = max(1, int(self.sample_rate * self.block_ms / 1000))
        while not self._stop.is_set():
            try:
                with sd.InputStream(
                    samplerate=self.sample_rate,
                    channels=1,
                    dtype="int16",
                    blocksize=blocksize,
                    device=self.device,
                ) as stream:
                    self._loop(stream, blocksize)
            except Exception:
                # Device busy/unplugged: back off briefly and re-open.
                if self._stop.wait(0.75):
                    return

    def _loop(self, stream, blocksize: int) -> None:
        while not self._stop.is_set():
            if self._triggered.is_set():
                self._triggered.clear()
                self._command_flow(stream, blocksize)
                continue

            # Hands-free follow-up window: any speech fires without a wake word.
            if self._follow_up.is_set():
                self._follow_up_flow(stream, blocksize)
                continue

            audio = self._record(stream, blocksize, self.utterance_max, start_timeout=None)
            if audio is None:
                continue
            text = self._transcribe(audio)
            if not text:
                continue
            end = _match_wake(text, self.keywords)
            if end is None:
                continue

            remainder = text[end:].strip(" ,.!?:;-—")
            if len(_WORD_RE.findall(remainder)) >= 2:
                self._emit("thinking")
                self._fire(remainder)
            else:
                self._command_flow(stream, blocksize)

    def _follow_up_flow(self, stream, blocksize: int) -> None:
        """One-shot hands-free capture window after Alana's last reply.

        Uses the same RMS gate as normal wake listening — the model only runs
        if somebody actually speaks, and the whole window is bounded by
        ``self._follow_up_duration`` so nothing keeps listening forever.
        """
        self._emit("listening")
        audio = self._record(
            stream, blocksize, self.command_max, start_timeout=self._follow_up_duration
        )
        # One window per reply; VoiceController re-arms it after the next reply.
        self._follow_up.clear()
        if audio is None:
            self._emit("idle")
            return
        self._emit("thinking")
        text = self._transcribe(audio)
        if text:
            self._fire(text)
        else:
            self._emit("idle")

    def _command_flow(self, stream, blocksize: int) -> None:
        self._emit("listening")
        audio = self._record(
            stream, blocksize, self.command_max, start_timeout=self.command_timeout
        )
        if audio is None:
            self._emit("idle")
            return
        self._emit("thinking")
        text = self._transcribe(audio)
        if text:
            self._fire(text)
        else:
            self._emit("idle")

    def _fire(self, text: str) -> None:
        if self.on_wake is not None:
            self.on_wake(text)

    def _record(
        self,
        stream,
        blocksize: int,
        max_seconds: float,
        start_timeout: float | None,
    ) -> np.ndarray | None:
        """Read one utterance. Returns None on silence/mute/stop.

        ``start_timeout=None`` waits indefinitely for speech (the idle wake
        gate); a number gives up after that many seconds of quiet.
        """
        blocks_per_sec = 1000.0 / self.block_ms
        max_blocks = int(max_seconds * blocks_per_sec)
        silence_limit = max(1, int(self.trailing_silence * blocks_per_sec))
        wait_limit = None if start_timeout is None else int(start_timeout * blocks_per_sec)
        preroll_len = max(1, int(0.32 * blocks_per_sec))

        preroll: deque[np.ndarray] = deque(maxlen=preroll_len)
        collected: list[np.ndarray] = []
        active = 0
        silent = 0
        waited = 0

        while not self._stop.is_set():
            block, _overflowed = stream.read(blocksize)
            block = block.reshape(-1).copy()

            if self._muted.is_set():
                if collected:
                    return None
                preroll.clear()
                active = 0
                continue

            loud = _rms(block) >= self.threshold

            if not collected:
                preroll.append(block)
                if loud:
                    active += 1
                    if active >= self.min_active_blocks:
                        collected.extend(preroll)
                        preroll.clear()
                else:
                    active = 0
                    waited += 1
                    if wait_limit is not None and waited >= wait_limit:
                        return None
                    if self._triggered.is_set() and wait_limit is None:
                        return None
                continue

            collected.append(block)
            if loud:
                silent = 0
            else:
                silent += 1
                if silent >= silence_limit:
                    break
            if len(collected) >= max_blocks:
                break

        if not collected or self._stop.is_set():
            return None
        return np.concatenate(collected)

    def _transcribe(self, audio: np.ndarray) -> str:
        if audio.size < self.sample_rate * 0.3:   # under 300 ms: not speech
            return ""
        try:
            import soundfile as sf

            sf.write(self._clip, audio, self.sample_rate)
            return (self._stt.transcribe(self._clip) or "").strip()
        except Exception:
            return ""


def make_wake(
    settings,
    on_wake: Callable[[str], None],
    on_state: Callable[[str], None] | None = None,
    stt=None,
) -> WakeWordEngine:
    """Build the wake engine selected by config/desktop.json."""
    wake = settings.wake
    if wake.engine == "keyword":
        if stt is None:
            raise ValueError("The 'keyword' wake engine needs an STT engine.")
        return KeywordWake(
            stt,
            keywords=wake.keywords,
            threshold=wake.speech_threshold,
            block_ms=wake.block_ms,
            min_active_blocks=wake.min_active_blocks,
            sample_rate=settings.stt.sample_rate,
            device=settings.stt.device,
            command_max=settings.stt.record_duration,
            command_timeout=wake.command_timeout,
            on_wake=on_wake,
            on_state=on_state,
        )
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