import platform
import subprocess
import time

SYSTEM = platform.system()


def get_selected_text() -> str:
    """Copy current selection to clipboard and return it."""
    original = _get_clipboard()
    _clear_clipboard()
    _send_copy()
    time.sleep(0.15)
    text = _get_clipboard()
    return text, original


def paste_text(text: str, original_clipboard: str = None):
    """Set clipboard to text, paste it, then restore original clipboard."""
    _set_clipboard(text)
    time.sleep(0.1)
    _send_paste()
    time.sleep(0.15)
    if original_clipboard is not None:
        _set_clipboard(original_clipboard)


# --- internals ---

def _send_copy():
    if SYSTEM == "Darwin":
        _applescript('tell application "System Events" to keystroke "c" using command down')
    elif SYSTEM == "Windows":
        import pyautogui
        pyautogui.hotkey("ctrl", "c")
    else:
        import pyautogui
        pyautogui.hotkey("ctrl", "c")


def _send_paste():
    if SYSTEM == "Darwin":
        _applescript('tell application "System Events" to keystroke "v" using command down')
    elif SYSTEM == "Windows":
        import pyautogui
        pyautogui.hotkey("ctrl", "v")
    else:
        import pyautogui
        pyautogui.hotkey("ctrl", "v")


def _get_clipboard() -> str:
    if SYSTEM == "Darwin":
        result = subprocess.run(["pbpaste"], capture_output=True, text=True)
        return result.stdout
    else:
        import pyperclip
        return pyperclip.paste()


def _set_clipboard(text: str):
    if SYSTEM == "Darwin":
        subprocess.run(["pbcopy"], input=text.encode(), check=True)
    else:
        import pyperclip
        pyperclip.copy(text)


def _clear_clipboard():
    _set_clipboard("")


def _applescript(script: str):
    subprocess.run(["osascript", "-e", script], check=True)
