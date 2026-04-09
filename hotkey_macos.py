"""
macOS global hotkey listener — runs as a SUBPROCESS.

This script uses Quartz CGEventTap to listen for a global hotkey combo.
It prints "HOTKEY\n" to stdout each time the hotkey is triggered.

Usage:  python hotkey_macos.py "ctrl+alt+g"

This MUST run in its own process (not a thread inside the main app) because
CGEventTap / Quartz initializes AppKit, and macOS requires all AppKit calls
to happen on the main thread.  The parent process runs tkinter on its main
thread, so we cannot share the process.
"""
import sys
import signal

# ── Modifier and key-code mapping ───────────────────────────────────────────

# Quartz modifier flags (mask bits)
_MOD_FLAGS = {
    "ctrl":    0x00040000,   # kCGEventFlagMaskControl
    "control": 0x00040000,
    "alt":     0x00080000,   # kCGEventFlagMaskAlternate
    "option":  0x00080000,
    "cmd":     0x00100000,   # kCGEventFlagMaskCommand
    "command": 0x00100000,
    "super":   0x00100000,
    "meta":    0x00100000,
    "shift":   0x00020000,   # kCGEventFlagMaskShift
}

# Common key codes on macOS (US keyboard layout)
_KEY_CODES = {
    "a": 0, "b": 11, "c": 8, "d": 2, "e": 14, "f": 3, "g": 5, "h": 4,
    "i": 34, "j": 38, "k": 40, "l": 37, "m": 46, "n": 45, "o": 31,
    "p": 35, "q": 12, "r": 15, "s": 1, "t": 17, "u": 32, "v": 9,
    "w": 13, "x": 7, "y": 16, "z": 6,
    "0": 29, "1": 18, "2": 19, "3": 20, "4": 21, "5": 23, "6": 22,
    "7": 26, "8": 28, "9": 25,
    "space": 49, "return": 36, "escape": 53, "tab": 48,
    "f1": 122, "f2": 120, "f3": 99, "f4": 118, "f5": 96, "f6": 97,
    "f7": 98, "f8": 100, "f9": 101, "f10": 109, "f11": 103, "f12": 111,
}


def _parse_hotkey(hotkey_str):
    """Parse 'ctrl+alt+g' into (required_modifier_mask, keycode)."""
    parts = hotkey_str.lower().split("+")
    mod_mask = 0
    keycode = None
    for p in parts:
        p = p.strip()
        if p in _MOD_FLAGS:
            mod_mask |= _MOD_FLAGS[p]
        elif p in _KEY_CODES:
            keycode = _KEY_CODES[p]
        else:
            print(f"[hotkey_macos] Unknown key component: {p!r}", file=sys.stderr)
    return mod_mask, keycode


def main():
    hotkey_str = sys.argv[1] if len(sys.argv) > 1 else "ctrl+alt+g"
    required_mods, required_keycode = _parse_hotkey(hotkey_str)

    if required_keycode is None:
        print(f"[hotkey_macos] No letter/key found in hotkey: {hotkey_str!r}",
              file=sys.stderr)
        sys.exit(1)

    # Import Quartz only here — this process owns the AppKit context
    try:
        import Quartz
    except ImportError:
        print("[hotkey_macos] Quartz (pyobjc) not available. "
              "Install pyobjc-framework-Quartz.", file=sys.stderr)
        sys.exit(1)

    def callback(proxy, event_type, event, refcon):
        if event_type == Quartz.kCGEventKeyDown:
            kc = Quartz.CGEventGetIntegerValueField(
                event, Quartz.kCGKeyboardEventKeycode)
            flags = Quartz.CGEventGetFlags(event)
            # Check if the pressed key matches AND all required modifiers are held
            if kc == required_keycode and (flags & required_mods) == required_mods:
                sys.stdout.write("HOTKEY\n")
                sys.stdout.flush()
        return event

    # Create an event tap for key-down events
    tap = Quartz.CGEventTapCreate(
        Quartz.kCGSessionEventTap,
        Quartz.kCGHeadInsertEventTap,
        Quartz.kCGEventTapOptionListenOnly,   # passive — don't block events
        Quartz.CGEventMaskBit(Quartz.kCGEventKeyDown),
        callback,
        None,
    )

    if tap is None:
        print("[hotkey_macos] Could not create event tap. "
              "Grant Accessibility permission in System Settings → "
              "Privacy & Security → Accessibility.", file=sys.stderr)
        sys.exit(1)

    run_loop_source = Quartz.CFMachPortCreateRunLoopSource(None, tap, 0)
    Quartz.CFRunLoopAddSource(
        Quartz.CFRunLoopGetCurrent(), run_loop_source,
        Quartz.kCFRunLoopCommonModes,
    )
    Quartz.CGEventTapEnable(tap, True)

    print(f"[hotkey_macos] Listening for {hotkey_str}", file=sys.stderr)

    # Let parent kill us cleanly
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    signal.signal(signal.SIGINT, lambda *_: sys.exit(0))

    # Run the Core Foundation run loop (blocks forever)
    Quartz.CFRunLoopRun()


if __name__ == "__main__":
    main()
