import speech_recognition as sr
import pyautogui
import time
import logging
import os
import datetime
import subprocess
import win32gui
import win32con
import webbrowser
import urllib.parse
import pyperclip
import re
from ctypes import cast, POINTER
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
import screen_brightness_control as sbc

# Configure PyAutoGUI
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.5

# Set up logging
log_dir = os.path.join(os.path.expanduser('~'), 'voice_controller_logs')
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, f'unified_voice_assistant_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Global variables
youtube_opened = False
volume_interface = None

# ------------ VOICE RECOGNITION FUNCTIONS ------------

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

# ------------ WHATSAPP FUNCTIONS ------------

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
    
    # Use clipboard for reliable input
    original_clipboard = pyperclip.paste()  # Save original clipboard
    pyperclip.copy(contact_name)
    pyautogui.hotkey('ctrl', 'v')
    time.sleep(2)  # Wait for search results
    
    # Press Escape to close the search overlay but keep results visible
    pyautogui.press('escape')
    time.sleep(0.5)
    
    # Now click on the first search result
    # Generally, the contact appears in a list on the left side of WhatsApp
    screen_width, screen_height = pyautogui.size()
    
    # Click in the left panel where contacts appear
    contact_x = int(screen_width * 0.15)  # 15% from left
    contact_y = int(screen_height * 0.25)  # 25% from top
    
    print(f"Clicking on potential contact position: ({contact_x}, {contact_y})")
    logging.info(f"Clicking on potential contact position: ({contact_x}, {contact_y})")
    
    pyautogui.click(contact_x, contact_y)
    time.sleep(1)
    
    # Restore original clipboard
    pyperclip.copy(original_clipboard)
    
    # After clicking, chat should be open on the right
    return True

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
        
        # Use clipboard for reliable message input
        original_clipboard = pyperclip.paste()  # Save original clipboard
        pyperclip.copy(message)
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(0.5)
        pyperclip.copy(original_clipboard)  # Restore original clipboard
        
        # Send the message
        pyautogui.press('enter')
        
        print("Message sent!")
        logging.info("Message sent successfully")
        return True
        
    except Exception as e:
        print(f"Error sending message: {e}")
        logging.error(f"Error sending message: {e}")
        return False

# ------------ VOLUME AND BRIGHTNESS FUNCTIONS ------------

def initialize_volume_control():
    try:
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(
            IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        return volume
    except Exception as e:
        print(f"Error initializing volume control: {e}")
        logging.error(f"Error initializing volume control: {e}")
        return None

def get_current_volume(volume_interface):
    try:
        if volume_interface:
            current_volume_scalar = volume_interface.GetMasterVolumeLevelScalar()
            current_volume = int(current_volume_scalar * 100)
            return current_volume
        return 0
    except Exception as e:
        print(f"Error getting current volume: {e}")
        logging.error(f"Error getting current volume: {e}")
        return 0

def set_volume(volume_interface, volume_percent):
    try:
        if volume_interface:
            volume_percent = max(0, min(100, volume_percent))
            volume_scalar = volume_percent / 100
            volume_interface.SetMasterVolumeLevelScalar(volume_scalar, None)
            print(f"Volume set to {volume_percent}%")
            logging.info(f"Volume set to {volume_percent}%")
            return True
        return False
    except Exception as e:
        print(f"Error setting volume: {e}")
        logging.error(f"Error setting volume: {e}")
        return False

def increase_volume(volume_interface, increment=10):
    try:
        current_volume = get_current_volume(volume_interface)
        new_volume = min(100, current_volume + increment)
        return set_volume(volume_interface, new_volume)
    except Exception as e:
        print(f"Error increasing volume: {e}")
        logging.error(f"Error increasing volume: {e}")
        return False

def decrease_volume(volume_interface, decrement=10):
    try:
        current_volume = get_current_volume(volume_interface)
        new_volume = max(0, current_volume - decrement)
        return set_volume(volume_interface, new_volume)
    except Exception as e:
        print(f"Error decreasing volume: {e}")
        logging.error(f"Error decreasing volume: {e}")
        return False

def toggle_mute(volume_interface):
    try:
        if volume_interface:
            is_muted = volume_interface.GetMute()
            volume_interface.SetMute(not is_muted, None)
            print(f"Volume {'muted' if not is_muted else 'unmuted'}")
            logging.info(f"Volume {'muted' if not is_muted else 'unmuted'}")
            return True
        return False
    except Exception as e:
        print(f"Error toggling mute: {e}")
        logging.error(f"Error toggling mute: {e}")
        return False

def get_current_brightness():
    try:
        brightness = sbc.get_brightness()
        if isinstance(brightness, list):
            return brightness[0]
        return brightness
    except Exception as e:
        print(f"Error getting brightness: {e}")
        logging.error(f"Error getting brightness: {e}")
        return 0

def set_brightness(brightness_percent):
    try:
        brightness_percent = max(0, min(100, brightness_percent))
        sbc.set_brightness(brightness_percent)
        print(f"Brightness set to {brightness_percent}%")
        logging.info(f"Brightness set to {brightness_percent}%")
        return True
    except Exception as e:
        print(f"Error setting brightness: {e}")
        logging.error(f"Error setting brightness: {e}")
        return False

def increase_brightness(increment=10):
    try:
        current_brightness = get_current_brightness()
        new_brightness = min(100, current_brightness + increment)
        return set_brightness(new_brightness)
    except Exception as e:
        print(f"Error increasing brightness: {e}")
        logging.error(f"Error increasing brightness: {e}")
        return False

def decrease_brightness(decrement=10):
    try:
        current_brightness = get_current_brightness()
        new_brightness = max(0, current_brightness - decrement)
        return set_brightness(new_brightness)
    except Exception as e:
        print(f"Error decreasing brightness: {e}")
        logging.error(f"Error decreasing brightness: {e}")
        return False

def parse_numeric_value(command):
    patterns = [
        r'(\d+)\s*%',               # "50%" or "50 %"
        r'(\d+)\s*percent',         # "50 percent"
        r'to\s*(\d+)',              # "to 50"
        r'(\d+)'                    # Just a number
    ]
    
    for pattern in patterns:
        match = re.search(pattern, command)
        if match:
            value = int(match.group(1))
            return value
    
    return None

def process_specific_level_command(command, volume_interface):
    value = parse_numeric_value(command)
    
    if value is None:
        print("I couldn't understand the level you specified.")
        logging.warning("Failed to parse numeric value from command")
        return False
    
    if "volume" in command:
        return set_volume(volume_interface, value)
    elif "brightness" in command:
        return set_brightness(value)
    else:
        print("Please specify whether you want to adjust volume or brightness.")
        logging.warning("Specific level command without volume/brightness specification")
        return False

# ------------ YOUTUBE FUNCTIONS ------------

def find_youtube_window():
    def callback(hwnd, windows):
        if win32gui.IsWindowVisible(hwnd):
            window_title = win32gui.GetWindowText(hwnd).lower()
            if "youtube" in window_title and any(browser in window_title for browser in 
                                               ["chrome", "firefox", "edge", "opera", "brave"]):
                windows.append(hwnd)
        return True
    
    windows = []
    win32gui.EnumWindows(callback, windows)
    
    if windows:
        # Use the first YouTube window found
        hwnd = windows[0]
        
        # Restore if minimized
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        
        # Bring to front
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.5)
        print("Found and focused YouTube window")
        logging.info("Found and focused YouTube window")
        return True
    
    print("No YouTube window found")
    logging.info("No YouTube window found")
    return False

def open_youtube():
    global youtube_opened
    
    print("Opening YouTube...")
    logging.info("Opening YouTube")
    
    # First try to find and focus existing window
    if find_youtube_window():
        youtube_opened = True
        return True
    
    # Open YouTube in default browser
    webbrowser.open("https://www.youtube.com")
    time.sleep(3)  # Give it time to open
    
    # Mark as opened
    youtube_opened = True
    
    print("YouTube opened successfully")
    logging.info("YouTube opened successfully")
    return True

def search_youtube(query):
    global youtube_opened
    
    print(f"Searching YouTube for: {query}")
    logging.info(f"Searching YouTube for: {query}")
    
    # Make sure YouTube is open first
    if not youtube_opened:
        print("YouTube not opened yet. Opening YouTube first...")
        open_youtube()
    else:
        # Try to find and focus the YouTube window
        find_youtube_window()
    
    # APPROACH: Use keyboard shortcuts to search in the current tab
    try:
        # First, focus on the search box using keyboard shortcut (/ key in YouTube)
        pyautogui.press('/')
        time.sleep(0.5)
        
        # Clear any existing text
        pyautogui.hotkey('ctrl', 'a')  # Select all
        time.sleep(0.2)
        
        # Use clipboard to paste the search query (more reliable than typing)
        original_clipboard = pyperclip.paste()  # Save current clipboard
        pyperclip.copy(query)  # Copy search query to clipboard
        pyautogui.hotkey('ctrl', 'v')  # Paste
        time.sleep(0.2)
        
        # Press Enter to search
        pyautogui.press('enter')
        
        # Restore original clipboard content
        pyperclip.copy(original_clipboard)
        
        print("Search completed")
        logging.info("Search completed")
        return True
        
    except Exception as e:
        print(f"Error searching YouTube: {e}")
        logging.error(f"Error searching YouTube: {e}")
        
        # Fallback: Use direct URL if keyboard approach fails
        encoded_query = urllib.parse.quote(query)
        search_url = f"https://www.youtube.com/results?search_query={encoded_query}"
        webbrowser.open(search_url)
        time.sleep(2)
        
        print("Search completed using fallback method")
        logging.info("Search completed using fallback method")
        return True

def extract_search_query(command):
    search_phrases = [
        "search for",
        "search",
        "find",
        "look for",
        "look up"
    ]
    
    for phrase in search_phrases:
        if phrase in command:
            query = command.split(phrase, 1)[1].strip()
            if query:
                return query
    
    return ""

# ------------ MAIN PROGRAM ------------

def main():
    global volume_interface
    
    print("Unified Voice Assistant activated! Say 'exit' to quit or 'help' for commands.")
    logging.info("Unified Voice Assistant started")
    
    # Initialize volume control
    volume_interface = initialize_volume_control()
    if not volume_interface:
        print("Warning: Volume control could not be initialized.")
        logging.warning("Volume control initialization failed")
    else:
        current_volume = get_current_volume(volume_interface)
        print(f"Current volume: {current_volume}%")
    
    try:
        current_brightness = get_current_brightness()
        print(f"Current brightness: {current_brightness}%")
    except:
        print("Warning: Brightness control not available.")
        logging.warning("Brightness control not available")
    
    while True:
        command = recognize_voice()
        
        if not command:
            continue
        
        # ---- EXIT COMMAND ----
        if "exit" in command or "quit" in command or "stop program" in command:
            print("Goodbye!")
            logging.info("Unified Voice Assistant stopped by user command")
            break
            
        # ---- WHATSAPP COMMANDS ----
        elif "open whatsapp" in command:
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
        
        # ---- VOLUME COMMANDS ----
        elif "volume up" in command or "increase volume" in command:
            if volume_interface:
                increase_volume(volume_interface, 10)
            else:
                print("Volume control not available.")
                
        elif "volume down" in command or "decrease volume" in command:
            if volume_interface:
                decrease_volume(volume_interface, 10)
            else:
                print("Volume control not available.")
                
        elif "mute" in command and "unmute" not in command:
            if volume_interface:
                toggle_mute(volume_interface)
            else:
                print("Volume control not available.")
                
        elif "unmute" in command:
            if volume_interface:
                is_muted = volume_interface.GetMute()
                if is_muted:
                    toggle_mute(volume_interface)
            else:
                print("Volume control not available.")
                
        # ---- BRIGHTNESS COMMANDS ----
        elif "brightness up" in command or "increase brightness" in command:
            increase_brightness(10)
                
        elif "brightness down" in command or "decrease brightness" in command:
            decrease_brightness(10)
                
        # ---- SPECIFIC LEVEL COMMANDS ----
        elif ("set volume" in command or "set brightness" in command or 
              "volume to" in command or "brightness to" in command):
            process_specific_level_command(command, volume_interface)
        
        # ---- GET CURRENT SETTINGS ----
        elif "current volume" in command or "what's the volume" in command or "what is the volume" in command:
            if volume_interface:
                current_volume = get_current_volume(volume_interface)
                print(f"Current volume is {current_volume}%")
            else:
                print("Volume control not available.")
                
        elif "current brightness" in command or "what's the brightness" in command or "what is the brightness" in command:
            try:
                current_brightness = get_current_brightness()
                print(f"Current brightness is {current_brightness}%")
            except:
                print("Brightness control not available.")
        
        # ---- YOUTUBE COMMANDS ----
        elif "open youtube" in command:
            open_youtube()
        
        elif any(phrase in command for phrase in ["search for", "search", "find", "look for", "look up"]):
            search_query = extract_search_query(command)
            
            if search_query:
                search_youtube(search_query)
            else:
                print("I couldn't understand what you want to search for.")
                
        # ---- MOUSE CONTROL ----
        elif "click" in command:
            pyautogui.click()
            logging.info("Mouse clicked")
                
        # ---- HELP COMMAND ----
        elif "help" in command:
            help_text = """
            Available commands:
            
            - WhatsApp:
              - open whatsapp
              - send message (will ask for contact and message)
            
            - Volume:
              - volume up / increase volume
              - volume down / decrease volume
              - mute / unmute
              - set volume to [number] percent
              - what's the volume / current volume
              
            - Brightness:
              - brightness up / increase brightness
              - brightness down / decrease brightness
              - set brightness to [number] percent
              - what's the brightness / current brightness
              
            - YouTube:
              - open youtube
              - search for [anything]
              - find [anything]
              
            - Other:
              - click (clicks at current mouse position)
              - exit / quit / stop program
            """
            print(help_text)
            logging.info("Help displayed")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logging.critical(f"Critical error in main program: {e}")
        print(f"A critical error occurred: {e}")