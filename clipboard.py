import platform
import subprocess
import time

SYSTEM = platform.system()


def get_selected_text() -> tuple:
    """Grab currently selected text. Returns (text, original_clipboard)."""
    try:
        original = _get_clipboard()
    except Exception:
        original = ""
    try:
        _set_clipboard("")
    except Exception:
        pass
    _send_copy()

    # Poll clipboard to catch text immediately when it arrives (max 1.5s)
    text = ""
    for _ in range(30):
        time.sleep(0.05)
        try:
            text = _get_clipboard()
        except Exception:
            text = ""
        if text:
            break

    return text or "", original or ""


def paste_text(text: str, original_clipboard: str = None):
    """Paste text in place, then restore original clipboard."""
    try:
        _set_clipboard(text)
    except Exception:
        return
    time.sleep(0.15)
    _send_paste()
    time.sleep(0.3)   # wait for paste to land before restoring clipboard
    if original_clipboard is not None:
        try:
            _set_clipboard(original_clipboard)
        except Exception:
            pass


def _send_copy():
    if SYSTEM == "Darwin":
        _applescript('tell application "System Events" to keystroke "c" using command down')
    else:
        try:
            import pyautogui
            pyautogui.hotkey("ctrl", "c")
        except Exception:
            pass


def _send_paste():
    if SYSTEM == "Darwin":
        _applescript('tell application "System Events" to keystroke "v" using command down')
    else:
        try:
            import pyautogui
            pyautogui.hotkey("ctrl", "v")
        except Exception:
            pass


def _get_clipboard() -> str:
    if SYSTEM == "Darwin":
        try:
            result = subprocess.run(["pbpaste"], capture_output=True, text=True, timeout=3)
            return result.stdout
        except Exception:
            return ""
    else:
        try:
            import pyperclip
            return pyperclip.paste()
        except Exception:
            # Fallback: try xclip directly
            try:
                result = subprocess.run(
                    ["xclip", "-selection", "clipboard", "-o"],
                    capture_output=True, text=True, timeout=3
                )
                return result.stdout
            except Exception:
                return ""


def _set_clipboard(text: str):
    if SYSTEM == "Darwin":
        try:
            subprocess.run(["pbcopy"], input=text.encode(), check=True, timeout=3)
        except Exception:
            pass
    else:
        try:
            import pyperclip
            pyperclip.copy(text)
        except Exception:
            # Fallback: try xclip directly
            try:
                subprocess.run(
                    ["xclip", "-selection", "clipboard"],
                    input=text.encode(), check=True, timeout=3
                )
            except Exception:
                pass


def _applescript(script: str):
    try:
        subprocess.run(["osascript", "-e", script], check=True, timeout=5)
    except Exception:
        pass
