# ALANA Desktop Frontend

A futuristic, frameless desktop interface for Alana built with **PySide6 + QML**.

## Architecture

```
ALANA APP
│
├── UI (PySide6 + QML)
│   ├── main.qml          Main interface (frameless, dark, HUD)
│   ├── Orb.qml           Central crimson holographic intelligence core
│   ├── controller.py     QML ↔ Python bridge (state + actions)
│   ├── orb_state.py      Explicit orb states
│   └── config.py         Tunable config (palette, TTS, STT, wake, window)
│
└── ALANA BACKEND (existing Brain, untouched)
    ├── Brain / Interpreter / Planner / Actions
    ├── Tools / Memory / Personality / Speech
    └── app/backend/       In-process or HTTP transport to Brain
```

## Orb States

| State | Trigger | Visual |
|-------|---------|--------|
| `IDLE` | nothing happening | slow breathing, alive but restrained |
| `TYPING` | user entering text | orb slightly more active |
| `LISTENING` | voice capture | orb expands, outer elements active |
| `THINKING` | brain processing | rotating scan, layers at different speeds |
| `EXECUTING` | running an action | brief focused burst |
| `SPEAKING` | TTS playing | pulses with speech amplitude |
| `ERROR` | failure | red alert flash → back to IDLE |

## Run

```bash
# From the project root (activate venv first)
pip install -r requirements.txt
python -m src.app
```

### Easiest Windows launch

Double-click **`Launch ALANA.cmd`** in the project folder. It uses the local
`.venv` automatically when present; otherwise it uses the installed Python 3.
On a new machine, run `pip install -r requirements.txt` once first.

## Voice Mode

- OFF by default. Toggle with **[VOICE]** button.
- While ON: a lightweight wake-word listener runs (energy/VAD gate by default).
  No heavy STT model is loaded until speech is captured.
- Wake word: say **"Alana"** (configurable in `config/desktop.json`).
- For a real keyword detector, set `wake.engine = "porcupine"` and provide an
  `access_key` from Picovoice.

## TTS

- Uses `edge-tts` (online). Voice/rate/pitch are configurable in
  `config/desktop.json` under `tts`. Easy to swap for a local engine later.

## Config

All frontend tuning lives in `config/desktop.json` (no code changes needed):

```json
{
  "tts":  { "provider": "edge-tts", "voice": "en-US-JennyNeural", "rate": "+12%", "pitch": "+0Hz" },
  "stt":  { "engine": "whisper", "model": "tiny" },
  "wake": { "engine": "energy", "threshold": 0.045, "keywords": ["alana"] },
  "orb":  { "fpsIdle": 24, "particleCount": 64 },
  "backend": { "mode": "inprocess" }
}
```
