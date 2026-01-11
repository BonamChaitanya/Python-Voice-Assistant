import speech_recognition as sr
import pyautogui
import time
import logging
import os
import datetime
import wmi
import ctypes
from ctypes import cast, POINTER
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
import math
import screen_brightness_control as sbc

# Configure PyAutoGUI
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.5

# Set up logging
log_dir = os.path.join(os.path.expanduser('~'), 'voice_controller_logs')
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, f'system_controller_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
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

# Initialize volume control
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

# Function to get current volume (0-100)
def get_current_volume(volume_interface):
    try:
        if volume_interface:
            # Get current volume in dB (usually -65.25 to 0.0)
            current_volume_db = volume_interface.GetMasterVolumeLevel()
            # Convert to percentage (0-100)
            current_volume_scalar = volume_interface.GetMasterVolumeLevelScalar()
            current_volume = int(current_volume_scalar * 100)
            return current_volume
        return 0
    except Exception as e:
        print(f"Error getting current volume: {e}")
        logging.error(f"Error getting current volume: {e}")
        return 0

# Function to set volume (0-100)
def set_volume(volume_interface, volume_percent):
    try:
        if volume_interface:
            # Ensure volume is between 0 and 100
            volume_percent = max(0, min(100, volume_percent))
            # Convert to scalar value (0.0 to 1.0)
            volume_scalar = volume_percent / 100
            # Set the volume
            volume_interface.SetMasterVolumeLevelScalar(volume_scalar, None)
            print(f"Volume set to {volume_percent}%")
            logging.info(f"Volume set to {volume_percent}%")
            return True
        return False
    except Exception as e:
        print(f"Error setting volume: {e}")
        logging.error(f"Error setting volume: {e}")
        return False

# Function to increase volume by a percentage
def increase_volume(volume_interface, increment=10):
    try:
        current_volume = get_current_volume(volume_interface)
        new_volume = min(100, current_volume + increment)
        return set_volume(volume_interface, new_volume)
    except Exception as e:
        print(f"Error increasing volume: {e}")
        logging.error(f"Error increasing volume: {e}")
        return False

# Function to decrease volume by a percentage
def decrease_volume(volume_interface, decrement=10):
    try:
        current_volume = get_current_volume(volume_interface)
        new_volume = max(0, current_volume - decrement)
        return set_volume(volume_interface, new_volume)
    except Exception as e:
        print(f"Error decreasing volume: {e}")
        logging.error(f"Error decreasing volume: {e}")
        return False

# Function to mute/unmute volume
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

# Function to get current brightness (0-100)
def get_current_brightness():
    try:
        brightness = sbc.get_brightness()
        if isinstance(brightness, list):
            # If multiple displays, return the first one
            return brightness[0]
        return brightness
    except Exception as e:
        print(f"Error getting brightness: {e}")
        logging.error(f"Error getting brightness: {e}")
        return 0

# Function to set brightness (0-100)
def set_brightness(brightness_percent):
    try:
        # Ensure brightness is between 0 and 100
        brightness_percent = max(0, min(100, brightness_percent))
        sbc.set_brightness(brightness_percent)
        print(f"Brightness set to {brightness_percent}%")
        logging.info(f"Brightness set to {brightness_percent}%")
        return True
    except Exception as e:
        print(f"Error setting brightness: {e}")
        logging.error(f"Error setting brightness: {e}")
        return False

# Function to increase brightness by a percentage
def increase_brightness(increment=10):
    try:
        current_brightness = get_current_brightness()
        new_brightness = min(100, current_brightness + increment)
        return set_brightness(new_brightness)
    except Exception as e:
        print(f"Error increasing brightness: {e}")
        logging.error(f"Error increasing brightness: {e}")
        return False

# Function to decrease brightness by a percentage
def decrease_brightness(decrement=10):
    try:
        current_brightness = get_current_brightness()
        new_brightness = max(0, current_brightness - decrement)
        return set_brightness(new_brightness)
    except Exception as e:
        print(f"Error decreasing brightness: {e}")
        logging.error(f"Error decreasing brightness: {e}")
        return False

# Parse numeric value from command
def parse_numeric_value(command):
    import re
    # Look for patterns like "50 percent", "50%", "to 50", etc.
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

# Process a command to set volume or brightness to specific level
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

# Main Function
def main():
    print("System Controller activated! Say 'exit' to quit.")
    logging.info("System Controller started")
    
    # Initialize volume control
    volume_interface = initialize_volume_control()
    if not volume_interface:
        print("Warning: Volume control could not be initialized.")
        logging.warning("Volume control initialization failed")
    
    # Show current settings
    if volume_interface:
        current_volume = get_current_volume(volume_interface)
        print(f"Current volume: {current_volume}%")
        logging.info(f"Initial volume: {current_volume}%")
    
    try:
        current_brightness = get_current_brightness()
        print(f"Current brightness: {current_brightness}%")
        logging.info(f"Initial brightness: {current_brightness}%")
    except:
        print("Warning: Brightness control not available.")
        logging.warning("Brightness control not available")
    
    while True:
        command = recognize_voice()
        
        if not command:
            continue
        
        # Volume commands
        if "volume up" in command or "increase volume" in command:
            if volume_interface:
                increase_volume(volume_interface, 10)
            else:
                print("Volume control not available.")
                logging.warning("Volume control not available for increase")
                
        elif "volume down" in command or "decrease volume" in command:
            if volume_interface:
                decrease_volume(volume_interface, 10)
            else:
                print("Volume control not available.")
                logging.warning("Volume control not available for decrease")
                
        elif "mute" in command:
            if volume_interface:
                toggle_mute(volume_interface)
            else:
                print("Volume control not available.")
                logging.warning("Volume control not available for mute")
                
        elif "unmute" in command:
            if volume_interface:
                is_muted = volume_interface.GetMute()
                if is_muted:
                    toggle_mute(volume_interface)
            else:
                print("Volume control not available.")
                logging.warning("Volume control not available for unmute")
                
        # Brightness commands
        elif "brightness up" in command or "increase brightness" in command:
            increase_brightness(10)
                
        elif "brightness down" in command or "decrease brightness" in command:
            decrease_brightness(10)
                
        # Specific level commands
        elif ("set volume" in command or "set brightness" in command or 
              "volume to" in command or "brightness to" in command):
            process_specific_level_command(command, volume_interface)
        
        # Get current settings
        elif "current volume" in command or "what's the volume" in command:
            if volume_interface:
                current_volume = get_current_volume(volume_interface)
                print(f"Current volume is {current_volume}%")
            else:
                print("Volume control not available.")
                
        elif "current brightness" in command or "what's the brightness" in command:
            try:
                current_brightness = get_current_brightness()
                print(f"Current brightness is {current_brightness}%")
            except:
                print("Brightness control not available.")
                
        # Help command
        elif "help" in command:
            help_text = """
            Available commands:
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
              
            - exit / quit / stop
            """
            print(help_text)
            logging.info("Help displayed")
                
        # Exit command
        elif "exit" in command or "quit" in command or "stop" in command:
            print("Goodbye!")
            logging.info("System Controller stopped by user command")
            break

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logging.critical(f"Critical error in main program: {e}")
        print(f"A critical error occurred: {e}")