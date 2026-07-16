
from actions.spotify import (
    authenticate_spotify,
    next_song,
    open_spotify,
    pause_song,
    play_song,
    previous_song,
    resume_song,
)
from actions.apps import open_chrome, open_vscode
from actions.instagram import send_message_instagram
from brain.brain import Brain
from voice.record import record_voice
from voice.transcribe import transcribe_audio

brain = Brain()


BRAIN_ACTIONS = {
    "open_spotify": open_spotify,
    "play_song": play_song,
    "pause_song": pause_song,
    "resume_song": resume_song,
    "previous_song": previous_song,
    "next_song": next_song,
    "open_chrome": open_chrome,
    "open_vscode": open_vscode,
}

# Action Registry
actions = {
    "spotify": open_spotify,
    "music": open_spotify,
    "open spotify": open_spotify,
    "tunes": open_spotify,
    "jams": open_spotify,
    "authenticate spotify": authenticate_spotify,
    "connect spotify": authenticate_spotify,
    "chrome": open_chrome,
    "open chrome": open_chrome,
    "vscode": open_vscode,
    "vs code": open_vscode,
    "open vscode": open_vscode,
    "open vs code": open_vscode,
    "instagram": send_message_instagram,
    "message": send_message_instagram,
    "dm": send_message_instagram,
    "pause" : pause_song,
}


def main():
    print("================================")
    print("          ALANA")
    print("Initializing...")
    print("System Ready, Sir.")
    print("================================")

    while True:

        record_voice()
        print("Recording complete.")
        command = transcribe_audio().lower().strip()
       

        # Exit commands
        if command in ["exit", "quit", "bye", "see ya", "go to sleep"]:
            print("Goodbye, Sir.") 
            break

        # Normal conversation
        elif command == "hello":
            print("Hello, Sir.")
        
        elif command in ["instagram", "message", "dm","ask"]:
            send_message_instagram()

        # Registered actions
        elif command in actions:
            actions[command]()

        # Unknown command
        else:
            if not brain.execute(command, BRAIN_ACTIONS, send_message_instagram):
                print("I don't recognize an action for that yet, Sir.")


if __name__ == "__main__":
    main()
