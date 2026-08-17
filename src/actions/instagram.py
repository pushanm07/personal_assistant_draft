import webbrowser
import time
import pyautogui

user = {
    "wgft" : "24580003574957598/",
    "chinmay" : "17842003841624671/",
    "sesha" : "17843965926541930/",
    "zaria" : "17853061227073119/",
    "prisha" : "17843196989914990/"

}

# Browser automation wait tuning. The page-load wait dominates the latency of
# a send; if your connection is fast you can lower it here without touching
# code. The trailing wait is already trimmed to confirm the send, not linger.
PAGE_LOAD_SECONDS = 9.0  # let the dm thread render
SEND_CONFIRM_SECONDS = 1.5  # let the message post before closing the tab

def has_contact(name: str | None) -> bool:
    """Return True when *name* is a known Instagram contact."""
    if not name:
        return False
    return name.lower().strip() in user


def send_message_instagram(name: str | None = None, mes: str | None = None) -> None:
    """Send an Instagram message, prompting only when details are missing."""
    if name is None:
        name = input("Enter the name of the user you want to send a message to: ")
    name = name.lower().strip()

    if name in user: 
        if mes is None:
            mes = input("Enter the message you want to send: ")
        print(f"Sending: {mes}")
        url = f"https://www.instagram.com/direct/t/{user[name]}"
        webbrowser.open(url)
        time.sleep(PAGE_LOAD_SECONDS)  # Wait for the page to load
        pyautogui.write(mes)
        pyautogui.press("enter")
        time.sleep(SEND_CONFIRM_SECONDS)  # Wait for the message to be sent
        pyautogui.hotkey("ctrl", "w")  # Close the tab
    else:
        print(f"I don't have an Instagram contact named {name}, Sir.")

 
