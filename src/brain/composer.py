"""ALANA message composition layer.

This module's only job is to author outgoing messages. Given a short intent
(e.g. "tell zaria i'm late") it writes the full message the user would actually
send, in the right voice for the recipient. It never sends anything itself.

This is the piece that lets ALANA write messages on the user's behalf instead
of parroting whatever fragment appeared in the prompt.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from brain import llm


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PERSONALITY_FILE = PROJECT_ROOT / "config" / "personality.json"
CONTACTS_FILE = PROJECT_ROOT / "config" / "contacts.json"


def _load_json(path: Path) -> dict[str, Any]:
    """Load a JSON object, returning an empty dict on any failure."""
    try:
        with path.open(encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, dict):
            return data
    except (OSError, json.JSONDecodeError):
        pass
    return {}


class Composer:
    """Turn a short intent into a finished, ready-to-send message.

    The composer is the author. The interpreter decides *who* and *what to get
    across*; the composer decides the actual words, shaped by ALANA's
    personality and the recipient's own tone/style profile.
    """

    def __init__(self, model: str = "llama3.2:latest") -> None:
        self.model = model
        self.personality = _load_json(PERSONALITY_FILE)
        self.contacts = {
            name.lower(): profile
            for name, profile in _load_json(CONTACTS_FILE).items()
            if isinstance(name, str) and isinstance(profile, dict)
        }

    def compose(
        self,
        recipient: str | None,
        intent: str | None,
        platform: str = "auto",
    ) -> str | None:
        """Write the message to *recipient* that conveys *intent*.

        Returns the finished message text, or None when there is no intent to
        work with (the caller should ask the user what to say).
        """
        intent = (intent or "").strip()
        if not intent:
            return None

        profile = self.contacts.get((recipient or "").lower().strip())

        if not llm.available:
            return self._fallback(intent)

        content = llm.chat(
            [
                {
                    "role": "system",
                    "content": self._system_prompt(recipient, platform, profile),
                },
                {"role": "user", "content": self._user_prompt(recipient, intent)},
            ],
            model=self.model,
            temperature=0.7,
            num_predict=llm.MAX_COMPOSE_TOKENS,
        )
        if content:
            content = self._clean(content.strip())
            if content:
                return content

        return self._fallback(intent)

    def _user_name(self) -> str:
        """Best guess at the user's own name for first-person framing."""
        for rule in self.personality.get("rules", []):
            if isinstance(rule, str):
                match = re.search(r"\bboss,?\s+([A-Z][a-z]+)", rule)
                if match:
                    return match.group(1)
        return "the user"

    def _voice_block(self, recipient: str | None, profile: dict[str, Any] | None) -> str:
        """Describe how the message to this specific recipient should read."""
        if not profile:
            return (
                "You do not have a saved profile for this person, so keep it "
                "casual, warm and natural — the way a friend texts. Stay concise."
            )

        def render(value: Any) -> str:
            if isinstance(value, list):
                return "; ".join(str(item) for item in value)
            return str(value)

        lines = [f"You are writing to {recipient}. Match this voice:"]
        if profile.get("relationship"):
            lines.append(f"- Relationship: {render(profile['relationship'])}")
        if profile.get("tone"):
            lines.append(f"- Tone: {render(profile['tone'])}")
        if profile.get("style_notes"):
            lines.append(f"- Style: {render(profile['style_notes'])}")
        return "\n".join(lines)

    def _system_prompt(
        self,
        recipient: str | None,
        platform: str,
        profile: dict[str, Any] | None,
    ) -> str:
        """Instruct the model to author the message, not echo the prompt."""
        user = self._user_name()
        channel = platform if platform in {"whatsapp", "instagram"} else "a chat app"

        return (
            f"You are ALANA, {user}'s personal assistant. You are drafting a "
            f"message that {user} will send to {recipient} on {channel}, as if "
            f"{user} wrote it himself.\n\n"
            f"Write in the first person as {user}. The reader is {recipient}.\n\n"
            f"{self._voice_block(recipient, profile)}\n\n"
            "Hard rules:\n"
            "- Output ONLY the final message text. No quotes, no 'Here is', no "
            "options, no explanation, no sign-off, no subject line.\n"
            "- Write the FULL message, properly constructed. Do NOT just repeat "
            "the instruction back — turn it into something a person would "
            "genuinely send. 'tell him i'm late' should become an actual note "
            "like 'hey, running a bit behind, be there soon'.\n"
            "- Preserve the intent exactly. Do NOT invent facts, names, times, "
            "reasons or commitments that were not given.\n"
            "- Sound human and natural. Match length to the intent — usually one "
            "or two short sentences.\n"
            "- Do not address the reader as 'Sir'. Avoid emojis unless the voice "
            "above clearly calls for them."
        )

    @staticmethod
    def _user_prompt(recipient: str | None, intent: str) -> str:
        """Frame the raw intent for the author model."""
        return (
            f"Draft the message to {recipient}. Here is what I want to get "
            f"across:\n{intent}"
        )

    @staticmethod
    def _clean(text: str) -> str:
        """Strip preambles and wrapping quotes the model sometimes adds."""
        lines = [line.strip() for line in text.splitlines()]
        # Drop a leading "Sure, here's the message:" style preamble line.
        while lines and re.match(
            r"^(sure|okay|ok|here'?s?|got it|alright|message)\b.*:\s*$",
            lines[0],
            flags=re.IGNORECASE,
        ):
            lines.pop(0)
        cleaned = "\n".join(line for line in lines if line).strip()
        # Remove a single pair of wrapping quotes.
        if len(cleaned) >= 2 and cleaned[0] in "\"'“”" and cleaned[-1] in "\"'“”":
            cleaned = cleaned[1:-1].strip()
        return cleaned

    @staticmethod
    def _fallback(intent: str) -> str:
        """Offline best effort: send the intent as-is with a capital first letter."""
        intent = intent.strip()
        if not intent:
            return intent
        return intent[0].upper() + intent[1:]
