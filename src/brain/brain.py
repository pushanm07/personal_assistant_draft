"""Compatibility wrapper that routes intent decisions through the interpreter."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from brain.interpreter import Interpreter


class Brain:
    """Bridge the old brain API to the new interpreter-only contract."""

    def __init__(self) -> None:
        self.interpreter = Interpreter()

    def execute(
        self,
        prompt: str,
        actions: dict[str, Callable[..., None]],
        send_message: Callable[..., None],
    ) -> bool:
        """Interpret *prompt* and run a matching action if the registry supports it."""
        decision = self.think(prompt)
        action = decision.get("action")

        if action == "open_app":
            target = decision.get("target")
            if isinstance(target, str) and target.strip():
                action_handler = actions.get(target)
                if action_handler:
                    action_handler()
                    return True
            return False

        if action == "play_song":
            song = decision.get("song")
            if isinstance(song, str) and song.strip():
                play_song = actions.get("play_song")
                if play_song:
                    play_song(song)
                    return True
            print("Please tell me which song to play, Sir.")
            return True

        if action == "send_message":
            recipient = decision.get("recipient")
            message = decision.get("message")
            platform = decision.get("platform", "auto")
            if isinstance(recipient, str) and recipient.strip():
                send_message(recipient, message, platform)
                return True
            print("Please tell me who to message, Sir.")
            return True

        if action == "answer_question":
            answer_handler = actions.get("answer_question")
            if answer_handler:
                answer_handler(prompt)
                return True

        if action in actions:
            actions[action]()
            return True

        return False

    def think(self, prompt: str) -> dict[str, Any]:
        """Return the interpreter's current best interpretation of the prompt."""
        return self.interpreter.interpret(prompt)

