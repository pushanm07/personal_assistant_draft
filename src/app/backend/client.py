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

import re
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


def _lazy(target: str):
    """Return a callable that imports ``module.function`` on first use.

    Every action in the registry is wrapped this way, so the heavy optional
    dependencies (spotipy, pyautogui, the instagram/whatsapp automation
    modules, ...) are only ever imported when that specific action actually
    runs. A one-song command never pays for the whatsapp stack, and vice
    versa — this is one of the cheapest wins for startup and steady-state RAM.
    """

    module_name, _, func_name = target.rpartition(".")

    def run(*args, **kwargs):
        import importlib

        return getattr(importlib.import_module(module_name), func_name)(
            *args, **kwargs
        )

    run.__name__ = func_name
    return run


def _brain_actions() -> dict[str, Any]:
    """Mirror src/main.py's action registry without importing the CLI.

    Values are lazily-imported callables (see :func:`_lazy`), so building this
    dict is cheap and nothing heavy is loaded until an action actually runs.
    """
    global _BRAIN_ACTIONS
    if _BRAIN_ACTIONS is None:
        _BRAIN_ACTIONS = {
            "spotify": _lazy("actions.spotify.open_spotify"),
            "chrome": _lazy("actions.apps.open_chrome"),
            "vscode": _lazy("actions.apps.open_vscode"),
            "play_song": _lazy("actions.spotify.play_song"),
            "pause_song": _lazy("actions.spotify.pause_song"),
            "resume_song": _lazy("actions.spotify.resume_song"),
            "previous_song": _lazy("actions.spotify.previous_song"),
            "next_song": _lazy("actions.spotify.next_song"),
            "play_playlist": _lazy("actions.spotify.play_playlist"),
            "play_album": _lazy("actions.spotify.play_album"),
            "add_to_playlist": _lazy("actions.spotify.add_song_to_playlist"),
            "authenticate_spotify": _lazy("actions.spotify.authenticate_spotify"),
            "answer_question": _lazy("actions.web.answer_question"),
            "send_whatsapp_message": _lazy("actions.whatsapp.send_message_whatsapp"),
            "send_instagram_message": _lazy("actions.instagram.send_message_instagram"),
            "set_reminder": _lazy("actions.reminder.set_reminder"),
            "send_email": _lazy("actions.email.send_email_command"),
        }
    return _BRAIN_ACTIONS
class InProcessClient:
    """Run the existing Brain in-process inside a worker thread."""

    def __init__(self) -> None:
        self._brain: Any = None
        self.actions: dict[str, Any] | None = None
        # Optional GUI confirmation hook: a blocking callable(dict) -> bool
        # invoked (off the GUI thread) before sending an email. The desktop
        # controller plugs a QML-confirmation closure in here; the CLI leaves
        # it None and uses the built-in console confirmation instead.
        self._confirm_email = None

    def set_email_confirmation(self, handler) -> None:
        self._confirm_email = handler

    def _ensure_brain(self) -> Any:
        if self._brain is None:
            from brain.brain import Brain

            self._brain = Brain()
        return self._brain

    def _ensure_actions(self) -> dict[str, Any]:
        """Load optional desktop integrations only for an actual command."""
        if self.actions is None:
            from actions import instagram, whatsapp

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

            def _send_email(recipient, message, platform="auto"):
                # Allowlist + confirmation live in actions.email; the desktop
                # app supplies its own GUI confirmation hook instead of the
                # console prompt.
                from actions import email as email_actions

                subject = "Message from ALANA"
                if self._confirm_email is not None:
                    if not self._confirm_email(
                        {
                            "recipient": recipient,
                            "subject": subject,
                            "body": message,
                        }
                    ):
                        print("Email cancelled.")
                        return
                    email_actions.send_email(recipient, subject, message, confirm=False)
                else:
                    email_actions.send_email(recipient, subject, message, confirm=True)

            brain = self._ensure_brain()
            brain._send_message = _send_message  # type: ignore[attr-defined]
            brain._send_email = _send_email  # type: ignore[attr-defined]
        return self.actions

    @staticmethod
    def _looks_like_command(text: str) -> bool:
        """Avoid an expensive action-classification pass for normal conversation."""
        return bool(re.search(
            r"\b(open|launch|start|run|play|pause|resume|continue|skip|next|previous|"
            r"message|text|dm|whatsapp|remind|set reminder|send|email|mail|"
            r"playlist|album|add to)\b",
            text,
            flags=re.IGNORECASE,
        ))

    def roundtrip(self, user_text: str) -> dict[str, Any]:
        try:
            brain = self._ensure_brain()
        except Exception as exc:  # pragma: no cover - environment dependent
            return {"kind": "error", "text": str(exc)}

        try:
            # Chat/question turns get one concise call. Knowledge questions are
            # answered from the *live web* by Brain.chat (see brain.brain).
            if not self._looks_like_command(user_text):
                return {"kind": "chat", "text": brain.chat(user_text)}

            actions = self._ensure_actions()
            executed = brain.execute(
                user_text,
                actions,
                brain._send_message,  # type: ignore[attr-defined]
                send_email=brain._send_email,  # type: ignore[attr-defined]
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
