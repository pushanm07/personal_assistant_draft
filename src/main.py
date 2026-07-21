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

brain = Brain()


def route_message(
    recipient: str,
    message: str | None = None,
    platform: str = "auto",
) -> None:
    """Send a message on the right platform.

    - platform == "whatsapp": go straight to WhatsApp.
    - platform == "instagram": go straight to Instagram.
    - platform == "auto" (default, e.g. "message"/"dm" with no app named):
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


def main() -> None:
    print("================================")
    print("          ALANA")
    print("Initializing...")
    print("System Ready, Sir.")
    print("================================")

    while True:
        try:
            command = input("what can I do for you, Sir?").strip()
        except EOFError:
            print("Goodbye, Sir.")
            break

        if not command:
            continue

        if command.lower() in {"exit", "quit", "bye", "see ya", "go to sleep"}:
            print("Goodbye, Sir.")
            break

        if command.lower() == "hello":
            print("Hello, Sir.")
            continue

        if not brain.execute(command, BRAIN_ACTIONS, route_message):
            print("I don't recognize an action for that yet, Sir.")


if __name__ == "__main__":
    main()
