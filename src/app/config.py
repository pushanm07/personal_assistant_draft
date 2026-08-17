"""Desktop application configuration for ALANA.

Everything the frontend needs that can be tuned *without touching code* lives
here and may be overridden from ``config/desktop.json``. This module is the
frontend's boundary: it never imports Brain, so wiring a different backend,
TTS voice or wake-word provider is always a config change, not a code change.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DESKTOP_CONFIG_FILE = PROJECT_ROOT / "config" / "desktop.json"

# --------------------------------------------------------------------------- #
# Crimson palette (avoids gold/orange entirely).
# --------------------------------------------------------------------------- #
PALETTE = { # A nice, beautiful purple/violet
    "background": "#0A0114",       # Deep, dark purple, almost black
    "backgroundAlt": "#140226",    # Slightly lighter dark purple
    "hudLine": "#3C1A5B",          # Muted violet for structural lines
    "hudText": "#6A4C9C",          # Soft purple for secondary text
    "accent": "#8A2BE2",           # Vibrant blue-violet for primary focus
    "accentHot": "#A45EFF",        # A brighter, more electric purple for highlights
    "core": "#D0A0FF",             # Light lavender for the hottest core elements
    "wine": "#2C0059",             # A deep, rich wine purple for contrast
    "page": "#1F0F33",             # Dark purple for page backgrounds
    "textPrimary": "#F2E6FF",      # Very light lavender, almost white, for main text
    "textDim": "#9E8AAE",          # Greyish-purple for less important text
}


@dataclass
class WindowConfig:
    width: int = 980
    height: int = 760
    min_width: int = 760
    min_height: int = 560
    title: str = "ALANA"


@dataclass
class OrbConfig:
    """The orb is tuned to look expensive but stay cheap on the CPU.

    ``fps_idle`` / ``fps_active`` are adaptive: the particle layer redraws
    slowly when nothing is happening and speeds up only while listening,
    thinking or speaking. ``particle_count`` is the visible drifting elements.
    """
 
    fps_idle: int = 6
    fps_active: int = 12
    particle_count: int = 12
    low_power: bool = True  # idle slows to ~10fps when the window is unfocused
    active_fraction: float = 0.6  # orb occupies ~60% of the main screen


@dataclass
class TTSConfig:
    provider: str = "edge-tts"          # provider key; edge-tts initially
    voice: str = "en-US-JennyNeural"    # configurable female voice
    rate: str = "+12%"                  # speaking rate
    pitch: str = "+0Hz"                 # pitch shift
    enabled: bool = True                # speak replies aloud


@dataclass
class STTConfig:
    engine: str = "whisper"             # replaceable speech engine
    model: str = "tiny"                 # 'tiny' keeps RAM low; 'small' for quality
    language: str = "en"
    sample_rate: int = 16000
    record_duration: float = 12.0
    device: int | None = None


@dataclass
class WakeConfig:
    """Wake word is only active while Voice Mode is enabled.

    ``engine="energy"`` is the zero-dependency lightweight default: a low-cost
    amplitude/VAD gate wakes full speech recognition when sound above the
    threshold is detected. No heavy model runs continuously. Set
    ``engine="porcupine"`` and provide ``access_key`` to use a real wake word.
    """

    engine: str = "energy"
    threshold: float = 0.045            # RMS gate for the energy engine
    min_active_blocks: int = 2          # consecutive loud blocks to confirm
    block_ms: int = 40
    keywords: list[str] = field(default_factory=lambda: ["alana"])
    access_key: str = ""
    model_path: str = ""


@dataclass
class BackendConfig:
    """How the UI talks to Alana's existing Brain.

    ``inprocess`` (default) runs Brain in a worker thread of this process: no
    serialization, no second process, lowest RAM and latency. ``http`` talks
    to the FastAPI layer in ``src/server``, which must be running.
    """

    mode: str = "inprocess"
    host: str = "127.0.0.1"
    port: int = 8000
    timeout: float = 90.0


@dataclass
class Settings:
    window: WindowConfig = field(default_factory=WindowConfig)
    orb: OrbConfig = field(default_factory=OrbConfig)
    tts: TTSConfig = field(default_factory=TTSConfig)
    stt: STTConfig = field(default_factory=STTConfig)
    wake: WakeConfig = field(default_factory=WakeConfig)
    backend: BackendConfig = field(default_factory=BackendConfig)


def _merge(target, override) -> None:
    """Merge a plain dict `override` into a dataclass-backed `target`.

    If `target` has an attribute matching a key in `override` and that
    attribute is itself a dataclass (or object with attributes), recurse
    into it instead of replacing it with a raw dict. This preserves
    typed configuration objects like `Settings.backend`.
    """
    for key, value in (override or {}).items():
        if not hasattr(target, key):
            continue
        current = getattr(target, key)
        # If the override is a dict and the current value is an object
        # (dataclass instance), merge into it recursively.
        if isinstance(value, dict) and not isinstance(current, dict):
            _merge(current, value)
        else:
            setattr(target, key, value)


def load_settings() -> Settings:
    """Load defaults, then merge config/desktop.json if present."""
    settings = Settings()
    if not DESKTOP_CONFIG_FILE.is_file():
        return settings
    try:
        with DESKTOP_CONFIG_FILE.open(encoding="utf-8") as handle:
            raw = json.load(handle)
        _merge(settings, raw)
    except (OSError, json.JSONDecodeError):
        pass
    return settings


def palette_map() -> dict:
    """Palette as a plain dict for embedding into the QML context."""
    return dict(PALETTE)