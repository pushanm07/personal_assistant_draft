from actions.spotify import open_spotify

# Action Registry
actions = {
    "spotify": open_spotify,
    "music": open_spotify,
    "open spotify": open_spotify,
    "tunes": open_spotify,
    "jams": open_spotify,
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

        # Registered actions
        elif command in actions:
            actions[command]()

        # Unknown command
        else:
            print("I'm afraid I don't know how to do that yet, Sir.")


if __name__ == "__main__":
    main()