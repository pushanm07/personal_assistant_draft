"""ALANA language understanding layer.

This module's only job is to read raw user text and return a clean,
structured interpretation for the rest of the project. It does not open apps,
play media, send messages, or otherwise execute anything.
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

KNOWN_APPS = {
    "spotify": "spotify",
    "chrome": "chrome",
    "vscode": "vscode",
    "vs code": "vscode",
    "visual studio code": "vscode",
}

CONFIGURED_ACTIONS = {
    "open_app",
    "play_song",
    "pause_song",
    "resume_song",
    "previous_song",
    "next_song",
    "send_message",
    "answer_question",
    "none",
    "set_reminder"
}


def load_personality() -> dict[str, Any]:
    """Load ALANA's editable personality settings."""
    with PERSONALITY_FILE.open(encoding="utf-8") as personality_file:
        personality = json.load(personality_file)

    if not isinstance(personality, dict):
        raise ValueError("config/personality.json must contain a JSON object.")
    return personality


def load_contacts() -> dict[str, dict[str, Any]]:
    """Load contact-specific writing preferences."""
    with CONTACTS_FILE.open(encoding="utf-8") as contacts_file:
        contacts = json.load(contacts_file)

    if not isinstance(contacts, dict):
        raise ValueError("config/contacts.json must contain a JSON object.")
    return {
        name.lower(): profile
        for name, profile in contacts.items()
        if isinstance(name, str) and isinstance(profile, dict)
    }


class Interpreter:
    """Turn raw user input into structured intent.

    The interpreter only answers: "what does the user want?" It never performs
    the action itself.
    """

    def __init__(self, model: str = "llama3.2:latest") -> None:
        self.model = model
        self.personality = load_personality()
        self.contacts = load_contacts()

    def interpret(self, raw_input: str) -> dict[str, Any]:
        """Return a structured interpretation for the user's request."""
        cleaned_text = self._clean_message(raw_input)
        local_decision = self._local_interpret(cleaned_text)
        if local_decision is not None:
            return local_decision

        if llm.available:
            llm_decision = self._llm_interpret(cleaned_text)
            if llm_decision is not None:
                return llm_decision

        if self._looks_like_question(cleaned_text):
            return {
                "action": "answer_question",
                "topic": cleaned_text.strip(),
                "confidence": 0.35,
            }

        return {
            "action": "none",
            "confidence": 0.0,
            "reason": "no supported action detected",
        }

    def _clean_message(self, raw_input: str) -> str:
        """Normalize obvious typing and phrasing issues in the user's text."""
        text = raw_input.strip()
        if not text:
            return text

        replacements = {
            "spotfy": "spotify",
            "spotfiy": "spotify",
            "spotifiy": "spotify",
            "spotify for me pls": "spotify for me please",
            "pls": "please",
            "plz": "please",
            "play some" : "play spotify",
            "remindd me" : "set reminder"
        }

        for typo, fixed in replacements.items():
            text = re.sub(rf"\b{re.escape(typo)}\b", fixed, text, flags=re.IGNORECASE)

        return text

    def _llm_interpret(self, prompt: str) -> dict[str, Any] | None:
        """Ask Ollama for a structured interpretation when available."""
        system_prompt = self._build_system_prompt()
        # temperature=0 keeps intent classification deterministic; a small
        # num_predict is plenty for the compact JSON we ask for and keeps the
        # call snappy.
        content = llm.chat(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            model=self.model,
            fmt="json",
            temperature=0.0,
            num_predict=200,
        )
        if not content:
            return None
        try:
            decision = json.loads(content)
        except (json.JSONDecodeError, TypeError) as error:
            return {
                "action": "none",
                "confidence": 0.0,
                "reason": f"llm parse failed: {error}",
            }

        if not isinstance(decision, dict):
            return None

        candidate = self._validate_decision(decision)
        return candidate

    def _build_system_prompt(self) -> str:
        """Describe the interpreter contract to the model."""
        personality_json = json.dumps(self.personality, indent=2)
        contacts_json = json.dumps(self.contacts, indent=2)
        return f"""
You are ALANA's language understanding component.
Your only job is to decide what the user means.
Do not open apps, send messages, play music, or use the computer.
Return only valid JSON with exactly this structure:
{{
  "action": "one of {sorted(CONFIGURED_ACTIONS)}",
  "target": "optional target for open_app or app-like intents",
  "song": "optional song title for play_song",
  "recipient": "optional recipient for send_message",
  "platform": "optional messaging platform: 'whatsapp', 'instagram', or 'auto' (default when unspecified)",
  "intent": "optional for send_message: a SHORT description of what the user wants to say. NOT a finished message. Do NOT write the message yourself; ALANA composes it separately.",
  "topic": "optional topic for answer_question",
  "text": "optional reminder request",
  "confidence": 0.0
}}

ALANA personality profile:
{personality_json}

Known contacts:
{contacts_json}

Examples:
- "can you open spotfy for me pls" -> {{"action": "open_app", "target": "spotify", "confidence": 0.97}}
- "play bad guy by billie eilish" -> {{"action": "play_song", "song": "Bad Guy by Billie Eilish", "confidence": 0.93}}
- "send chinmay a quick message" -> {{"action": "send_message", "recipient": "chinmay", "platform": "auto", "confidence": 0.88}}
- "tell chinmay im gonna be late" -> {{"action": "send_message", "recipient": "chinmay", "platform": "auto", "intent": "i'm going to be late", "confidence": 0.92}}
- "whatsapp rohin that i'm running late" -> {{"action": "send_message", "recipient": "rohin", "platform": "whatsapp", "intent": "i'm running late", "confidence": 0.9}}
- "let sesha know i landed safe" -> {{"action": "send_message", "recipient": "sesha", "platform": "auto", "intent": "i landed safely", "confidence": 0.9}}
- "shoot zaria a text that the plan is off tonight" -> {{"action": "send_message", "recipient": "zaria", "platform": "auto", "intent": "the plan is off tonight", "confidence": 0.9}}
- "dm zaria on instagram" -> {{"action": "send_message", "recipient": "zaria", "platform": "instagram", "confidence": 0.9}}
- "what is WPW syndrome" -> {{"action": "answer_question", "topic": "WPW syndrome", "confidence": 0.89}}
- "remind me tomorrow to call mum" -> {"action":"set_reminder","text":"remind me tomorrow to call mum","confidence":0.95}

Return only JSON and nothing else.
"""

    def _validate_decision(self, decision: dict[str, Any]) -> dict[str, Any]:
        """Ensure the model output is a safe, structured interpretation."""
        action = str(decision.get("action", "none")).strip().lower()
        if action not in CONFIGURED_ACTIONS:
            return {
                "action": "none",
                "confidence": 0.0,
                "reason": "unsupported action",
            }

        normalized = {
            "action": action,
            "confidence": float(decision.get("confidence", 0.0) or 0.0),
        }

        if "target" in decision and isinstance(decision.get("target"), str):
            normalized["target"] = decision["target"].strip().lower()
        if "song" in decision and isinstance(decision.get("song"), str):
            normalized["song"] = decision["song"].strip()
        if "recipient" in decision and isinstance(decision.get("recipient"), str):
            normalized["recipient"] = decision["recipient"].strip().lower()
        if "platform" in decision and isinstance(decision.get("platform"), str):
            platform = decision["platform"].strip().lower()
            normalized["platform"] = platform if platform in {"whatsapp", "instagram", "auto"} else "auto"
        raw_intent = decision.get("intent") or decision.get("message")
        if isinstance(raw_intent, str) and raw_intent.strip():
            normalized["intent"] = raw_intent.strip()
        if "topic" in decision and isinstance(decision.get("topic"), str):
            normalized["topic"] = decision["topic"].strip()
        if "text" in decision and isinstance(decision.get("text"), str):
            normalized["text"] = decision["text"].strip()

        if action in {"open_app", "play_song", "send_message", "answer_question"}:
            if action == "open_app" and not normalized.get("target"):
                return {"action": "none", "confidence": 0.0, "reason": "missing target"}
            if action == "play_song" and not normalized.get("song"):
                return {"action": "none", "confidence": 0.0, "reason": "missing song"}
            if action == "send_message" and not normalized.get("recipient"):
                return {"action": "none", "confidence": 0.0, "reason": "missing recipient"}
            if action == "answer_question" and not normalized.get("topic"):
                return {"action": "none", "confidence": 0.0, "reason": "missing topic"}
            if action == "set_reminder":
                if not normalized.get("text"):
                 return {"action": "none", "confidence": 0.0, "reason": "missing reminder text"}

        return normalized

    def _local_interpret(self, prompt: str) -> dict[str, Any] | None:
        """Handle the most common requests without going through the model."""
        command = prompt.lower()

        if re.search(r"\b(please|pls|plz)\b", command):
            command = re.sub(r"\b(please|pls|plz)\b", "please", command)

        if any(word in command for word in ("spotify", "music", "tunes", "jams")):
            if re.search(r"\b(open|launch|start|run)\b", command):
                return {
                    "action": "open_app",
                    "target": "spotify",
                    "confidence": 0.97,
                }

        for app_name, normalized_name in KNOWN_APPS.items():
            if app_name in command:
                if re.search(r"\b(open|launch|start|run)\b", command):
                    return {
                        "action": "open_app",
                        "target": normalized_name,
                        "confidence": 0.95,
                    }

        if re.search(r"\b(pause|stop)\b", command):
            return {"action": "pause_song", "confidence": 0.97}
        if re.search(r"\b(resume|continue|unpause)\b", command):
            return {"action": "resume_song", "confidence": 0.97}
        if re.search(r"\b(previous|prev|go back|last)\b", command):
            return {"action": "previous_song", "confidence": 0.96}
        if re.search(r"\b(skip|next)\b", command):
            return {"action": "next_song", "confidence": 0.96}

        song_match = re.search(r"\bplay\s+(.+)", prompt, flags=re.IGNORECASE)
        if song_match:
            song = song_match.group(1).strip().removesuffix(" song").strip()
            if song.lower() not in {"music", "some music", "spotify", "something"}:
                return {
                    "action": "play_song",
                    "song": song,
                    "confidence": 0.92,
                }
        if re.search(r"\b(remind|reminder)\b", command):
            return {
                "action": "set_reminder",
                "text": prompt.strip(),
                "confidence": 0.98,
             }
        if re.search(
            r"\b(message|msg|dm|text|whatsapp|whats\s?app|wa|tell|ping|remind"
            r"|shoot|hit\s+up|let)\b",
            prompt,
            flags=re.IGNORECASE,
        ):
            recipient = self._extract_recipient(prompt)
            if recipient:
                decision = {
                    "action": "send_message",
                    "recipient": recipient,
                    "platform": self._detect_platform(prompt),
                    "confidence": 0.9,
                }
                intent = self._extract_intent(prompt, recipient)
                if intent:
                    decision["intent"] = intent
                return decision

        if self._looks_like_question(command):
            topic = self._extract_question_topic(prompt)
            return {
                "action": "answer_question",
                "topic": topic,
                "confidence": 0.75,
            }

        return None

    def _contact_in_prompt(self, prompt: str) -> str | None:
        """Return the configured contact named in a command, if any."""
        for name in self.contacts:
            if re.search(rf"\b{re.escape(name)}\b", prompt, flags=re.IGNORECASE):
                return name
        return None

    # Words that follow a messaging verb but are not real recipient names.
    _NON_RECIPIENTS = {
        "to", "on", "a", "an", "the", "someone", "somebody", "him", "her",
        "them", "me", "message", "msg", "dm", "text", "whatsapp", "wa",
        "know", "that", "and",
    }

    # Filler that sits between the recipient's name and the actual intent.
    _INTENT_FILLER = {
        "that", "to", "know", "saying", "say", "a", "an", "the", "and",
        "message", "msg", "text", "note",
    }

    def _extract_recipient(self, prompt: str) -> str | None:
        """Pull the recipient name from a messaging request.

        Prefers a name already known in contacts.json, then falls back to the
        word following a messaging verb so contacts that only live on a
        platform (Instagram/WhatsApp) are still routed downstream.
        """
        known = self._contact_in_prompt(prompt)
        if known:
            return known

        patterns = (
            r"\b(?:message|msg|dm|text|whatsapp|whats\s?app|wa|tell|ping"
            r"|remind|shoot|hit\s+up)\s+(?:to\s+)?([a-zA-Z]+)",
            r"\blet\s+([a-zA-Z]+)\s+know\b",
            r"\bsend\s+([a-zA-Z]+)\b",
        )
        for pattern in patterns:
            match = re.search(pattern, prompt, flags=re.IGNORECASE)
            if match:
                candidate = match.group(1).lower().strip()
                if candidate and candidate not in self._NON_RECIPIENTS:
                    return candidate
        return None

    def _extract_intent(self, prompt: str, recipient: str) -> str | None:
        """Infer the gist the user wants conveyed — not a finished message.

        The composer turns this gist into the actual message, so we only need a
        faithful description of intent, stripped of the command framing.
        """
        quoted = re.search(r'["“](.+?)["”]', prompt)
        if quoted:
            return quoted.group(1).strip().rstrip("?.!") or None

        # Everything after the recipient's name is usually the intent.
        match = re.search(rf"\b{re.escape(recipient)}\b", prompt, flags=re.IGNORECASE)
        if match:
            tail = prompt[match.end():].strip().lstrip(",:- ")
            # Drop a leading platform qualifier like "on instagram" so it does
            # not leak into the message (but leave a real "on my way" alone).
            tail = re.sub(
                r"^on\s+(?:instagram|insta|ig|whatsapp|whats\s?app|wa)\b",
                "",
                tail,
                flags=re.IGNORECASE,
            ).strip()
            words = tail.split()
            while words and words[0].lower().strip(",:-") in self._INTENT_FILLER:
                words.pop(0)
            tail = " ".join(words).strip().rstrip("?.!")
            if tail:
                return tail

        # Fall back to marker-based extraction for odd phrasings.
        lower_prompt = prompt.lower()
        for marker in (" that ", " saying ", " say ", " tell ", " to "):
            if marker in lower_prompt:
                body = prompt.split(marker, 1)[1].strip()
                if body:
                    return body.rstrip("?.!")

        return None

    @staticmethod
    def _detect_platform(prompt: str) -> str:
        """Decide which messaging platform the user explicitly named, if any."""
        if re.search(r"\b(whatsapp|whats\s?app|wa)\b", prompt, flags=re.IGNORECASE):
            return "whatsapp"
        if re.search(r"\b(instagram|insta|ig)\b", prompt, flags=re.IGNORECASE):
            return "instagram"
        return "auto"

    @staticmethod
    def _looks_like_question(text: str) -> bool:
        """Return True when the request looks like an information question."""
        return bool(re.search(r"\b(what|who|where|when|why|how)\b", text, flags=re.IGNORECASE))

    @staticmethod
    def _extract_question_topic(prompt: str) -> str:
        """Extract the topic phrase from a question fragment."""
        cleaned = prompt.strip().rstrip("?")
        if cleaned.lower().startswith(("what is ", "who is ", "where is ", "when is ", "why is ", "how is ")):
            return cleaned.split(" ", 1)[1].strip()
        return cleaned


if __name__ == "__main__":
    interpreter = Interpreter()
    sample = "can you open spotfy for me pls"
    print(json.dumps(interpreter.interpret(sample), indent=2))
