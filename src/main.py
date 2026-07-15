from actions.spotify import open_spotify
from actions.apps import open_chrome, open_vscode
from actions.instagram import send_message_instagram

# Action Registry
actions = {
    "spotify": open_spotify,
    "music": open_spotify,
    "open spotify": open_spotify,
    "tunes": open_spotify,
    "jams": open_spotify,
    "chrome": open_chrome,
    "open chrome": open_chrome,
    "vscode": open_vscode,
    "vs code": open_vscode,
    "open vscode": open_vscode,
    "open vs code": open_vscode,
    "instagram": send_message_instagram,
    "message": send_message_instagram,
    "dm": send_message_instagram
}


def main():
    print("================================")
    print("          ALANA")
    print("Initializing...")
    print("System Ready, Sir.")
    print("================================")

    while True:
        command = input("What can I do for you? ").lower().strip()

        # Exit commands
        if command in ["exit", "quit", "bye", "see ya", "go to sleep"]:
            print("Goodbye, Sir.") 
            break

        # Normal conversation
        elif command == "hello":
            print("Hello, Sir.")
        
        elif command in ["instagram", "message", "dm"]:
            send_message_instagram()

        # Registered actions
        elif command in actions:
            actions[command]()

        # Unknown command
        else:
            print("I'm afraid I don't know how to do that yet, Sir.")


if __name__ == "__main__":
    main()
