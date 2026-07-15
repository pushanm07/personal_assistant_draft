import webbrowser
import time
import pyautogui
import language_tool_python

user = {
    "wgft" : "24580003574957598/",
    "chinmay" : "17842003841624671/",
    "sesha" : "17843965926541930/",
    "zaria" : "17853061227073119/"

}

def send_message_instagram():
    tool = language_tool_python.LanguageTool('en-US')
    name=input("Enter the name of the user you want to send a message to: ").lower().strip()
    if name in user: 
        mes=input("Enter the message you want to send: ")
        gmes=tool.correct(mes)
        print(f"Sending: {gmes}")
        url = f"https://www.instagram.com/direct/t/{user[name]}"
        webbrowser.open(url)
        time.sleep(7)  # Wait for the page to load
        pyautogui.write(gmes)
        pyautogui.press("enter")
        time.sleep(3)  # Wait for the message to be sent
        pyautogui.hotkey("ctrl", "w")  # Close the tab

 
