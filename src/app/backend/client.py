"""Backend clients — the frontend's only channel to Alana's Brain.

Two interchangeable transports:

- ``InProcessClient`` (default): runs the existing ``Brain`` in a worker
  thread inside this process. Fastest possible path — no serialization, no
  second process — which matters first for *speed* and *low RAM*.
- ``HttpClient``: talks to the FastAPI layer in ``src/server`` over local
  HTTP. Lets the Brain run as a service while the UI stays thin.

Both implement the same small contract, so swapping is a config change.
"""

from __future__ import annotations

from typing import Any, Protocol

import requests


# --------------------------------------------------------------------------- #
# Transport contract
# --------------------------------------------------------------------------- #
class BackendClient(Protocol):
    def roundtrip(self, user_text: str) -> dict[str, Any]:
        """Run a full user turn and return a result dict.

        Result shape (shared by both transports):
            {"kind": "answer"|"action"|"chat"|"error",
             "text": response text, ...}
        """
        ...


# --------------------------------------------------------------------------- #
# In-process transport (loads Brain lazily on first turn so startup is fast)
# --------------------------------------------------------------------------- #
_BRAIN_ACTIONS: dict[str, Any] | None = None


def _brain_actions() -> dict[str, Any]:
    """Mirror src/main.py's action registry without importing the CLI."""
    global _BRAIN_ACTIONS
    if _BRAIN_ACTIONS is None:
        # Lazy: importing actions pulls in pyautogui/spotipy etc. — do it in
        # the worker thread once, off the critical start path.
        from actions.apps import open_chrome, open_vscode
        from actions.instagram import send_message_instagram
        from actions.reminder import set_reminder
        from actions.spotify import (
            authenticate_spotify,
            next_song,
            open_spotify,
            pause_song,
            play_song,
            previous_song,
            resume_song,
        )
        from actions.web import answer_question
        from actions.whatsapp import send_message_whatsapp

        _BRAIN_ACTIONS = {
            "spotify": open_spotify,
            "chrome": open_chrome,
            "vscode": open_vscode,
            "play_song": play_song,
            "pause_song": pause_song,
            "resume_song": resume_song,
            "previous_song": previous_song,
            "next_song": next_song,
            "authenticate_spotify": authenticate_spotify,
            "answer_question": answer_question,
            "send_whatsapp_message": send_message_whatsapp,
            "send_instagram_message": send_message_instagram,
            "set_reminder": set_reminder,
        }
    return _BRAIN_ACTIONS
class InProcessClient:
    """Run the existing Brain in-process inside a worker thread."""

    def __init__(self) -> None:
        self._brain: Any = None
        self.actions: dict[str, Any] | None = None

    def _ensure_brain(self) -> Any:
        if self._brain is None:
            from brain.brain import Brain
            from actions import instagram, whatsapp

            brain = Brain()
            self.actions = _brain_actions()

            def _send_message(recipient, message, platform="auto"):
                if platform == "whatsapp":
                    whatsapp.send_message_whatsapp(recipient, message)
                elif platform == "instagram":
                    instagram.send_message_instagram(recipient, message)
                elif instagram.has_contact(recipient):
                    instagram.send_message_instagram(recipient, message)
                elif whatsapp.has_contact(recipient):
                    whatsapp.send_message_whatsapp(recipient, message)
                else:
                    print(f"No contact named {recipient} on IG or WhatsApp.")

            brain._send_message = _send_message  # type: ignore[attr-defined]
            self._brain = brain
        return self._brain

    def roundtrip(self, user_text: str) -> dict[str, Any]:
        try:
            brain = self._ensure_brain()
        except Exception as exc:  # pragma: no cover - environment dependent
            return {"kind": "error", "text": str(exc)}

        try:
            executed = brain.execute(
                user_text,
                self.actions,
                brain._send_message,  # type: ignore[attr-defined]
            )
            if executed:
                return {"kind": "action", "text": "", "handled": True}
            reply = brain.chat(user_text)
            return {"kind": "chat", "text": reply}
        except Exception as exc:
            return {"kind": "error", "text": f"Error: {exc}"}


# --------------------------------------------------------------------------- #
# HTTP transport (talks to the FastAPI layer in src/server)
# --------------------------------------------------------------------------- #
class HttpClient:
    def __init__(self, host: str = "127.0.0.1", port: int = 8000, timeout: float = 90.0) -> None:
        self.base_url = f"http://{host}:{port}"
        self.timeout = timeout

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = requests.post(
            f"{self.base_url}{path}",
            json=payload,
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()

    def roundtrip(self, user_text: str) -> dict[str, Any]:
        try:
            routed = self._post("/v1/route", {"text": user_text})
        except requests.RequestException as exc:
            return {"kind": "error", "text": f"Backend unreachable: {exc}"}

        decision = routed.get("decision", {})
        execution = routed.get("execution", "chat")
        if execution == "headless":
            return {
                "kind": "answer",
                "text": routed.get("result", ""),
                "decision": decision,
            }
        if execution == "chat":
            return {"kind": "chat", "text": routed.get("reply", "")}
        return {
            "kind": "action",
            "text": routed.get("note", ""),
            "handled": False,
            "decision": decision,
        }


def make_client(settings) -> BackendClient:
    """Build the transport selected by config/desktop.json."""
    if settings.backend.mode == "http":
        return HttpClient(
            host=settings.backend.host,
            port=settings.backend.port,
            timeout=settings.backend.timeout,
        )
    return InProcessClient()