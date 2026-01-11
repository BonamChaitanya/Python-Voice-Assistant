from flask import Flask, render_template, jsonify, request
import speech_recognition as sr
import logging
import os
import datetime
import re
import json
import threading
import time
import pyautogui
import pyperclip
import webbrowser
from ctypes import cast, POINTER
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
import screen_brightness_control as sbc

# Configure PyAutoGUI - safety settings
pyautogui.FAILSAFE = True  # Move mouse to corner to abort
pyautogui.PAUSE = 0.5      # Add pause between PyAutoGUI commands

app = Flask(__name__)

# Set up logging
log_dir = os.path.join(os.path.expanduser('~'), 'voice_controller_logs')
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, f'desktop_voice_assistant_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Global variables
is_listening = False
last_command = ""
last_response = ""
listening_thread = None
waiting_for_contact = False
waiting_for_message = False
contact_name = ""
volume_interface = None

# ------------ VOICE RECOGNITION FUNCTIONS ------------

def initialize_volume_control():
    try:
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(
            IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        return volume
    except Exception as e:
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
        logging.error(f"Error getting current volume: {e}")
        return 0

def set_volume(volume_interface, volume_percent):
    try:
        if volume_interface:
            volume_percent = max(0, min(100, volume_percent))
            volume_scalar = volume_percent / 100
            volume_interface.SetMasterVolumeLevelScalar(volume_scalar, None)
            logging.info(f"Volume set to {volume_percent}%")
            return f"Volume set to {volume_percent}%"
        return "Volume control not available"
    except Exception as e:
        logging.error(f"Error setting volume: {e}")
        return f"Error setting volume: {e}"

def get_current_brightness():
    """Get the current screen brightness level (0-100)"""
    try:
        brightness = sbc.get_brightness()
        if isinstance(brightness, list):
            return brightness[0]  # Return first monitor's brightness if multiple
        return brightness
    except Exception as e:
        logging.error(f"Error getting brightness: {e}")
        return 0

def set_brightness(brightness_percent):
    """Set the screen brightness level (0-100)"""
    try:
        brightness_percent = max(0, min(100, brightness_percent))
        sbc.set_brightness(brightness_percent)
        logging.info(f"Brightness set to {brightness_percent}%")
        return f"Brightness set to {brightness_percent}%"
    except Exception as e:
        logging.error(f"Error setting brightness: {e}")
        return f"Error setting brightness: {e}"

def increase_brightness(increment=10):
    """Increase the screen brightness by the specified increment"""
    try:
        current_brightness = get_current_brightness()
        new_brightness = min(100, current_brightness + increment)
        return set_brightness(new_brightness)
    except Exception as e:
        logging.error(f"Error increasing brightness: {e}")
        return f"Error increasing brightness: {e}"

def decrease_brightness(decrement=10):
    """Decrease the screen brightness by the specified decrement"""
    try:
        current_brightness = get_current_brightness()
        new_brightness = max(0, current_brightness - decrement)
        return set_brightness(new_brightness)
    except Exception as e:
        logging.error(f"Error decreasing brightness: {e}")
        return f"Error decreasing brightness: {e}"

def recognize_voice_once():
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        logging.info("Listening for command")

        # Adjust for ambient noise
        recognizer.adjust_for_ambient_noise(source, duration=0.5)
        try:
            # Listen for audio
            audio = recognizer.listen(source, timeout=5, phrase_time_limit=5)

            try:
                # Recognize speech using Google Speech Recognition
                command = recognizer.recognize_google(audio)
                logging.info(f"Command recognized: {command}")
                return command.lower()
            except sr.UnknownValueError:
                logging.warning("Command not recognized")
                return ""
            except sr.RequestError:
                logging.error("Speech service unavailable")
                return "ERROR: Speech service unavailable. Check your internet connection."
        except Exception as e:
            logging.error(f"Error listening: {e}")
            return ""

def continuous_listen():
    global is_listening, last_command, last_response, volume_interface, waiting_for_contact, waiting_for_message, contact_name

    if volume_interface is None:
        volume_interface = initialize_volume_control()

    while is_listening:
        command = recognize_voice_once()

        if not command:
            continue

        if command.startswith("ERROR:"):
            last_response = command
            continue

        last_command = command

        # Handle multi-step commands
        if waiting_for_contact:
            contact_name = command
            waiting_for_contact = False
            waiting_for_message = True
            response = f"Contact set to {contact_name}. What message would you like to send?"
            last_response = response
            continue

        if waiting_for_message and contact_name:
            message_text = command
            waiting_for_message = False
            response = send_whatsapp_message(contact_name, message_text)
            contact_name = ""
            last_response = response
            continue

        # Process regular commands
        response = process_command(command)
        last_response = response

        # Short pause to prevent CPU overuse
        time.sleep(0.5)


# ------------ WHATSAPP DESKTOP AUTOMATION FUNCTIONS ------------

def open_windows_search():
    """Opens the Windows search bar by pressing Win key"""
    try:
        logging.info("Opening Windows search")
        pyautogui.hotkey('win')  # Press Windows key to open search
        time.sleep(1)  # Wait for search bar to appear
        return True
    except Exception as e:
        logging.error(f"Error opening Windows search: {e}")
        return False


def open_whatsapp_desktop():
    """Open WhatsApp by using Windows search"""
    try:
        logging.info("Attempting to open WhatsApp desktop app")

        # First attempt: Try to use Windows search
        if open_windows_search():
            # Type "WhatsApp" in the search bar
            pyautogui.write("whatsapp")
            time.sleep(1.5)  # Wait for search results

            # Press Enter to open the top result
            pyautogui.press('enter')
            time.sleep(5)  # Give WhatsApp time to open

            # Log success
            logging.info("WhatsApp desktop app should now be open")
            return "WhatsApp opened successfully"

        # Second attempt: Try to use Run dialog
        logging.info("Trying alternative method to open WhatsApp")
        pyautogui.hotkey('win', 'r')  # Open Run dialog
        time.sleep(1)

        # Try to open WhatsApp from common installation paths
        pyautogui.write("explorer shell:AppsFolder")
        pyautogui.press('enter')
        time.sleep(2)

        # Type WhatsApp to search in apps folder
        pyautogui.write("whatsapp")
        time.sleep(1)
        pyautogui.press('enter')
        time.sleep(5)

        return "Attempted to open WhatsApp using alternative method"
    except Exception as e:
        logging.error(f"Error opening WhatsApp: {e}")
        return f"Error opening WhatsApp: {str(e)}"


def find_whatsapp_search():
    """Find and click on the search area in WhatsApp"""
    try:
        logging.info("Looking for WhatsApp search box")

        # Wait for WhatsApp to be fully loaded
        time.sleep(2)

        # Try keyboard shortcut Ctrl+F which often focuses the search in WhatsApp
        logging.info("Trying Ctrl+F shortcut for search")
        pyautogui.hotkey('ctrl', 'f')
        time.sleep(1)

        # If that didn't work, try clicking on the search area
        # Get screen dimensions
        screen_width, screen_height = pyautogui.size()

        # Try to click on the search box (typically in the upper part of the left panel)
        search_x = int(screen_width * 0.15)  # 15% from left edge
        search_y = int(screen_height * 0.1)  # 10% from top edge

        logging.info(f"Clicking at position ({search_x}, {search_y}) to find search box")
        pyautogui.click(search_x, search_y)
        time.sleep(0.5)

        return True
    except Exception as e:
        logging.error(f"Error finding WhatsApp search: {e}")
        return False


def search_whatsapp_contact(contact_name):
    """Search for a contact in WhatsApp and select the first result"""
    try:
        logging.info(f"Searching for contact: {contact_name}")

        # First find the search box
        if not find_whatsapp_search():
            logging.warning("Could not find WhatsApp search box, but will try to continue")

        # Clear any existing text in the search field
        pyautogui.hotkey('ctrl', 'a')  # Select all text
        pyautogui.press('delete')  # Delete selected text
        time.sleep(0.5)

        # Use clipboard for reliable input
        original_clipboard = pyperclip.paste()  # Save original clipboard
        pyperclip.copy(contact_name)
        pyautogui.hotkey('ctrl', 'v')  # Paste contact name
        time.sleep(2)  # Wait for search results

        # Now we need to select the first contact in the results
        # First, let's try pressing Enter to select the first result
        logging.info("Attempting to select first contact result by pressing Enter")
        pyautogui.press('enter')
        time.sleep(1.5)

        # If that didn't work, try clicking on the first search result
        # These positions are where the first contact usually appears
        # We'll try multiple positions to be more reliable
        screen_width, screen_height = pyautogui.size()

        first_contact_positions = [
            (int(screen_width * 0.15), int(screen_height * 0.2)),  # 15% from left, 20% from top
            (int(screen_width * 0.15), int(screen_height * 0.25)),  # 15% from left, 25% from top
            (int(screen_width * 0.2), int(screen_height * 0.2)),  # 20% from left, 20% from top
        ]

        for position in first_contact_positions:
            logging.info(f"Clicking first contact at position: {position}")
            pyautogui.click(position[0], position[1])
            time.sleep(1)
            # After the first click, break to avoid clicking multiple times
            break

        # Restore original clipboard
        pyperclip.copy(original_clipboard)

        return True
    except Exception as e:
        logging.error(f"Error searching for contact: {e}")
        return False


def find_and_click_call_button(call_type="voice"):
    """Find and click on the call button in WhatsApp chat"""
    try:
        logging.info(f"Looking for {call_type} call button")

        # Wait for the chat to be fully loaded
        time.sleep(1.5)

        # Get screen dimensions
        screen_width, screen_height = pyautogui.size()

        # These are the positions where the call buttons are typically located
        # The call buttons are usually in the top-right corner of the chat window

        # We'll define multiple possible positions for better reliability
        if call_type == "voice":
            # Voice call button positions (usually right header area)
            call_positions = [
                (int(screen_width * 0.75), int(screen_height * 0.08)),  # 75% from left, 8% from top
                (int(screen_width * 0.80), int(screen_height * 0.08)),  # 80% from left, 8% from top
                (int(screen_width * 0.85), int(screen_height * 0.08)),  # 85% from left, 8% from top
                # Add more positions as fallbacks
                (int(screen_width * 0.75), int(screen_height * 0.10)),  # 75% from left, 10% from top
                (int(screen_width * 0.80), int(screen_height * 0.10)),  # 80% from left, 10% from top
            ]
        else:  # video call
            # Video call button positions (usually next to voice call button)
            call_positions = [
                (int(screen_width * 0.80), int(screen_height * 0.08)),  # 80% from left, 8% from top
                (int(screen_width * 0.85), int(screen_height * 0.08)),  # 85% from left, 8% from top
                (int(screen_width * 0.90), int(screen_height * 0.08)),  # 90% from left, 8% from top
                # Add more positions as fallbacks
                (int(screen_width * 0.80), int(screen_height * 0.10)),  # 80% from left, 10% from top
                (int(screen_width * 0.85), int(screen_height * 0.10)),  # 85% from left, 10% from top
            ]

        # Try clicking each position until we find the call button
        for position in call_positions:
            logging.info(f"Trying to click {call_type} call button at: {position}")
            pyautogui.click(position[0], position[1])
            time.sleep(1.5)  # Wait to see if a call starts

            # Look for signs of a call starting
            # For now, we'll just try each position and hope one works
            # In a real implementation, we could check if a call UI appears

            # After clicking, break to avoid continuing if the call started
            break

        return True
    except Exception as e:
        logging.error(f"Error finding and clicking {call_type} call button: {e}")
        return False


def send_whatsapp_message(contact_name, message):
    """Send a message to a WhatsApp contact"""
    try:
        logging.info(f"Sending message to {contact_name}: {message}")

        # First open WhatsApp if it's not already open
        open_result = open_whatsapp_desktop()
        logging.info(open_result)
        time.sleep(3)  # Wait for WhatsApp to open

        # Then search for the contact
        if not search_whatsapp_contact(contact_name):
            logging.error(f"Failed to find contact: {contact_name}")
            return f"Failed to find contact: {contact_name}"

        # Click on the message input area (usually at the bottom of the window)
        screen_width, screen_height = pyautogui.size()
        message_x = int(screen_width * 0.5)  # Center horizontally
        message_y = int(screen_height * 0.9)  # 90% down from top (near bottom)

        logging.info(f"Clicking message input area at ({message_x}, {message_y})")
        pyautogui.click(message_x, message_y)
        time.sleep(0.5)

        # Clear any existing text
        pyautogui.hotkey('ctrl', 'a')
        pyautogui.press('delete')
        time.sleep(0.5)

        # Use clipboard for reliable message input
        original_clipboard = pyperclip.paste()  # Save original clipboard
        pyperclip.copy(message)
        pyautogui.hotkey('ctrl', 'v')  # Paste message
        time.sleep(0.5)
        pyperclip.copy(original_clipboard)  # Restore original clipboard

        # Send the message by pressing Enter
        pyautogui.press('enter')

        logging.info(f"Message sent to {contact_name}")
        return f"Message sent to {contact_name}: '{message}'"

    except Exception as e:
        logging.error(f"Error sending WhatsApp message: {e}")
        return f"Error sending WhatsApp message: {str(e)}"


def call_whatsapp_contact(contact_name, call_type="voice"):
    """Make a voice or video call to a WhatsApp contact"""
    try:
        logging.info(f"Initiating {call_type} call to {contact_name}")

        # First open WhatsApp if it's not already open
        open_result = open_whatsapp_desktop()
        logging.info(open_result)
        time.sleep(3)  # Wait for WhatsApp to open

        # Then search for the contact
        if not search_whatsapp_contact(contact_name):
            logging.error(f"Failed to find contact: {contact_name}")
            return f"Failed to find contact: {contact_name}"

        # Wait for the chat to open
        time.sleep(2)

        # Now find and click the appropriate call button
        if not find_and_click_call_button(call_type):
            logging.error(f"Failed to find {call_type} call button")
            return f"Failed to find {call_type} call button. The call could not be initiated."

        logging.info(f"{call_type.capitalize()} call initiated to {contact_name}")
        return f"{call_type.capitalize()} call initiated to {contact_name}"

    except Exception as e:
        logging.error(f"Error making WhatsApp {call_type} call: {e}")
        return f"Error making WhatsApp {call_type} call: {str(e)}"


def process_compound_whatsapp_command(command):
    """Process compound WhatsApp commands like 'open WhatsApp and text ... to ...'"""
    logging.info(f"Processing compound WhatsApp command: {command}")

    # Extract contact name and message for text commands
    text_pattern = r'text ["\'](.+?)["\'] to (.+)'  # Matches: text "message" to contact
    alt_text_pattern = r'text (.+?) to (.+)'  # Fallback: text message to contact

    # Extract contact name for call commands
    call_pattern = r'call (.+)'  # Matches: call contact
    video_call_pattern = r'video call (.+)'  # Matches: video call contact

    # Check for text command patterns
    match = re.search(text_pattern, command)
    if not match:
        match = re.search(alt_text_pattern, command)

    if match:
        message = match.group(1)
        contact = match.group(2)

        # Open WhatsApp and send the message
        open_result = open_whatsapp_desktop()
        logging.info(open_result)
        time.sleep(3)  # Wait for WhatsApp to open

        return send_whatsapp_message(contact, message)

    # Check for video call pattern
    match = re.search(video_call_pattern, command)
    if match:
        contact = match.group(1)
        return call_whatsapp_contact(contact, call_type="video")

    # Check for voice call pattern
    match = re.search(call_pattern, command)
    if match:
        contact = match.group(1)
        return call_whatsapp_contact(contact, call_type="voice")

    # If no pattern matched
    return "I couldn't understand the WhatsApp command. Please try again."


# ------------ YOUTUBE FUNCTIONALITY ------------

def open_chrome():
    """Open Google Chrome browser"""
    try:
        logging.info("Opening Google Chrome")

        # Try using Windows search
        if open_windows_search():
            # Type "chrome" in the search bar
            pyautogui.write("chrome")
            time.sleep(1)

            # Press Enter to open the top result
            pyautogui.press('enter')
            time.sleep(3)  # Wait for Chrome to open

            logging.info("Chrome opened successfully via search")
            return True

        # Alternative: Try using Run dialog
        logging.info("Trying alternative method to open Chrome")
        pyautogui.hotkey('win', 'r')  # Open Run dialog
        time.sleep(1)

        # Try to run Chrome directly
        pyautogui.write("chrome")
        pyautogui.press('enter')
        time.sleep(3)

        logging.info("Chrome opened successfully via Run dialog")
        return True

    except Exception as e:
        logging.error(f"Error opening Chrome: {e}")
        return False


def search_youtube(query):
    """Search YouTube for a specific query"""
    try:
        logging.info(f"Searching YouTube for: {query}")

        # First, open Chrome
        if not open_chrome():
            logging.warning("Failed to open Chrome, trying direct URL approach")

        # Prepare the YouTube search URL
        search_query = query.replace(' ', '+')
        youtube_search_url = f"https://www.youtube.com/results?search_query={search_query}"

        # Open the YouTube search URL
        webbrowser.open(youtube_search_url)
        time.sleep(4)  # Wait for the page to load

        logging.info(f"YouTube search for '{query}' completed")
        return f"Searched YouTube for '{query}'"

    except Exception as e:
        logging.error(f"Error searching YouTube: {e}")
        return f"Error searching YouTube: {str(e)}"


def play_first_youtube_result():
    """Click on the first video in YouTube search results"""
    try:
        logging.info("Attempting to play the first YouTube video result")

        # The first video is typically found in these screen coordinates
        # We'll try multiple positions for better reliability
        screen_width, screen_height = pyautogui.size()

        # Possible positions where the first video might be
        first_video_positions = [
            (int(screen_width * 0.4), int(screen_height * 0.3)),  # 40% from left, 30% from top
            (int(screen_width * 0.4), int(screen_height * 0.35)),  # 40% from left, 35% from top
            (int(screen_width * 0.5), int(screen_height * 0.3)),  # 50% from left, 30% from top
            (int(screen_width * 0.3), int(screen_height * 0.3)),  # 30% from left, 30% from top
        ]

        # Try clicking on each position until one works
        for position in first_video_positions:
            logging.info(f"Clicking potential first video at ({position[0]}, {position[1]})")
            pyautogui.click(position[0], position[1])
            time.sleep(2)  # Wait to see if video starts playing

            # After the first click, break to avoid clicking multiple times
            break

        logging.info("First YouTube result should now be playing")
        return "Playing the first YouTube video"

    except Exception as e:
        logging.error(f"Error playing first YouTube result: {e}")
        return f"Error playing first YouTube result: {str(e)}"


def search_and_play_youtube(query):
    """Search YouTube for a query and play the first result"""
    try:
        logging.info(f"Searching and playing YouTube video for: {query}")

        # First search YouTube
        search_result = search_youtube(query)
        logging.info(search_result)

        # Wait for search results to load
        time.sleep(3)

        # Then play the first result
        play_result = play_first_youtube_result()
        logging.info(play_result)

        return f"Playing YouTube video for '{query}'"

    except Exception as e:
        logging.error(f"Error in search and play YouTube: {e}")
        return f"Error playing YouTube video for '{query}': {str(e)}"


def process_youtube_command(command):
    """Process commands related to YouTube"""
    logging.info(f"Processing YouTube command: {command}")

    # Extract the search query
    patterns = [
        r'play (.+?) on youtube',
        r'play (.+?) in youtube',
        r'search and play (.+?) on youtube',
        r'search for (.+?) on youtube',
        r'find (.+?) on youtube',
        r'play (.+)',  # Fallback pattern
    ]

    for pattern in patterns:
        match = re.search(pattern, command)
        if match:
            query = match.group(1).strip()
            if query:
                return search_and_play_youtube(query)

    return "I couldn't understand what to play on YouTube. Please try again."


# ------------ BRIGHTNESS CONTROL FUNCTIONS ------------

def increase_volume(volume_interface, increment=10):
    try:
        current_volume = get_current_volume(volume_interface)
        new_volume = min(100, current_volume + increment)
        response = set_volume(volume_interface, new_volume)
        return response
    except Exception as e:
        logging.error(f"Error increasing volume: {e}")
        return f"Error increasing volume: {e}"


def decrease_volume(volume_interface, decrement=10):
    try:
        current_volume = get_current_volume(volume_interface)
        new_volume = max(0, current_volume - decrement)
        response = set_volume(volume_interface, new_volume)
        return response
    except Exception as e:
        logging.error(f"Error decreasing volume: {e}")
        return f"Error decreasing volume: {e}"


def toggle_mute(volume_interface):
    try:
        if volume_interface:
            is_muted = volume_interface.GetMute()
            volume_interface.SetMute(not is_muted, None)
            status = "muted" if not is_muted else "unmuted"
            logging.info(f"Volume {status}")
            return f"Volume {status}"
        return "Volume control not available"
    except Exception as e:
        logging.error(f"Error toggling mute: {e}")
        return f"Error toggling mute: {e}"


# ------------ COMMAND PROCESSING FUNCTIONS ------------

def process_command(command):
    global volume_interface, waiting_for_contact, waiting_for_message, contact_name

    # ---- EXIT COMMAND ----
    if "exit" in command or "quit" in command or "stop listening" in command:
        return "Voice recognition paused. Click 'Start Listening' to resume."

    # ---- YOUTUBE COMMANDS ----
    elif ("play" in command and "youtube" in command) or \
            (("search" in command or "find" in command) and "youtube" in command) or \
            "play" in command and any(music_term in command for music_term in ["song", "music", "video"]):
        return process_youtube_command(command)

    # ---- COMPOUND WHATSAPP COMMANDS ----
    # Handle commands like "Open WhatsApp and text 'message' to contact"
    elif ("open whatsapp" in command or "open what's app" in command) and "text" in command and "to" in command:
        return process_compound_whatsapp_command(command)

    # Handle commands like "Open WhatsApp and call contact"
    elif ("open whatsapp" in command or "open what's app" in command) and (
            "call" in command and not "video" in command):
        # Extract the contact name after "call"
        match = re.search(r'call (.+)', command)
        if match:
            contact = match.group(1)
            return call_whatsapp_contact(contact, "voice")
        else:
            return "I couldn't understand which contact to call."

    # Handle commands like "Open WhatsApp and video call contact"
    elif ("open whatsapp" in command or "open what's app" in command) and "video call" in command:
        # Extract the contact name after "video call"
        match = re.search(r'video call (.+)', command)
        if match:
            contact = match.group(1)
            return call_whatsapp_contact(contact, "video")
        else:
            return "I couldn't understand which contact to video call."

    # ---- WHATSAPP COMMANDS ----
    elif "open whatsapp" in command:
        return open_whatsapp_desktop()

    # Handle "message to contact that message" or "text to contact that message"
    elif "message to" in command or "text to" in command:
        if "message to" in command:
            # Extract contact name and message
            parts = command.split("message to", 1)
            if len(parts) > 1 and parts[1].strip():
                contact = parts[1].strip()
                if "that" in contact or "saying" in contact or "with" in contact:
                    # Complex command like "send message to John that I'll be late"
                    separator_words = ["that", "saying", "with"]
                    for word in separator_words:
                        if word in contact:
                            contact_parts = contact.split(word, 1)
                            if len(contact_parts) > 1:
                                contact_name = contact_parts[0].strip()
                                message = contact_parts[1].strip()
                                return send_whatsapp_message(contact_name, message)
                else:
                    # Only contact provided, ask for message
                    contact_name = contact
                    waiting_for_message = True
                    return f"What message would you like to send to {contact_name}?"

        elif "text to" in command:
            # Extract contact name and message
            parts = command.split("text to", 1)
            if len(parts) > 1 and parts[1].strip():
                contact = parts[1].strip()
                if "that" in contact or "saying" in contact or "with" in contact:
                    # Complex command like "text to John that I'll be late"
                    separator_words = ["that", "saying", "with"]
                    for word in separator_words:
                        if word in contact:
                            contact_parts = contact.split(word, 1)
                            if len(contact_parts) > 1:
                                contact_name = contact_parts[0].strip()
                                message = contact_parts[1].strip()
                                return send_whatsapp_message(contact_name, message)
                else:
                    # Only contact provided, ask for message
                    contact_name = contact
                    waiting_for_message = True
                    return f"What message would you like to send to {contact_name}?"

        # If we reach here, start the conversation flow for sending a message
        waiting_for_contact = True
        return "Who would you like to send a message to?"

    # Handle "call contact" commands
    elif "call" in command and not "video" in command:
        # Extract contact name after "call"
        match = re.search(r'call (.+)', command)
        if match:
            contact = match.group(1)
            return call_whatsapp_contact(contact, "voice")
        else:
            return "I couldn't understand which contact to call."

    # Handle "video call contact" commands
    elif "video call" in command:
        # Extract contact name after "video call"
        match = re.search(r'video call (.+)', command)
        if match:
            contact = match.group(1)
            return call_whatsapp_contact(contact, "video")
        else:
            return "I couldn't understand which contact to video call."

    # ---- VOLUME COMMANDS ----
    elif "volume up" in command or "increase volume" in command:
        if volume_interface:
            try:
                current_volume = get_current_volume(volume_interface)
                new_volume = min(100, current_volume + 10)
                return set_volume(volume_interface, new_volume)
            except Exception as e:
                logging.error(f"Error increasing volume: {e}")
                return f"Error increasing volume: {e}"
        else:
            return "Volume control not available."

    elif "volume down" in command or "decrease volume" in command:
        if volume_interface:
            try:
                current_volume = get_current_volume(volume_interface)
                new_volume = max(0, current_volume - 10)
                return set_volume(volume_interface, new_volume)
            except Exception as e:
                logging.error(f"Error decreasing volume: {e}")
                return f"Error decreasing volume: {e}"
        else:
            return "Volume control not available."

    # ---- BRIGHTNESS COMMANDS ----
    elif "brightness up" in command or "increase brightness" in command:
        try:
            return increase_brightness(10)
        except Exception as e:
            logging.error(f"Error increasing brightness: {e}")
            return f"Error increasing brightness: {e}"

    elif "brightness down" in command or "decrease brightness" in command or "reduce brightness" in command:
        try:
            return decrease_brightness(10)
        except Exception as e:
            logging.error(f"Error decreasing brightness: {e}")
            return f"Error decreasing brightness: {e}"

    elif "set brightness" in command:
        # Try to extract a numeric value
        match = re.search(r'set brightness (?:to |at |)(\d+)(?:%|percent|)', command)
        if match:
            try:
                brightness_level = int(match.group(1))
                return set_brightness(brightness_level)
            except Exception as e:
                logging.error(f"Error setting brightness: {e}")
                return f"Error setting brightness: {e}"
        else:
            return "Please specify a brightness level between 0 and 100 percent."

    # ---- HELP COMMAND ----
    elif "help" in command:
        help_text = """
        Available commands:

        - WhatsApp:
          - open whatsapp
          - open whatsapp and text "message" to contact
          - open whatsapp and call contact
          - open whatsapp and video call contact
          - message to [contact] that [message]
          - text to [contact] that [message]
          - call [contact]
          - video call [contact]

        - YouTube:
          - play [song/video name] on youtube
          - search for [query] on youtube
          - play [song/video name]

        - Volume:
          - volume up / increase volume
          - volume down / decrease volume

        - Brightness:
          - brightness up / increase brightness
          - brightness down / decrease brightness
          - set brightness to [level]

        - Other:
          - help (shows this message)
          - stop listening / exit / quit
        """
        logging.info("Help displayed")
        return help_text

    # Command not recognized
    else:
        return f"Command not recognized: {command}"


# ------------ FLASK ROUTES ------------

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/start_listening', methods=['POST'])
def start_listening():
    global is_listening, listening_thread

    if not is_listening:
        is_listening = True
        listening_thread = threading.Thread(target=continuous_listen)
        listening_thread.daemon = True
        listening_thread.start()
        return jsonify({"status": "Listening started"})
    else:
        return jsonify({"status": "Already listening"})


@app.route('/stop_listening', methods=['POST'])
def stop_listening():
    global is_listening, waiting_for_contact, waiting_for_message

    is_listening = False
    waiting_for_contact = False
    waiting_for_message = False
    return jsonify({"status": "Listening stopped"})


@app.route('/get_status', methods=['GET'])
def get_status():
    global is_listening, last_command, last_response, waiting_for_contact, waiting_for_message

    status = {
        "is_listening": is_listening,
        "last_command": last_command,
        "last_response": last_response,
        "waiting_for_contact": waiting_for_contact,
        "waiting_for_message": waiting_for_message
    }

    # Add volume info if available
    if volume_interface:
        status["volume"] = get_current_volume(volume_interface)

    return jsonify(status)


@app.route('/execute_command', methods=['POST'])
def execute_command():
    data = request.get_json()
    if 'command' in data:
        command = data['command'].lower()
        response = process_command(command)
        return jsonify({"response": response})
    return jsonify({"error": "No command provided"})


# ------------ HTML TEMPLATE ------------


if __name__ == '__main__':
    # Initialize volume control at startup
    volume_interface = initialize_volume_control()
    if not volume_interface:
        logging.warning("Volume control initialization failed")

    # Use Waitress as a more stable server option
    try:
        from waitress import serve

        print("Starting server on http://127.0.0.1:5000")
        print("You can now say commands like:")
        print("- 'Open WhatsApp and text \"Hey how are you\" to Uday'")
        print("- 'Call Uday' (will open WhatsApp and make a voice call)")
        print("- 'Video call Uday' (will open WhatsApp and make a video call)")
        print("- 'Play Shape of You on YouTube'")
        print("- 'Brightness up' or 'Brightness down'")
        serve(app, host='127.0.0.1', port=5000)
    except ImportError:
        # Fall back to Flask's built-in server if Waitress is not installed
        print("Starting server on http://127.0.0.1:5000")
        print("You can now say commands like:")
        print("- 'Open WhatsApp and text \"Hey how are you\" to Uday'")
        print("- 'Call Uday' (will open WhatsApp and make a voice call)")
        print("- 'Video call Uday' (will open WhatsApp and make a video call)")
        print("- 'Play Shape of You on YouTube'")
        print("- 'Brightness up' or 'Brightness down'")
        app.run(debug=False, threaded=False, host='127.0.0.1', port=5000)