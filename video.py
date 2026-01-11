import speech_recognition as sr
import webbrowser
import pyautogui
import time
import logging
import os
import datetime
import urllib.parse
import win32gui
import win32con
import pyperclip  # For clipboard operations

# Set up logging
log_dir = os.path.join(os.path.expanduser('~'), 'voice_controller_logs')
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, f'youtube_search_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Track if YouTube is already open
youtube_opened = False

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

# Function to find and focus YouTube window
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

# Function to open YouTube
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

# Function to search YouTube in the same tab
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

# Function to extract search query from command
def extract_search_query(command):
    # Common phrases used when asking to search
    search_phrases = [
        "search for",
        "search",
        "find",
        "look for",
        "look up"
    ]
    
    # Try to extract the query after each search phrase
    for phrase in search_phrases:
        if phrase in command:
            # Extract everything after the phrase
            query = command.split(phrase, 1)[1].strip()
            if query:
                return query
    
    # If no search phrase is found, return empty
    return ""

# Main Function
def main():
    print("Improved YouTube Voice Controller activated! Say 'exit' to quit.")
    logging.info("Improved YouTube Voice Controller started")
    
    while True:
        command = recognize_voice()
        
        if not command:
            continue
        
        # Exit command
        if "exit" in command or "quit" in command or "stop" in command:
            print("Goodbye!")
            logging.info("YouTube Voice Controller stopped by user command")
            break
        
        # Open YouTube command
        elif "open youtube" in command:
            open_youtube()
        
        # Search command
        elif any(phrase in command for phrase in ["search for", "search", "find", "look for", "look up"]):
            # Extract the search query from the command
            search_query = extract_search_query(command)
            
            if search_query:
                # Perform the search
                search_youtube(search_query)
            else:
                print("I couldn't understand what you want to search for.")
                logging.warning("Empty search query extracted")
        
        # Help command
        elif "help" in command:
            print("""
            Available commands:
            - "open youtube" - Opens YouTube in your browser
            - "search for [anything]" - Searches YouTube for specified content in the same tab
            - "exit" or "quit" - Exits the program
            """)
            logging.info("Help displayed")
        
        # Brief pause before next command
        time.sleep(0.5)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logging.critical(f"Critical error in main program: {e}")
        print(f"A critical error occurred: {e}")