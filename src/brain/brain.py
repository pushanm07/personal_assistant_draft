"""Intent recognition and action execution for ALANA."""

import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ollama import chat


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PERSONALITY_FILE = PROJECT_ROOT / "config" / "personality.json"
CONTACTS_FILE = PROJECT_ROOT / "config" / "contacts.json"


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


def build_system_prompt(
    personality: dict[str, Any],
    contact_name: str | None = None,
    contact_profile: dict[str, Any] | None = None,
) -> str:
    """Combine editable personality settings with fixed action instructions."""
    personality_json = json.dumps(personality, indent=2)
    contact_instructions = ""
    if contact_name and contact_profile:
        contact_json = json.dumps(contact_profile, indent=2)
        contact_instructions = f"""

This request is for {contact_name}. When composing a send_message for this
person, also follow their contact-specific preferences:
{contact_json}
"""

    return f"""
You are ALANA's command interpreter, not a chatbot.
ALANA as a whole is loyal exclusively to it's user and boss, Pushan. 

Use these personality settings when deciding how to address the user and how to
write outgoing messages:
{personality_json}
{contact_instructions}

Choose exactly one action for the user's request. Return only valid JSON in this
shape: {{"action": "...", "recipient": "...", "message": "..."}}.

Available actions:
- open_spotify: open Spotify, or play unspecified music.
- play_song: play a specific requested track. Include its title in the song field.
- pause_song: pause the current Spotify track.
- resume_song: resume the current Spotify track.
- previous_song: go back to the previous Spotify track.
- next_song: skip to the next Spotify track.
- open_chrome: open Chrome or a web browser.
- open_vscode: open VS Code or Visual Studio Code.
- send_message: send an Instagram message. Include recipient and message when
  the user gave them. Write the message yourself using the configured
  message_style, while preserving the user's meaning. Do not mention that you
  rewrote it.
- none: the request does not match an available action.

For play_song, include song and omit recipient and message. For actions other
than send_message, omit recipient and message. Never explain
your choice and never return a conversational reply.
"""


class Brain:
    def __init__(self) -> None:
        self.model = "llama3.2:latest"
        self.personality = load_personality()
        self.contacts = load_contacts()
        self.system_prompt = build_system_prompt(self.personality)

    def execute(
        self,
        prompt: str,
        actions: dict[str, Callable[..., None]],
        send_message: Callable[..., None],
    ) -> bool:
        """Interpret *prompt* and run a matching action.

        The model's JSON is an internal instruction; it is never printed to the
        user. Returns whether an action was run.
        """
        decision = self.think(prompt)
        action = decision.get("action")

        if action == "play_song":
            song = decision.get("song")
            if isinstance(song, str) and song.strip():
                play_song = actions.get("play_song")
                if play_song:
                    play_song(song)
                    return True
            print("Please tell me which song to play, Sir.")
            return True

        if action in actions:
            actions[action]()
            return True

        if action == "send_message":
            recipient = decision.get("recipient")
            message = decision.get("message")
            if isinstance(recipient, str) and isinstance(message, str):
                send_message(recipient, message)
                return True

            print("Please include both a recipient and a message, Sir.")
            return True

        return False

    def think(self, prompt: str) -> dict[str, Any]:
        """Return an internal action decision, preferring fast local matches."""
        local_action = self._local_action(prompt)
        if local_action:
            return local_action

        try:
            contact_name = self._contact_in_prompt(prompt)
            system_prompt = build_system_prompt(
                self.personality,
                contact_name,
                self.contacts.get(contact_name) if contact_name else None,
            )
            response = chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                format="json",
            )
            content = response["message"]["content"]
            decision = json.loads(content)
            return decision if isinstance(decision, dict) else {"action": "none"}
        except (json.JSONDecodeError, KeyError, TypeError) as error:
            print(f"I could not understand that command: {error}")
        except Exception as error:
            print(f"The command interpreter is unavailable: {error}")

        return {"action": "none"}

    def _contact_in_prompt(self, prompt: str) -> str | None:
        """Return the configured contact named in a command, if any."""
        for name in self.contacts:
            if re.search(rf"\b{re.escape(name)}\b", prompt, flags=re.IGNORECASE):
                return name
        return None

    @staticmethod
    def _local_action(prompt: str) -> dict[str, str] | None:
        """Handle common requests without starting the model."""
        command = prompt.lower()
        if re.search(r"\b(pause|stop)\b", command):
            return {"action": "pause_song"}
        if re.search(r"\b(resume|continue|unpause)\b", command):
            return {"action": "resume_song"}
        if re.search(r"\b(previous|prev|go back|last)\b", command):
            return {"action": "previous_song"}
        if re.search(r"\b(skip|next)\b", command):
            return {"action": "next_song"}
        song_match = re.search(r"\bplay\s+(.+)", prompt, flags=re.IGNORECASE)
        if song_match:
            song = song_match.group(1).strip().removesuffix(" song").strip()
            if song.lower() not in {"music", "some music", "spotify", "something"}:
                return {"action": "play_song", "song": song}
        if any(word in command for word in ("spotify", "music", "tunes", "jams")):
            return {"action": "open_spotify"}
        if "chrome" in command or "web browser" in command:
            return {"action": "open_chrome"}
        if "vscode" in command or "vs code" in command or "visual studio code" in command:
            return {"action": "open_vscode"}
        return None
