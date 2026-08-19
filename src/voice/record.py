"""Audio recording utilities for ALANA's voice input.

Captures microphone audio as 16 kHz mono (the native rate faster-whisper
expects) and writes it to a WAV file.

Design notes
------------
Recording is done through a **freshly opened and closed** ``sd.InputStream``
on every call rather than the module-global ``sd.rec()`` / ``sd.wait()``
helpers.  Those helpers share a single persistent PortAudio stream, and on
Windows that stream is not reliably reset between calls -- the second and
subsequent recordings would come back as pure silence.  Owning the stream
per-call guarantees clean device state every time.

On top of that we do lightweight voice-activity detection: ALANA waits for
you to start talking, then records until you stop (or a hard cap is hit),
so there's no awkward fixed-length window to race against.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import sounddevice as sd
import soundfile as sf

try:  # Windows key polling for push-to-talk stop; optional elsewhere.
    import msvcrt
except ImportError:  # pragma: no cover - non-Windows
    msvcrt = None

# ALANA records at 16 kHz mono -- the native sample rate Whisper expects.
DEFAULT_SAMPLE_RATE = 16_000

# Hard ceiling on a single utterance (seconds).  Recording always stops here.
DEFAULT_MAX_DURATION = 15.0

# How long to wait for speech to begin before giving up (seconds).
START_TIMEOUT = 8.0

# Once speech has started, stop after this much trailing silence (seconds).
TRAILING_SILENCE = 1.0

# RMS amplitude (int16 scale) above which a block counts as speech.
SILENCE_THRESHOLD = 350

# Audio is processed in blocks of this many milliseconds.
BLOCK_MS = 50


def list_input_devices() -> list[dict]:
    """Return the available input (recording-capable) devices."""
    devices = []
    for index, info in enumerate(sd.query_devices()):
        if info["max_input_channels"] > 0:
            devices.append({"index": index, **info})
    return devices


def _print_available_devices() -> None:
    print(
        "  No audio detected -- check that your microphone is selected and "
        "not muted. Available input devices:"
    )
    for info in list_input_devices():
        print(f"    [{info['index']}] {info['name']}")


def _rms(block: np.ndarray) -> float:
    """Root-mean-square amplitude of an int16 audio block."""
    if block.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(block.astype(np.float64) ** 2)))


def record_voice(
    duration: float = DEFAULT_MAX_DURATION,
    samplerate: int = DEFAULT_SAMPLE_RATE,
    output_path: str = "voice.wav",
    device: int | str | None = None,
) -> str:
    """Record a single spoken utterance and save it to a WAV file.

    Waits (up to ``START_TIMEOUT``) for you to start speaking, records until
    you stop (``TRAILING_SILENCE`` of quiet) or ``duration`` seconds elapse,
    then writes the audio to ``output_path``.

    Parameters
    ----------
    duration:
        Maximum recording length in seconds (hard cap).
    samplerate:
        Sample rate in Hz (16 000 is ideal for Whisper).
    output_path:
        Where to write the ``.wav`` file.
    device:
        Input device index or name.  ``None`` uses the system default.

    Returns
    -------
    str
        The path the recording was written to.
    """
    blocksize = max(1, int(samplerate * BLOCK_MS / 1000))
    max_blocks = int(duration * 1000 / BLOCK_MS)
    start_timeout_blocks = int(START_TIMEOUT * 1000 / BLOCK_MS)
    trailing_silence_blocks = max(1, int(TRAILING_SILENCE * 1000 / BLOCK_MS))

    collected: list[np.ndarray] = []
    speech_started = False
    silent_run = 0

    print("🎙️  Listening...")

    # Defensively clear any lingering global stream state before we open ours.
    try:
        sd.stop()
    except Exception:
        pass

    # A fresh, fully-owned stream per call -- this is what makes repeated
    # recordings reliable on Windows.
    with sd.InputStream(
        samplerate=samplerate,
        channels=1,
        dtype="int16",
        blocksize=blocksize,
        device=device,
    ) as stream:
        for block_index in range(max_blocks):
            block, _overflowed = stream.read(blocksize)
            block = block.reshape(-1)
            level = _rms(block)

            if not speech_started:
                if level >= SILENCE_THRESHOLD:
                    speech_started = True
                    collected.append(block.copy())
                elif block_index >= start_timeout_blocks:
                    # Nobody spoke within the window -- return quiet.
                    break
                continue

            collected.append(block.copy())
            if level < SILENCE_THRESHOLD:
                silent_run += 1
                if silent_run >= trailing_silence_blocks:
                    break
            else:
                silent_run = 0

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    if not speech_started or not collected:
        _print_available_devices()
        # Write a tiny silent buffer so downstream code has a valid file.
        sf.write(str(output), np.zeros(1, dtype="int16"), samplerate)
        return str(output)

    audio = np.concatenate(collected)
    sf.write(str(output), audio, samplerate)
    return str(output)


def _stop_key_pressed() -> bool:
    """True once the user taps Enter or Space to end a push-to-talk capture."""
    if msvcrt is None:
        return False
    pressed = False
    # Drain everything buffered so a fast tap is never missed.
    while msvcrt.kbhit():
        key = msvcrt.getch()
        if key in (b"\r", b"\n", b" "):
            pressed = True
    return pressed


def record_push_to_talk(
    samplerate: int = DEFAULT_SAMPLE_RATE,
    output_path: str = "voice.wav",
    device: int | str | None = None,
    max_duration: float = 60.0,
) -> str:
    """Record on demand (push-to-talk) rather than listening continuously.

    The caller has already signalled intent to speak, so recording starts
    immediately and keeps everything. It stops when any of these happen:

    - the user taps Enter or Space (an explicit "I'm done"),
    - they trail off into silence after having spoken, or
    - ``max_duration`` seconds elapse (a safety cap).

    Returns the path the recording was written to.
    """
    blocksize = max(1, int(samplerate * BLOCK_MS / 1000))
    max_blocks = int(max_duration * 1000 / BLOCK_MS)
    trailing_silence_blocks = max(1, int(TRAILING_SILENCE * 1000 / BLOCK_MS))

    collected: list[np.ndarray] = []
    speech_started = False
    silent_run = 0

    print("🎙️  Recording... (tap Enter or Space to stop)")

    try:
        sd.stop()
    except Exception:
        pass

    with sd.InputStream(
        samplerate=samplerate,
        channels=1,
        dtype="int16",
        blocksize=blocksize,
        device=device,
    ) as stream:
        for _ in range(max_blocks):
            if _stop_key_pressed():
                break

            block, _overflowed = stream.read(blocksize)
            block = block.reshape(-1)
            collected.append(block.copy())

            level = _rms(block)
            if level >= SILENCE_THRESHOLD:
                speech_started = True
                silent_run = 0
            elif speech_started:
                silent_run += 1
                if silent_run >= trailing_silence_blocks:
                    break

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    if not speech_started or not collected:
        _print_available_devices()
        sf.write(str(output), np.zeros(1, dtype="int16"), samplerate)
        return str(output)

    audio = np.concatenate(collected)
    sf.write(str(output), audio, samplerate)
    return str(output)
