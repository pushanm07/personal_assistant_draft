"""Compatibility wrapper that routes intent decisions through the interpreter."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from brain.composer import Composer
from brain.interpreter import Interpreter


class Brain:
    """Bridge the old brain API to the new interpreter-only contract."""

    def __init__(self) -> None:
        self.interpreter = Interpreter()
        self.composer = Composer()

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
            intent = decision.get("intent")
            platform = decision.get("platform", "auto")
            if isinstance(recipient, str) and recipient.strip():
                if not (isinstance(intent, str) and intent.strip()):
                    intent = input(
                        f"What should I tell {recipient}, Sir? "
                    ).strip()
                # ALANA writes the actual message from the intent; the user
                # never has to hand it a finished line.
                message = self.composer.compose(recipient, intent, platform)
                send_message(recipient, message, platform)
                return True
            print("Please tell me who to message, Sir.")
            return True

        if action == "answer_question":
            answer_handler = actions.get("answer_question")
            if answer_handler:
                answer_handler(prompt)
                return True
            
        if action == "set_reminder":
            set_reminder = actions.get("set_reminder")
            if set_reminder:
                # Pass the full reminder phrase so the parser can extract the
                # reminder text, schedule, and repeat frequency without asking
                # for a verbatim follow-up.
                set_reminder(reminder_request=decision.get("text"))
                return True
            return False


        if action in actions:
            actions[action]()
            return True

        return False

    def think(self, prompt: str) -> dict[str, Any]:
        """Return the interpreter's current best interpretation of the prompt."""
        return self.interpreter.interpret(prompt)

