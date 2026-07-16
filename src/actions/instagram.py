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
        time.sleep(6)  # Wait for the page to load
        pyautogui.write(mes)
        pyautogui.press("enter")
        time.sleep(3)  # Wait for the message to be sent
        pyautogui.hotkey("ctrl", "w")  # Close the tab
    else:
        print(f"I don't have an Instagram contact named {name}, Sir.")

 
