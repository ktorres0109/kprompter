import platform
import subprocess
import time

SYSTEM = platform.system()


def get_selected_text() -> tuple:
    """Grab currently selected text. Returns (text, original_clipboard)."""
    original = _get_clipboard()
    _set_clipboard("")
    _send_copy()
    time.sleep(0.2)   # wait for copy to land
    text = _get_clipboard()
    return text, original


def paste_text(text: str, original_clipboard: str = None):
    """Paste text in place, then restore original clipboard."""
    _set_clipboard(text)
    time.sleep(0.15)
    _send_paste()
    time.sleep(0.3)   # wait for paste to land before restoring clipboard
    if original_clipboard is not None:
        _set_clipboard(original_clipboard)


def _send_copy():
    if SYSTEM == "Darwin":
        _applescript('tell application "System Events" to keystroke "c" using command down')
    else:
        import pyautogui
        pyautogui.hotkey("ctrl", "c")


def _send_paste():
    if SYSTEM == "Darwin":
        _applescript('tell application "System Events" to keystroke "v" using command down')
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


def _applescript(script: str):
    subprocess.run(["osascript", "-e", script], check=True)
