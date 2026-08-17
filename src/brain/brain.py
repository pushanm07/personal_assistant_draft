"""Compatibility wrapper that routes intent decisions through the interpreter."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from brain import llm
from brain.composer import Composer
from brain.interpreter import Interpreter

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PERSONALITY_FILE = PROJECT_ROOT / "config" / "personality.json"


class Brain:
    """Bridge the old brain API to the new interpreter-only contract."""

    def __init__(self) -> None:
        self.interpreter = Interpreter()
        self.composer = Composer()
        self.personality = self._load_personality()

    @staticmethod
    def _load_personality() -> dict[str, Any]:
        """Load ALANA's personality so conversational replies stay in voice."""
        try:
            with PERSONALITY_FILE.open(encoding="utf-8") as handle:
                data = json.load(handle)
            if isinstance(data, dict):
                return data
        except (OSError, json.JSONDecodeError):
            pass
        return {}

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

    def _chat_system_prompt(self) -> str:
        """Describe how ALANA should sound when just talking to the user."""
        name = self.personality.get("name", "ALANA")
        tone = self.personality.get(
            "tone", "polished, concise, discreet, lightly witty"
        )
        address = self.personality.get("user_address", ["Sir"])
        address_hint = address[0] if isinstance(address, list) and address else "Sir"
        rules = self.personality.get("rules", [])
        rules_block = "\n".join(f"- {rule}" for rule in rules if isinstance(rule, str))

        return (
            f"You are {name}, {address_hint}'s personal AI assistant — think "
            f"J.A.R.V.I.S. Your tone is {tone}. You may address the user as "
            f"{address_hint}.\n\n"
            "You are talking directly to your user, not executing a command. "
            "Reply conversationally and helpfully in your own voice.\n\n"
            "Style rules:\n"
            "- Be genuinely helpful and answer directly from your own knowledge.\n"
            "- Keep it short and natural — usually one to three sentences.\n"
            "- No filler openers, no lists unless truly needed, no emojis.\n"
            f"{rules_block}"
        )

    def chat(self, prompt: str) -> str:
        """Answer the user conversationally when no concrete action fits.

        This is the graceful fallback for anything the command router does not
        recognise, and the path for plain questions the user asks ALANA itself.
        """
        reply = llm.chat(
            [
                {"role": "system", "content": self._chat_system_prompt()},
                {"role": "user", "content": prompt},
            ],
            temperature=0.6,
            num_predict=100,
        )
        if reply and reply.strip():
            return reply.strip()

        address = self.personality.get("user_address", ["Sir"])
        address_hint = address[0] if isinstance(address, list) and address else "Sir"
        return f"I'm not sure how to help with that yet, {address_hint}."

