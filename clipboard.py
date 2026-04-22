import platform
import subprocess
import time
import uuid

from config import _dbg


def _as_str(s: str) -> str:
    """Escape a string for use inside an AppleScript double-quoted literal."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _hid_release_modifiers():
    """Post key-up events for Cmd, Alt, Shift, Ctrl at HID level to clear any held modifiers."""
    try:
        import Quartz as Q
        # keycodes: left cmd=55, left alt=58, left shift=56, left ctrl=59
        for kc in (55, 58, 56, 59):
            ev = Q.CGEventCreateKeyboardEvent(None, kc, False)
            Q.CGEventSetFlags(ev, 0)
            Q.CGEventPost(Q.kCGHIDEventTap, ev)
        time.sleep(0.03)
    except Exception:
        pass


def _hid_copy():
    """
    Post a real Cmd+C at the HID event tap level.
    This bypasses Electron's block on synthetic keystrokes from System Events.
    kCGHIDEventTap = 0 — indistinguishable from real hardware input.
    Releases any held modifiers first so the app sees a clean Cmd+C.
    """
    try:
        import Quartz as Q
        kc = 8  # 'c'
        cmd_flag = Q.kCGEventFlagMaskCommand

        down = Q.CGEventCreateKeyboardEvent(None, kc, True)
        Q.CGEventSetFlags(down, cmd_flag)
        up = Q.CGEventCreateKeyboardEvent(None, kc, False)
        Q.CGEventSetFlags(up, cmd_flag)

        Q.CGEventPost(Q.kCGHIDEventTap, down)
        time.sleep(0.04)
        Q.CGEventPost(Q.kCGHIDEventTap, up)
        return True
    except Exception:
        return False

SYSTEM = platform.system()

# Sentinel used to clear the clipboard before a copy so that
# change-detection always works even when selection == clipboard.
_SENTINEL_PREFIX = "\x00kp_sentinel_"


def _get_ax_selected_text(app_name: str = "") -> str:
    """Read selected text via PyObjC AXUIElement API (runs inside KPrompter process,
    which already has Accessibility). No subprocess — works on Electron/browsers too."""
    try:
        import Quartz
        from ApplicationServices import (
            AXUIElementCreateApplication,
            AXUIElementCopyAttributeValue,
            kAXSelectedTextAttribute,
            kAXFocusedUIElementAttribute,
        )

        # Find the target PID
        pid = None
        if app_name:
            # Look up by app name using NSWorkspace
            from AppKit import NSWorkspace
            for app in NSWorkspace.sharedWorkspace().runningApplications():
                if app.localizedName() == app_name:
                    pid = app.processIdentifier()
                    break
        if pid is None:
            # Fall back to frontmost app
            from AppKit import NSWorkspace
            front = NSWorkspace.sharedWorkspace().frontmostApplication()
            if front:
                pid = front.processIdentifier()

        if pid is None:
            return ""

        app_elem = AXUIElementCreateApplication(pid)

        # Try AXSelectedText on the app element directly first
        err, value = AXUIElementCopyAttributeValue(app_elem, kAXSelectedTextAttribute, None)
        _dbg(f"[AX] pid={pid} app_level err={err} value={str(value)[:60] if value else None}")
        if err == 0 and value:
            return str(value)

        # Try focused UI element → AXSelectedText
        err2, focused = AXUIElementCopyAttributeValue(app_elem, kAXFocusedUIElementAttribute, None)
        _dbg(f"[AX] focused_err={err2} focused={focused is not None}")
        if err2 == 0 and focused:
            err3, value2 = AXUIElementCopyAttributeValue(focused, kAXSelectedTextAttribute, None)
            _dbg(f"[AX] focused_text err={err3} value={str(value2)[:60] if value2 else None}")
            if err3 == 0 and value2:
                return str(value2)

        return ""
    except Exception as e:
        _dbg(f"[AX] exception: {e}")
        return ""


def grab_selected_text_now(source_app: str = "") -> str:
    """
    Grab selected text IMMEDIATELY — call this at hotkey time before any sleep.
    Tries AX first, then HID Cmd+C.
    Returns the text or "" if nothing found.
    """
    if SYSTEM != "Darwin":
        return ""

    # 1. AX — works on native apps
    ax_text = _get_ax_selected_text(source_app)
    if ax_text and ax_text.strip():
        _dbg(f"[grab_now] AX hit: {len(ax_text)} chars")
        return ax_text

    # 2. HID Cmd+C — wait for hotkey modifiers to release first (brief delay)
    # so the copy doesn't get swallowed by the app thinking it's still part of
    # the hotkey chord. We use a sentinel to detect clipboard change.
    original = _get_clipboard()
    sentinel = _SENTINEL_PREFIX + uuid.uuid4().hex
    _set_clipboard(sentinel)

    # Release modifiers and post copy
    _hid_release_modifiers()
    _hid_copy()

    # Poll up to 1.5s
    for _ in range(30):
        time.sleep(0.05)
        candidate = _get_clipboard()
        if candidate and candidate != sentinel:
            _set_clipboard(original)
            _dbg(f"[grab_now] HID copy hit: {len(candidate)} chars")
            return candidate

    _set_clipboard(original)
    _dbg("[grab_now] both AX and HID failed")
    return ""


def get_selected_text(source_app: str = "") -> tuple:
    """Grab currently selected text.  Returns (text, original_clipboard).

    Strategy on macOS:
      1. Try AXSelectedText via Accessibility API (works on Electron/browsers).
      2. Fall back to sentinel + Cmd+C clipboard method.
    """
    try:
        original = _get_clipboard()
    except Exception:
        original = ""

    if SYSTEM == "Darwin":
        # Try AX API first — works even on apps that block synthetic keystrokes
        ax_text = _get_ax_selected_text()
        if ax_text and ax_text.strip():
            return ax_text, original or ""

        # Fall back: sentinel + HID-level Cmd+C (works on Electron/browsers)
        sentinel = _SENTINEL_PREFIX + uuid.uuid4().hex
        try:
            _set_clipboard(sentinel)
        except Exception:
            sentinel = original

        # Activate source app first, then post HID Cmd+C
        if source_app:
            _applescript(f'tell application "{source_app}" to activate')
            time.sleep(0.15)

        # Try HID-level copy first (works on Electron); fall back to AppleScript
        if not _hid_copy():
            _applescript('tell application "System Events" to keystroke "c" using command down')

        # Poll until clipboard differs from sentinel (max 2 s).
        text = ""
        for _ in range(40):
            time.sleep(0.05)
            try:
                candidate = _get_clipboard()
            except Exception:
                continue
            if candidate and candidate != sentinel:
                text = candidate
                break

        # Restore original clipboard if nothing was captured.
        if not text:
            try:
                _set_clipboard(original)
            except Exception:
                pass

        return text or "", original or ""

    else:
        # Non-macOS: use the original change-detection approach.
        _send_copy()
        text = ""
        for _ in range(30):
            time.sleep(0.05)
            try:
                candidate = _get_clipboard()
            except Exception:
                continue
            if candidate and candidate != original:
                text = candidate
                break
        return text or "", original or ""


def paste_text(text: str, original_clipboard: str = None):
    """Paste text in place, then restore original clipboard.

    On macOS we use a single AppleScript block that:
      1. Sets the clipboard to the result text
      2. Sends Cmd+V to paste it
      3. Immediately restores the original clipboard
    All three steps happen in one script execution so clipboard managers
    see the original clipboard before and after — not the intermediate state.
    """
    if SYSTEM == "Darwin":
        paste_escaped    = _as_str(text)
        restore_escaped  = _as_str(original_clipboard or "")

        script = (
            f'set the clipboard to "{paste_escaped}"\n'
            f'delay 0.25\n'
            f'tell application "System Events" to keystroke "v" using command down\n'
            f'delay 0.35\n'
            f'set the clipboard to "{restore_escaped}"'
        )
        try:
            subprocess.run(["osascript", "-e", script], check=True, timeout=6)
        except Exception:
            # Fallback: original approach
            try:
                _set_clipboard(text)
            except Exception:
                return
            time.sleep(0.3)
            _send_paste()
            time.sleep(0.5)
            if original_clipboard is not None:
                try:
                    _set_clipboard(original_clipboard)
                except Exception:
                    pass
    else:
        try:
            _set_clipboard(text)
        except Exception:
            return
        time.sleep(0.3)
        _send_paste()
        time.sleep(0.6)
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
        for _ in range(3):
            try:
                result = subprocess.run(["pbpaste"], capture_output=True, text=True, timeout=3)
                if result.returncode == 0:
                    return result.stdout
            except Exception:
                pass
            time.sleep(0.05)
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
        for _ in range(3):
            try:
                result = subprocess.run(["pbcopy"], input=text.encode(), check=False, timeout=3)
                if result.returncode == 0:
                    return
            except Exception:
                pass
            time.sleep(0.05)
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


def get_frontmost_app() -> str:
    """Return the name of the currently frontmost application (macOS only)."""
    if SYSTEM != "Darwin":
        return ""
    try:
        result = subprocess.run(
            ["osascript", "-e",
             "tell application \"System Events\" to get name of first process whose frontmost is true"],
            capture_output=True, text=True, timeout=3,
        )
        return result.stdout.strip()
    except Exception:
        return ""


def activate_app(name: str):
    """Bring a named application to the foreground (macOS only)."""
    if SYSTEM != "Darwin" or not name:
        return
    try:
        subprocess.run(
            ["osascript", "-e", f"tell application \"{name}\" to activate"],
            check=False, timeout=3,
        )
    except Exception:
        pass


def _applescript(script: str):
    try:
        subprocess.run(["osascript", "-e", script], check=True, timeout=5)
    except Exception:
        pass
