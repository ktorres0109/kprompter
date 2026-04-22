"""
macOS global hotkey monitor.

Strategy:
1. CGEventTap (kCGSessionEventTap, ListenOnly) — requires Accessibility.
   This is the gold standard: fires for every real key event system-wide.
2. NSEvent addGlobalMonitorForEventsMatchingMask — also requires Accessibility,
   but works even when CGEventTap is unavailable in some sandboxed contexts.
   Requires a running NSRunLoop (we pump it on a background thread).

Both are tried on start(). is_active is only True when at least one of them
succeeded — this lets the caller know whether Accessibility was granted.
"""

import threading

_MOD_FLAGS = {
    "ctrl":    0x00040000,
    "control": 0x00040000,
    "alt":     0x00080000,
    "option":  0x00080000,
    "cmd":     0x00100000,
    "command": 0x00100000,
    "super":   0x00100000,
    "meta":    0x00100000,
    "shift":   0x00020000,
}

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

_OPT_CHARS = {
    "©": "g", "®": "r", "ß": "s", "∂": "d", "ƒ": "f",
    "å": "a", "∫": "b", "ç": "c", "˙": "h", "∆": "j",
    "˚": "k", "¬": "l", "µ": "m", "ø": "o", "π": "p",
    "œ": "q", "†": "t", "√": "v", "∑": "w", "≈": "x",
    "¥": "y", "ω": "z", "Ω": "z",
}

# NSEvent modifier flag constants
_NS_MOD_FLAGS = {
    "ctrl":    1 << 18,   # NSEventModifierFlagControl
    "control": 1 << 18,
    "alt":     1 << 19,   # NSEventModifierFlagOption
    "option":  1 << 19,
    "cmd":     1 << 20,   # NSEventModifierFlagCommand
    "command": 1 << 20,
    "super":   1 << 20,
    "meta":    1 << 20,
    "shift":   1 << 17,   # NSEventModifierFlagShift
}


from config import _dbg

# Keycode → modifier flag mask for tracking held modifiers in CGEventTap.
# Defined once at module level — not rebuilt per call.
_MOD_KEYCODES = {
    54: 0x00100000,  # right cmd
    55: 0x00100000,  # left cmd
    56: 0x00020000,  # left shift
    58: 0x00080000,  # left option
    59: 0x00040000,  # left ctrl
    60: 0x00020000,  # right shift
    61: 0x00080000,  # right option
    62: 0x00040000,  # right ctrl
}


def _parse_hotkey(hotkey_str):
    mod_mask = 0
    ns_mod_mask = 0
    keycode = None
    for part in hotkey_str.lower().split("+"):
        part = part.strip()
        part = _OPT_CHARS.get(part, part)
        if part in _MOD_FLAGS:
            mod_mask |= _MOD_FLAGS[part]
            ns_mod_mask |= _NS_MOD_FLAGS[part]
        elif part in _KEY_CODES:
            keycode = _KEY_CODES[part]
        else:
            print(f"[hotkey_macos] Unknown key component: {part!r}")
    return mod_mask, ns_mod_mask, keycode


class HotkeyMonitor:
    """
    Global hotkey monitor. Tries CGEventTap first, falls back to NSEvent monitor.
    Call start() from the main thread (via root.after(0, ...)).
    """

    def __init__(self, hotkey_str: str, callback):
        self._hotkey_str = hotkey_str
        self._callback = callback
        self._tap = None
        self._src = None
        self._ns_monitor = None
        self._mod_mask, self._ns_mod_mask, self._keycode = _parse_hotkey(hotkey_str)

    def start(self):
        if self._tap is not None or self._ns_monitor is not None:
            return
        if self._keycode is None:
            _dbg(f"[hotkey_macos] No key in hotkey string: {self._hotkey_str!r}")
            return

        # Try CGEventTap first (best option)
        if self._try_cgeventtap():
            return

        # Fall back to NSEvent global monitor
        self._try_nsevent()

    def _try_cgeventtap(self):
        """Run CGEventTap on a dedicated background thread with its own CFRunLoop.
        This prevents macOS from disabling the tap due to slow main-thread callbacks."""
        try:
            import Quartz
        except ImportError:
            _dbg("[hotkey_macos] Quartz not available")
            return False

        req_kc = self._keycode
        req_mods = self._mod_mask
        cb = self._callback
        self._tap_stop = False
        registered = threading.Event()
        success = [False]

        _current_mods = 0

        def _tap_thread():
            nonlocal _current_mods
            import Quartz as Q

            def _handler(proxy, event_type, event, refcon):
                nonlocal _current_mods
                kc = Q.CGEventGetIntegerValueField(event, Q.kCGKeyboardEventKeycode)
                if event_type == Q.kCGEventFlagsChanged:
                    mod_bit = _MOD_KEYCODES.get(kc, 0)
                    if mod_bit:
                        raw = Q.CGEventGetFlags(event)
                        if raw & mod_bit:
                            _current_mods |= mod_bit
                        else:
                            _current_mods &= ~mod_bit
                elif event_type == Q.kCGEventKeyDown:
                    mods = _current_mods
                    _dbg(f"KeyDown kc={kc} mods=0x{mods:08x} req_kc={req_kc} req_mods=0x{req_mods:08x} match={kc==req_kc and mods==req_mods}")
                    if kc == req_kc and mods == req_mods:
                        cb()
                return event

            mask = (Q.CGEventMaskBit(Q.kCGEventKeyDown) |
                    Q.CGEventMaskBit(Q.kCGEventFlagsChanged))

            tap = Q.CGEventTapCreate(
                Q.kCGSessionEventTap,
                Q.kCGHeadInsertEventTap,
                Q.kCGEventTapOptionListenOnly,
                mask, _handler, None,
            )
            _dbg(f"[hotkey_macos] CGEventTap -> {'OK' if tap else 'None'}")
            if tap is None:
                registered.set()
                return

            src = Q.CFMachPortCreateRunLoopSource(None, tap, 0)
            rl = Q.CFRunLoopGetCurrent()
            Q.CFRunLoopAddSource(rl, src, Q.kCFRunLoopCommonModes)
            Q.CGEventTapEnable(tap, True)
            self._tap = tap
            self._src = src
            success[0] = True
            _dbg(f"[hotkey_macos] CGEventTap active on bg thread for {self._hotkey_str}")
            registered.set()

            # Pump this thread's runloop; re-enable tap if macOS disables it
            while not self._tap_stop:
                Q.CFRunLoopRunInMode(Q.kCFRunLoopDefaultMode, 0.5, False)
                if self._tap is not None and not Q.CGEventTapIsEnabled(self._tap):
                    _dbg("[hotkey_macos] tap disabled by macOS — re-enabling")
                    Q.CGEventTapEnable(self._tap, True)

            Q.CFRunLoopRemoveSource(rl, src, Q.kCFRunLoopCommonModes)
            Q.CGEventTapEnable(tap, False)
            _dbg("[hotkey_macos] CGEventTap thread exited")

        t = threading.Thread(target=_tap_thread, daemon=True)
        t.start()
        if not registered.wait(timeout=3.0):
            # Thread timed out before signalling — stop it to prevent leak
            self._tap_stop = True
            return False

        if success[0]:
            return True
        else:
            self._tap_stop = True
            return False

    def _try_nsevent(self):
        """
        Register an NSEvent global monitor on a dedicated background thread
        that owns its own NSRunLoop. This is the correct pattern:
        - addGlobalMonitorForEventsMatchingMask must be called from a thread
          with a running NSRunLoop
        - The handler fires on that same thread's runloop
        - Tkinter's main thread is NOT suitable because its CFRunLoop doesn't
          pump NSEvent's global monitor queue reliably
        """
        try:
            from AppKit import NSEvent, NSKeyDownMask
            import Quartz
        except ImportError:
            _dbg("[hotkey_macos] AppKit not available for NSEvent fallback")
            return

        req_ns_mods = self._ns_mod_mask
        req_kc = self._keycode
        cb = self._callback
        self._runloop_stop = False
        registered = threading.Event()
        success = [False]

        def _thread_main():
            """Run entirely on a background thread with its own NSRunLoop."""
            try:
                def _handler(event):
                    try:
                        kc = event.keyCode()
                        flags = event.modifierFlags() & (
                            (1 << 17) | (1 << 18) | (1 << 19) | (1 << 20)
                        )
                        _dbg(f"NSEvent kc={kc} flags=0x{flags:08x} req_kc={req_kc} req_ns_mods=0x{req_ns_mods:08x} match={kc == req_kc and flags == req_ns_mods}")
                        if kc == req_kc and flags == req_ns_mods:
                            cb()
                    except Exception as e:
                        _dbg(f"[hotkey_macos] NSEvent handler error: {e}")

                monitor = NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(
                    NSKeyDownMask, _handler
                )
                if monitor is None:
                    _dbg("[hotkey_macos] NSEvent.addGlobalMonitor returned None (Accessibility not granted?)")
                    registered.set()
                    return

                self._ns_monitor = monitor
                success[0] = True
                _dbg(f"[hotkey_macos] NSEvent monitor active on background thread for {self._hotkey_str}")
                registered.set()

                # Pump this thread's NSRunLoop until stop() is called
                while not self._runloop_stop:
                    Quartz.CFRunLoopRunInMode(Quartz.kCFRunLoopDefaultMode, 0.25, False)

                NSEvent.removeMonitor_(monitor)
                self._ns_monitor = None
                _dbg("[hotkey_macos] NSEvent monitor thread exited")
            except Exception as e:
                _dbg(f"[hotkey_macos] NSEvent thread error: {e}")
                registered.set()

        t = threading.Thread(target=_thread_main, daemon=True)
        t.start()
        # Wait up to 2s for registration to complete
        registered.wait(timeout=2.0)
        if not success[0]:
            self._runloop_stop = True  # signal thread to exit

    def stop(self):
        try:
            self._tap_stop = True
            self._tap = None
            self._src = None
        except Exception as e:
            _dbg(f"[hotkey_macos] stop tap error: {e}")

        try:
            # Signal the NSEvent background thread to stop (it removes the monitor itself)
            self._runloop_stop = True
        except Exception as e:
            _dbg(f"[hotkey_macos] stop ns monitor error: {e}")

        _dbg("[hotkey_macos] Monitor stopped.")

    @property
    def is_active(self):
        return self._tap is not None or self._ns_monitor is not None
