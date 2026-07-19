import webbrowser
import time
import pyautogui

users = {
    "rohin": "riop bbc r",
    "father": "aveek",
    "aman": "aman",
    "john": "john",
    "driver": "john",
}


def has_contact(name: str | None) -> bool:
    """Return True when *name* is a known WhatsApp contact."""
    if not name:
        return False
    return name.lower().strip() in users


def send_message_whatsapp(name: str | None = None, mes: str | None = None) -> None:
    """Send a WhatsApp message, prompting only when details are missing."""
    if name is None:
        name = input("Enter the name of the user you want to send a message to: ")
    name = name.lower().strip()

    if name not in users:
        print(f"I don't have a WhatsApp contact named {name}, Sir.")
        return

    if mes is None:
        mes = input("Enter the message you want to send: ")

    print(f"Sending: {mes}")
    webbrowser.open("https://web.whatsapp.com/")
    time.sleep(13)  # Wait for the page to load
    pyautogui.moveTo(200, 206)
    time.sleep(0.7)
    pyautogui.click()
    time.sleep(0.7)
    pyautogui.write(users[name])  # type the contact name into search
    time.sleep(1.5)
    pyautogui.press("enter")  # open the top matching chat
    time.sleep(1)
    pyautogui.write(mes)
    pyautogui.press("enter")
    time.sleep(3)  # Wait for the message to be sent
    pyautogui.hotkey("ctrl", "w")  
    pyautogui.press("enter")       # Close the tab
