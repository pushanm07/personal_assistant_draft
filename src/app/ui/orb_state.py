"""Orb animation states shared between Python and QML."""


class OrbState:
    IDLE = "idle"
    TYPING = "typing"
    LISTENING = "listening"
    THINKING = "thinking"
    EXECUTING = "executing"
    SPEAKING = "speaking"
    ERROR = "error"


# State -> target visual intensity (0..1) the orb uses to modulate movement.
STATE_INTENSITY = {
    OrbState.IDLE: 0.15,
    OrbState.TYPING: 0.35,
    OrbState.LISTENING: 0.6,
    OrbState.THINKING: 0.7,
    OrbState.EXECUTING: 0.65,
    OrbState.SPEAKING: 0.85,
    OrbState.ERROR: 0.9,
}
