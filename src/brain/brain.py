"""Compatibility wrapper that routes intent decisions through the interpreter."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from brain import llm
from brain.composer import Composer
from brain.interpreter import Interpreter

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PERSONALITY_FILE = PROJECT_ROOT / "config" / "personality.json"

# Questions that should be answered from the *live web*, not the model's
# (possibly stale) internal knowledge. Anything matching these is routed to
# actions.web.get_answer() before the model is ever consulted.
_KNOWLEDGE_Q_RE = re.compile(r"\b(what|who|where|when|why|how)\b", re.IGNORECASE)
# Command-ish verbs — "how do I open spotify" is a command, not a fact query.
_COMMAND_VERBS_RE = re.compile(
    r"\b(open|launch|start|run|play|pause|resume|close|stop|send|message|dm|"
    r"remind|set|create|delete|add|remove|install|update|download|email|mail)\b",
    re.IGNORECASE,
)
# Personal / self-referential questions that would be nonsense on a search page.
_SELF_REFERENTIAL = {
    "how are you", "how are you doing", "how are you today", "how do you do",
    "how's it going", "how is it going", "how's everything", "what's up",
    "whats up", "sup", "who are you", "what are you", "what do you do",
    "what can you do", "what's your name", "what is your name",
    "how do you work", "how does it work", "what time is it",
    "what is the time", "what day is it", "what is the date",
    "what is today's date", "what's today's date", "what is today",
    "what's happening", "whats happening", "how is the weather",
    "what's the weather", "whats the weather", "how old are you",
}


def _looks_like_knowledge_question(text: str) -> bool:
    """True when *text* is a fact/current-info question best served by the web."""
    cleaned = re.sub(r"\s+", " ", (text or "").lower()).strip().strip("?.,!")
    if not cleaned or len(cleaned.split()) < 3:
        return False
    if cleaned in _SELF_REFERENTIAL:
        return False
    # "what's my ..." is personal/local, never a web fact.
    if re.search(r"\b(my|me|i|we|us|you|your)\b", cleaned):
        if re.search(r"\b(what|how|why|where|when)\b", cleaned) and re.search(
            r"\b(my|me)\b", cleaned
        ):
            return False
    if _COMMAND_VERBS_RE.search(cleaned):
        return False
    return bool(_KNOWLEDGE_Q_RE.search(cleaned))


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
        send_email: Callable[..., None] | None = None,
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

        if action == "send_email":
            recipient = decision.get("recipient")
            intent = decision.get("intent")
            if isinstance(recipient, str) and recipient.strip():
                if not (isinstance(intent, str) and intent.strip()):
                    intent = input(
                        f"What should I email {recipient}, Sir? "
                    ).strip()
                message = self.composer.compose(recipient, intent, "email")
                handler = send_email or actions.get("send_email")
                if handler is None:
                    print("Email is not available, Sir.")
                    return True
                handler(recipient, message)
                return True
            print("Please tell me who to email, Sir.")
            return True

        if action in ("play_playlist", "play_album"):
            target = decision.get("target") or decision.get("song")
            if isinstance(target, str) and target.strip():
                handler = actions.get(action)
                if handler:
                    handler(target)
                    return True
            print(f"Please tell me which {'playlist' if action == 'play_playlist' else 'album'} to play, Sir.")
            return True

        if action == "add_to_playlist":
            song = decision.get("song")
            playlist = decision.get("playlist")
            if isinstance(song, str) and song.strip() and isinstance(playlist, str) and playlist.strip():
                handler = actions.get("add_to_playlist")
                if handler:
                    handler(song, playlist)
                    return True
            print("Tell me the song and the playlist, Sir.")
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

        Knowledge questions (facts / current events / people / places) are
        answered from the *live web* first — the local model's training data is
        stale, so "who is the president" must not be answered from a snapshot.
        """
        if _looks_like_knowledge_question(prompt):
            try:
                from actions.web import get_answer

                answer = get_answer(prompt)
                if answer and answer.strip():
                    return answer.strip()
            except Exception:  # pragma: no cover - network dependent
                pass

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

