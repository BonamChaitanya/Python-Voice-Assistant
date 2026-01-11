import speech_recognition as sr
import pyautogui
import time
import logging
import os
import datetime
import subprocess
import win32gui
import win32con
import sys

# Configure PyAutoGUI
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.5

# Set up logging
log_dir = os.path.join(os.path.expanduser('~'), 'voice_controller_logs')
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, f'voice_controller_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Function to capture and recognize voice
def recognize_voice():
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        print("Listening for your command...")
        logging.info("Listening for command")
        
        recognizer.adjust_for_ambient_noise(source, duration=0.5)
        audio = recognizer.listen(source)
        
        try:
            command = recognizer.recognize_google(audio)
            print(f"You said: {command}")
            logging.info(f"Command recognized: {command}")
            return command.lower()
        except sr.UnknownValueError:
            print("Sorry, I didn't catch that.")
            logging.warning("Command not recognized")
            return ""
        except sr.RequestError:
            print("Speech service unavailable. Check your internet connection.")
            logging.error("Speech service unavailable")
            return ""

# Find WhatsApp window and bring it to front
def find_whatsapp_window():
    def callback(hwnd, result):
        if win32gui.IsWindowVisible(hwnd) and "WhatsApp" in win32gui.GetWindowText(hwnd):
            result.append(hwnd)
        return True
    
    handles = []
    win32gui.EnumWindows(callback, handles)
    
    if handles:
        # Get the first WhatsApp window
        hwnd = handles[0]
        # Restore if minimized
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        # Bring to front
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(1)
        print("Found and focused existing WhatsApp window")
        logging.info("Found and focused existing WhatsApp window")
        return True
    
    print("No WhatsApp window found")
    logging.info("No WhatsApp window found")
    return False

# Open WhatsApp application
def open_whatsapp():
    print("Opening WhatsApp...")
    logging.info("Opening WhatsApp")
    
    # First try to find and focus existing window
    if find_whatsapp_window():
        return True
    
    # Try to open WhatsApp via Start menu
    try:
        pyautogui.press('win')
        time.sleep(1)
        pyautogui.typewrite('WhatsApp')
        time.sleep(1)
        pyautogui.press('enter')
        time.sleep(5)  # Wait for WhatsApp to open
        
        # Check if WhatsApp is now open
        if find_whatsapp_window():
            print("WhatsApp opened successfully")
            logging.info("WhatsApp opened successfully")
            return True
    except Exception as e:
        print(f"Error opening WhatsApp via Start menu: {e}")
        logging.error(f"Error opening WhatsApp via Start menu: {e}")
    
    # Try direct path if Start menu fails
    try:
        # Common installation paths
        whatsapp_paths = [
            os.path.expandvars(r"%LOCALAPPDATA%\WhatsApp\WhatsApp.exe"),
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\WhatsApp\WhatsApp.exe")
        ]
        
        for path in whatsapp_paths:
            if os.path.exists(path):
                subprocess.Popen(path)
                print(f"Launched WhatsApp from {path}")
                logging.info(f"Launched WhatsApp from {path}")
                time.sleep(5)
                
                if find_whatsapp_window():
                    print("WhatsApp opened successfully via direct path")
                    logging.info("WhatsApp opened successfully via direct path")
                    return True
    except Exception as e:
        print(f"Error opening WhatsApp via direct path: {e}")
        logging.error(f"Error opening WhatsApp via direct path: {e}")
    
    print("Failed to open WhatsApp. Please install it or check installation path.")
    logging.error("Failed to open WhatsApp")
    return False

# Find and click on a contact's chat in WhatsApp
def find_and_click_contact(contact_name):
    print(f"Looking for contact: {contact_name}")
    logging.info(f"Looking for contact: {contact_name}")
    
    # Go to search box (Ctrl+F in WhatsApp)
    pyautogui.hotkey('ctrl', 'f')
    time.sleep(1)
    
    # Clear search field and type contact name
    pyautogui.hotkey('ctrl', 'a')  # Select all text
    pyautogui.press('delete')      # Delete selected text
    time.sleep(0.5)
    pyautogui.typewrite(contact_name)
    time.sleep(2)  # Wait for search results
    
    # Press Escape to close the search overlay but keep results visible
    pyautogui.press('escape')
    time.sleep(0.5)
    
    # Now click on the first search result
    # Generally, the contact appears in a list on the left side of WhatsApp
    screen_width, screen_height = pyautogui.size()
    
    # Click in the left panel where contacts appear (about 1/4 of the way across, 1/4 of the way down)
    contact_x = int(screen_width * 0.15)  # 15% from left
    contact_y = int(screen_height * 0.25)  # 25% from top
    
    print(f"Clicking on potential contact position: ({contact_x}, {contact_y})")
    logging.info(f"Clicking on potential contact position: ({contact_x}, {contact_y})")
    
    pyautogui.click(contact_x, contact_y)
    time.sleep(1)
    
    # After clicking, chat should be open on the right
    return True

# Send a message using direct keyboard shortcuts
def send_whatsapp_message(contact_name, message):
    try:
        print(f"Sending message to {contact_name}...")
        logging.info(f"Sending message to {contact_name}")
        
        # Make sure WhatsApp is open
        if not open_whatsapp():
            print("Could not open WhatsApp. Cannot send message.")
            logging.error("Could not open WhatsApp. Cannot send message.")
            return False
        
        # Find and click on the contact's chat
        if not find_and_click_contact(contact_name):
            print(f"Could not find chat with {contact_name}")
            logging.error(f"Could not find chat with {contact_name}")
            return False
        
        # Ensure we're in the chat window (click in the message input area)
        screen_width, screen_height = pyautogui.size()
        # Message input is typically at the bottom of the screen, centered horizontally
        input_x = int(screen_width * 0.5)
        input_y = int(screen_height * 0.9)  # Near bottom of screen
        
        print(f"Clicking on message input area: ({input_x}, {input_y})")
        logging.info(f"Clicking on message input area: ({input_x}, {input_y})")
        
        pyautogui.click(input_x, input_y)
        time.sleep(0.5)
        
        # Make sure input area is clear
        pyautogui.hotkey('ctrl', 'a')
        pyautogui.press('delete')
        time.sleep(0.3)
        
        # Type and send message
        pyautogui.typewrite(message)
        time.sleep(0.5)
        pyautogui.press('enter')
        
        print("Message sent!")
        logging.info("Message sent successfully")
        return True
        
    except Exception as e:
        print(f"Error sending message: {e}")
        logging.error(f"Error sending message: {e}")
        return False

# Main Function
def main():
    print("Voice Controller activated! Say 'exit' to quit.")
    logging.info("Voice Controller started")
    
    while True:
        command = recognize_voice()
        
        if not command:
            continue
            
        # WhatsApp commands
        if "open whatsapp" in command:
            open_whatsapp()
            
        elif "send message" in command or "send a message" in command:
            print("Who should I send a message to?")
            logging.info("Asking for contact name")
            contact_name = recognize_voice()
            
            if contact_name:
                print("What is the message?")
                logging.info("Asking for message content")
                message = recognize_voice()
                
                if message:
                    send_whatsapp_message(contact_name, message)
        
        # Mouse control commands
        elif "click" in command:
            pyautogui.click()
            logging.info("Mouse clicked")
            
        # Exit command
        elif "exit" in command or "quit" in command or "stop" in command:
            print("Goodbye!")
            logging.info("Voice Controller stopped by user command")
            break
            
        # Help command
        elif "help" in command:
            help_text = """
            Available commands:
            - open whatsapp
            - send message (it will ask for contact and message)
            - click
            - exit / quit / stop
            """
            print(help_text)
            logging.info("Help displayed")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logging.critical(f"Critical error in main program: {e}")
        print(f"A critical error occurred: {e}")