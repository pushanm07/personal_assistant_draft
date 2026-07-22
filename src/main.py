import threading

from actions.apps import open_chrome, open_vscode
from actions import instagram, whatsapp
from actions.instagram import send_message_instagram
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
from brain.brain import Brain
from actions.whatsapp import send_message_whatsapp
from actions.reminder import set_reminder

from brain import llm

try:
    from voice import listen_push_to_talk
    from voice import warm_up as warm_up_voice
except ImportError:
    listen_push_to_talk = None
    warm_up_voice = None

brain = Brain()


def route_message(
    recipient: str,
    message: str | None = None,
    platform: str = "auto",
) -> None:
    """Send a message on the right platform.

    - platform == "whatsapp": go straight to WhatsApp.
    - platform == "instagram": go straight to Instagram.
    - platform == "auto" (default, e.g. "message"/"dm" with no app named):00
      try Instagram contacts first, then WhatsApp, else say we can't find them.
    """
    if platform == "whatsapp":
        send_message_whatsapp(recipient, message)
        return

    if platform == "instagram":
        send_message_instagram(recipient, message)
        return

    if instagram.has_contact(recipient):
        send_message_instagram(recipient, message)
    elif whatsapp.has_contact(recipient):
        send_message_whatsapp(recipient, message)
    else:
        print(
            f"I don't have a contact named {recipient} on Instagram or WhatsApp, Sir."
        )


BRAIN_ACTIONS = {
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


EXIT_WORDS = {"exit", "quit", "bye", "see ya", "go to sleep"}
VOICE_WORDS = {"voice", "v", "voice on", "voice mode", "listen"}
TEXT_WORDS = {"text", "t", "type", "keyboard", "voice off", "text mode"}


def _warm_up_models() -> None:
    """Preload the LLM and speech model in the background so first use is fast."""
    llm.warm_up_async()
    if warm_up_voice is not None:
        threading.Thread(target=warm_up_voice, daemon=True).start()


def _get_command(voice_mode: bool) -> str:
    """Read the next command.

    In voice mode this is push-to-talk: pressing Enter with no text starts a
    recording, while typing anything runs it as a text command straight away
    (so you can always drop back to the keyboard). In text mode it is a plain
    prompt.
    """
    if voice_mode and listen_push_to_talk is not None:
        raw = input("🎤  [Enter] to talk · or just type · (t = text mode): ").strip()
        if raw:
            return raw
        command = listen_push_to_talk().strip()
        if command:
            print(f"🗣️  {command}")
        return command

    return input("⌨️  What can I do for you, Sir? (v = voice mode): ").strip()


def main() -> None:
    print("================================")
    print("          ALANA")
    print("Initializing...")
    _warm_up_models()

    # Start in whichever mode is actually available.
    voice_mode = listen_push_to_talk is not None
    print("System Ready, Sir.")
    if not voice_mode:
        print("(Voice input unavailable — running in text mode, Sir.)")
    print("================================")

    while True:
        try:
            command = _get_command(voice_mode)
        except EOFError:
            print("Goodbye, Sir.")
            break
        except KeyboardInterrupt:
            if voice_mode:
                voice_mode = False
                print("\nText mode, Sir. Type 'v' to talk again.")
                continue
            print("\nGoodbye, Sir.")
            break

        if not command:
            continue

        lowered = command.lower()

        if lowered in EXIT_WORDS:
            print("Goodbye, Sir.")
            break

        if lowered == "hello":
            print("Hello, Sir.")
            continue

        if lowered in VOICE_WORDS:
            if listen_push_to_talk is None:
                print("Voice input isn't available, Sir.")
                continue
            voice_mode = True
            print("Voice mode, Sir. Tap Enter to talk.")
            continue

        if lowered in TEXT_WORDS:
            voice_mode = False
            print("Text mode, Sir.")
            continue

        # Recognised command? Run it. Otherwise fall back to a conversational
        # reply so nothing ever dead-ends on "I don't understand".
        if not brain.execute(command, BRAIN_ACTIONS, route_message):
            print(brain.chat(command))


if __name__ == "__main__":
    main()
