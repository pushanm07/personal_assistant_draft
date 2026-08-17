"""Speech-to-text transcription using faster-whisper.

The Whisper model is loaded lazily and cached so that the (potentially
slow) first-run download only happens once per process.
"""

from __future__ import annotations

import os

from faster_whisper import WhisperModel

# Module-level cache so we don't reload the model on every call.
_model: WhisperModel | None = None


def _get_model(model_name: str = "small") -> WhisperModel:
    """Lazily initialise and cache the Whisper model.

    We run int8-quantised inference across all CPU cores: on CPU this is
    several times faster than the default float path with negligible impact
    on transcription quality, which keeps voice latency low.
    """
    global _model
    if _model is None:
        print(
            f"Loading Whisper model '{model_name}' "
            "(first run may download ~244 MB)..."
        )
        _model = WhisperModel(
            model_name,
            device="cpu",
            compute_type="int8",
            cpu_threads=os.cpu_count() or 4,
        )
    return _model


def warm_up(model_name: str = "small") -> None:
    """Preload the model so the first transcription doesn't pay load cost."""
    try:
        _get_model(model_name)
    except Exception:  # pragma: no cover - best effort
        pass


def transcribe_audio(
    audio_path: str = "voice.wav",
    model_name: str = "small",
    language: str = "en",
) -> str:
    """Transcribe an audio file to text using Whisper.

    Parameters
    ----------
    audio_path:
        Path to the WAV file to transcribe.
    model_name:
        Whisper model size — ``tiny``, ``small``, ``medium``, or ``large``.
    language:
        ISO-639-1 language code (``"en"`` for English).

    Returns
    -------
    str
        The transcribed text, or an empty string on failure.
    """
    # A near-empty file means no speech was captured -- skip the model call
    # (the WAV header alone is ~44 bytes; anything under a fraction of a
    # second of audio isn't worth transcribing).
    if not os.path.exists(audio_path) or os.path.getsize(audio_path) < 1024:
        return ""

    model = _get_model(model_name)
    segments, _ = model.transcribe(
        audio_path,
        language=language,
        # VAD skips long stretches of silence up front, so Whisper only decodes
        # the actual speech — a steady speed win on most real recordings.
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 500},
        condition_on_previous_text=False,
        beam_size=1,
    )

    text = "".join(segment.text for segment in segments).strip()
    return text
