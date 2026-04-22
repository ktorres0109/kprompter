"""
KPrompter — main entry point
Hotkey → grab selection → optimize → paste back
"""
import sys
import threading
import platform
import tkinter as tk
import time
import os
import subprocess
import webbrowser

from config import load_config, is_first_run, PROVIDERS, get_best_model, _dbg
from optimizer import optimize
from clipboard import get_selected_text, paste_text, get_frontmost_app, activate_app, grab_selected_text_now
from gui import SetupWizard, SettingsWindow, LoadingPopup
from icon_gen import generate as gen_icon

SYSTEM = platform.system()


def _ax_trusted() -> bool:
    """Return True if this process has macOS Accessibility permission."""
    if SYSTEM != "Darwin":
        return True
    try:
        import ctypes
        ax = ctypes.cdll.LoadLibrary(
            "/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices"
        )
        ax.AXIsProcessTrusted.restype = ctypes.c_bool
        return bool(ax.AXIsProcessTrusted())
    except Exception:
        return True  # can't check — assume OK


class KPrompter:
    def __init__(self):
        self._busy = False
        self._busy_lock = threading.Lock()
        self._conversation: list = []
        self._project_windows: list = []
        self._tray = None
        self._root = None
        self._spinner = None
        self._listener = None           # pynput listener (Linux/Windows)
        self._hotkey_monitor = None     # HotkeyMonitor (macOS NSEvent)
        self._settings_win = None
        self._accessibility_prompted = False

    # ── Hotkey listener ───────────────────────────────────────────────────────

    def _start_hotkey_listener(self):
        cfg = load_config()
        hotkey_str = cfg.get("hotkey", "cmd+option+k" if SYSTEM == "Darwin" else "ctrl+alt+k")
        if SYSTEM == "Darwin":
            self._start_hotkey_macos(hotkey_str)
        else:
            self._start_hotkey_pynput(hotkey_str)

    # ── macOS: hotkey via NSEvent global monitor (main-thread, no subprocess) ──

    def _start_hotkey_macos(self, hotkey_str):
        """Install an NSEvent global key-down monitor for the hotkey.

        NSEvent.addGlobalMonitorForEventsMatchingMask_handler_ runs on the
        main thread's run loop (which tkinter's mainloop drives), so there is
        no subprocess, no second NSApplication, and no Gatekeeper issue.
        Requires Accessibility permission — if not granted the monitor returns
        None and we schedule a retry every 10 s until permission is given.
        """
        # Tear down any previous monitor first
        if self._hotkey_monitor is not None:
            self._hotkey_monitor.stop()
            self._hotkey_monitor = None

        from hotkey_macos import HotkeyMonitor

        def _on_hotkey():
            with self._busy_lock:
                if self._busy:
                    return
                self._busy = True
            # Only capture app name on tap thread — text grab needs its own thread
            # so HID events aren't posted from within the tap callback context.
            app_at_keypress = get_frontmost_app()
            _dbg(f"[_on_hotkey] app={app_at_keypress!r}")
            threading.Thread(
                target=self._run_flow,
                args=(app_at_keypress, ""),
                daemon=True
            ).start()

        monitor = HotkeyMonitor(hotkey_str, callback=_on_hotkey)

        # Must install on the main thread — use after() to be safe
        def _install():
            monitor.start()
            _dbg(f"[KPrompter] tap active={monitor.is_active} hotkey={hotkey_str}")
            if not monitor.is_active:
                # CGEventTap failed — Accessibility not granted yet.
                # Poll silently every 5 s until granted; open Settings once.
                self._check_accessibility()
                self._root.after(5_000, lambda: self._start_hotkey_macos(hotkey_str))
            else:
                self._hotkey_monitor = monitor
                self._accessibility_prompted = True  # mark as done

        if self._root:
            self._root.after(0, _install)
        else:
            # root not ready yet — will be called again once root exists
            pass

    # ── Linux/Windows: hotkey via pynput (safe — no AppKit conflict) ───────

    def _parse_hotkey(self, hotkey_str: str):
        """Parse 'ctrl+alt+g' into a frozenset of pynput keys.

        Only called on Linux/Windows — pynput must NEVER be imported on macOS
        because it initializes Quartz/AppKit which conflicts with tkinter's
        NSApplication on the main thread.
        """
        from pynput import keyboard as kb  # safe: only reachable on non-Darwin
        parts = hotkey_str.lower().split("+")
        keys = set()
        for p in parts:
            p = p.strip()
            if p in ("ctrl", "control"):
                keys.add(kb.Key.ctrl)
            elif p in ("alt", "option"):
                keys.add(kb.Key.alt)
            elif p in ("cmd", "command", "super", "meta"):
                keys.add(kb.Key.cmd)
            elif p == "shift":
                keys.add(kb.Key.shift)
            elif len(p) == 1:
                keys.add(kb.KeyCode.from_char(p.lower()))
        return frozenset(keys)

    def _start_hotkey_pynput(self, hotkey_str):
        if SYSTEM == "Darwin":
            # pynput must NEVER be imported on macOS — it initializes
            # Quartz/AppKit which conflicts with tkinter's NSApplication.
            print("[KPrompter] Warning: pynput hotkey listener not available on macOS.")
            return
        try:
            from pynput import keyboard as kb  # safe: guarded by Darwin check above
        except ImportError:
            print("[KPrompter] Warning: pynput not available. Hotkey disabled.")
            return

        target = self._parse_hotkey(hotkey_str)
        pressed = set()

        def _normalize(key):
            """Collapse left/right variants and normalize char case."""
            _map = {
                kb.Key.alt_l: kb.Key.alt, kb.Key.alt_r: kb.Key.alt,
                kb.Key.ctrl_l: kb.Key.ctrl, kb.Key.ctrl_r: kb.Key.ctrl,
                kb.Key.shift_l: kb.Key.shift, kb.Key.shift_r: kb.Key.shift,
                kb.Key.cmd_l: kb.Key.cmd, kb.Key.cmd_r: kb.Key.cmd,
            }
            key = _map.get(key, key)
            if isinstance(key, kb.KeyCode) and key.char:
                return kb.KeyCode.from_char(key.char.lower())
            return key

        def on_press(key):
            pressed.add(_normalize(key))
            if target and target.issubset(pressed):
                if not self._busy:
                    threading.Thread(target=self._run_flow, daemon=True).start()

        def on_release(key):
            pressed.discard(_normalize(key))

        try:
            self._listener = kb.Listener(on_press=on_press, on_release=on_release)
            self._listener.daemon = True
            self._listener.start()
            print(f"[KPrompter] Listening for hotkey: {hotkey_str}")
        except Exception as e:
            print(f"[KPrompter] Warning: Could not start hotkey listener: {e}")

    # ── Main flow ─────────────────────────────────────────────────────────────

    def _run_flow(self, source_app: str = "", pre_captured_text: str = ""):
        """Called by the hotkey: grab selection → optimize → paste back. Silent — no UI."""
        try:
            _dbg(f"[_run_flow] source_app={source_app!r}")

            # ── Accessibility gate ────────────────────────────────────────────
            if SYSTEM == "Darwin" and not _ax_trusted():
                self._show_error(
                    "⚠  Accessibility permission required.\n\n"
                    "Go to: System Settings → Privacy & Security → Accessibility\n"
                    "Enable KPrompter, then try the hotkey again."
                )
                self._busy = False
                return

            # ── Grab text NOW before any sleep (we're on a fresh thread, not tap thread) ──
            original_cb = ""
            if pre_captured_text and pre_captured_text.strip():
                text = pre_captured_text
            elif SYSTEM == "Darwin":
                text = grab_selected_text_now(source_app)
                original_cb = ""
            else:
                time.sleep(0.4)
                text, original_cb = get_selected_text("")

            # Brief pause for key releases to settle before we do anything else
            time.sleep(0.3)
            _dbg(f"[_run_flow] text={text[:50]!r} len={len(text)}")
            if not text or not text.strip():
                self._show_error(
                    "No text selected.\n\n"
                    "Select text in another app first, then trigger the hotkey.\n\n"
                    "If this keeps happening, check:\n"
                    "System Settings → Privacy & Security → Accessibility → KPrompter ✓"
                )
                self._busy = False
                return

            # ── Show in Home tab + typing indicator ──────────────────────────
            sw = getattr(self, "_settings_win", None)
            is_first = len(self._conversation) == 0
            if sw and self._root:
                self._root.after(0, lambda t=text: sw.append_user_message(t))
                self._root.after(0, sw.show_typing)

            # ── Optimize ──────────────────────────────────────────────────────
            try:
                result = optimize(
                    text,
                    is_first_message=is_first,
                    conversation_history=self._conversation if not is_first else None,
                )
            except Exception as e:
                if sw and self._root:
                    self._root.after(0, sw.hide_typing)
                self._show_error(str(e))
                return

            if sw and self._root:
                self._root.after(0, sw.hide_typing)

            if not result or not result.strip():
                self._show_error("AI returned an empty response. Please try again.")
                return

            # Detect clarifying questions (last line ends with "?" or ≥2 questions)
            q_count   = result.count("?")
            last_line = result.strip().splitlines()[-1].strip() if result.strip() else ""
            is_question = last_line.endswith("?") or q_count >= 2

            self._conversation.append({"role": "user",      "content": text})
            self._conversation.append({"role": "assistant", "content": result})
            if len(self._conversation) > 8:
                self._conversation = self._conversation[-8:]

            # ── Update Home tab with result ───────────────────────────────────
            if sw and self._root:
                self._root.after(0, lambda r=result: sw.append_ai_message(r))

            # ── Paste or show question popup ──────────────────────────────────
            if is_question:
                # AI has questions — show a small floating popup, stay in source app
                self._show_question_popup(result, original_cb, source_app)
            else:
                if source_app and SYSTEM == "Darwin":
                    activate_app(source_app)
                    time.sleep(0.3)
                paste_text(result, original_cb)

        except Exception as e:
            self._show_error(f"Unexpected error: {e}")
        finally:
            self._busy = False

    def _show_question_popup(self, question_text: str, original_cb: str, source_app: str = ""):
        """Show a small floating popup with the AI's question.
        User types an answer → we send it back through optimize → paste result.
        The main window is never shown."""
        if not self._root:
            return

        def _open():
            from gui import QuestionPopup
            def on_answer(answer: str):
                if answer and answer.strip():
                    threading.Thread(
                        target=self._run_answer_flow,
                        args=(answer, original_cb, source_app),
                        daemon=True,
                    ).start()
            QuestionPopup(self._root, question_text, on_answer=on_answer)

        self._root.after(0, _open)

    def _run_answer_flow(self, answer: str, original_cb: str, source_app: str):
        """After user answers the AI's question, optimize again and paste."""
        self._busy = True
        try:
            result = optimize(
                answer,
                is_first_message=False,
                conversation_history=self._conversation if self._conversation else None,
            )
            if not result or not result.strip():
                self._show_error("AI returned an empty response. Please try again.")
                return
            self._conversation.append({"role": "user",      "content": answer})
            self._conversation.append({"role": "assistant", "content": result})
            if len(self._conversation) > 8:
                self._conversation = self._conversation[-8:]
            if source_app and SYSTEM == "Darwin":
                activate_app(source_app)
                time.sleep(0.3)
            paste_text(result, original_cb)
        except Exception as e:
            self._show_error(str(e))
        finally:
            self._busy = False

    def _clear_conversation(self):
        self._conversation = []

    def _retry_input(self, text):
        with self._busy_lock:
            if self._busy:
                return
            self._busy = True
        threading.Thread(target=self._run_input_flow, args=(text,), daemon=True).start()

    def _optimize_from_input(self, text):
        """Called by the Home tab Optimize button — no clipboard/paste, just show result popup."""
        if not text.strip():
            return
        with self._busy_lock:
            if self._busy:
                return
            self._busy = True
        threading.Thread(target=self._run_input_flow, args=(text,), daemon=True).start()

    def _run_input_flow(self, text):
        sw = getattr(self, '_settings_win', None)
        try:
            is_first = len(self._conversation) == 0
            if self._root:
                if sw:
                    # Show user message immediately + typing indicator in the Home chat
                    self._root.after(0, lambda t=text: sw.append_user_message(t))
                    self._root.after(0, sw.show_typing)
                else:
                    self._root.after(0, self._start_spinner)
            try:
                result = optimize(
                    text, is_first_message=is_first,
                    conversation_history=self._conversation if not is_first else None,
                )
            except Exception as e:
                if self._root:
                    if sw:
                        self._root.after(0, sw.hide_typing)
                    else:
                        self._stop_spinner()
                self._show_error(str(e))
                return
            if self._root:
                if sw:
                    self._root.after(0, sw.hide_typing)
                else:
                    self._stop_spinner()
            if not result or not result.strip():
                self._show_error("AI returned an empty response. Please try again.")
                return
            self._conversation.append({"role": "user", "content": text})
            self._conversation.append({"role": "assistant", "content": result})
            if len(self._conversation) > 8:
                self._conversation = self._conversation[-8:]
            if self._root and sw:
                self._root.after(0, lambda r=result: sw.append_ai_message(r))
        except Exception as e:
            if self._root:
                if sw:
                    self._root.after(0, sw.hide_typing)
                else:
                    self._stop_spinner()
            self._show_error(f"Unexpected error: {e}")
        finally:
            self._busy = False

    def _start_spinner(self):
        try:
            self._spinner = LoadingPopup(self._root)
        except Exception:
            self._spinner = None

    def _stop_spinner(self):
        if self._root and self._spinner:
            try:
                self._root.after(0, self._spinner.close)
            except Exception:
                pass
            self._spinner = None

    def _show_error(self, msg):
        import tkinter.messagebox as mb
        if self._root:
            self._root.after(0, lambda m=msg: mb.showerror("KPrompter Error", m))

    def _restart_hotkey(self, new_hotkey: str):
        """Swap in a new hotkey without restarting the app."""
        if self._listener:
            try:
                self._listener.stop()
            except Exception:
                pass
            self._listener = None
        if self._hotkey_monitor:
            self._hotkey_monitor.stop()
            self._hotkey_monitor = None
        if SYSTEM == "Darwin":
            self._start_hotkey_macos(new_hotkey)
        else:
            self._start_hotkey_pynput(new_hotkey)

    def open_settings(self):
        if self._root:
            if self._settings_win is not None:
                self._root.after(0, self._settings_win.switch_to_settings)
            else:
                self._root.after(0, lambda: SettingsWindow(self._root))

    def quit_app(self):
        if self._listener:
            try:
                self._listener.stop()
            except Exception:
                pass
        if self._hotkey_monitor:
            self._hotkey_monitor.stop()
            self._hotkey_monitor = None
        if self._tray:
            try:
                self._tray.stop()
            except Exception:
                pass
        if self._root:
            try:
                self._root.after(0, self._root.quit)
            except Exception:
                pass

    def _show_about(self):
        import tkinter.messagebox as mb
        mb.showinfo("About KPrompter",
                    "KPrompter\n\nTransform rough text into AI-ready prompts.\n\n"
                    "github.com/ktorres0109/kprompter")

    def _setup_macos_menu(self):
        """Create a native macOS menu bar with File, View, Window, Help menus."""
        menubar = tk.Menu(self._root)

        # Apple menu
        app_menu = tk.Menu(menubar, name="apple", tearoff=0)
        app_menu.add_command(label="About KPrompter", command=self._show_about)
        app_menu.add_separator()
        app_menu.add_command(label="Settings…", command=self.open_settings,
                             accelerator="Command+,")
        app_menu.add_separator()
        app_menu.add_command(label="Quit KPrompter", command=self.quit_app,
                             accelerator="Command+Q")
        menubar.add_cascade(menu=app_menu)

        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="New Project Window", command=self._new_project_window,
                              accelerator="Command+N")
        menubar.add_cascade(label="File", menu=file_menu)

        # View menu
        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_command(label="Settings", command=self.open_settings,
                              accelerator="Command+,")
        menubar.add_cascade(label="View", menu=view_menu)

        # Window menu (name="window" → macOS manages minimize/zoom entries)
        window_menu = tk.Menu(menubar, name="window", tearoff=0)
        window_menu.add_command(label="Minimize", command=self._root.iconify,
                                accelerator="Command+M")
        menubar.add_cascade(label="Window", menu=window_menu)

        # Help menu (name="help" → macOS adds the search field)
        help_menu = tk.Menu(menubar, name="help", tearoff=0)
        help_menu.add_command(
            label="KPrompter on GitHub",
            command=lambda: webbrowser.open("https://github.com/ktorres0109/kprompter"),
        )
        menubar.add_cascade(label="Help", menu=help_menu)

        self._root.config(menu=menubar)
        self._root.bind("<Command-comma>", lambda e: self.open_settings())
        self._root.bind("<Command-q>", lambda e: self.quit_app())
        self._root.bind("<Command-m>", lambda e: self._root.iconify())
        self._root.bind("<Command-n>", lambda e: self._new_project_window())
        self._root.createcommand("tk::mac::Quit", self.quit_app)

    def _new_project_window(self):
        """Open a new project window with its own conversation context."""
        if self._root:
            from gui import ProjectWindow
            pw = ProjectWindow(
                self._root,
                on_optimize=self._optimize_for_project,
            )
            self._project_windows.append(pw)

    def _optimize_for_project(self, text: str, project):
        """Run optimization for a project window (uses project's conversation)."""
        if not text.strip():
            return
        threading.Thread(
            target=self._run_project_flow, args=(text, project), daemon=True
        ).start()

    def _run_project_flow(self, text: str, project):
        """Like _run_input_flow but operates on the project's conversation list."""
        project.busy = True
        try:
            is_first = len(project.conversation) == 0
            try:
                result = optimize(
                    text, is_first_message=is_first,
                    conversation_history=project.conversation if not is_first else None,
                )
            except Exception as e:
                self._show_error(str(e))
                return
            if not result or not result.strip():
                return
            project.conversation.append({"role": "user", "content": text})
            project.conversation.append({"role": "assistant", "content": result})
            if len(project.conversation) > 6:
                project.conversation = project.conversation[-6:]
            sw = getattr(self, "_settings_win", None)
            if sw and self._root:
                self._root.after(0, lambda r=result: sw.append_ai_message(r))
        except Exception:
            pass
        finally:
            project.busy = False

    def _setup_macos_window(self, cfg):
        """Single unified window: Home tab (status) + Settings tabs in one notebook."""
        self._root.configure(bg="#1c1c1e")
        self._root.minsize(620, 500)
        w, h = 780, 640
        sw = self._root.winfo_screenwidth()
        sh = self._root.winfo_screenheight()
        self._root.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")
        self._root.resizable(True, True)
        # Deiconify BEFORE building the UI so Canvas widgets can draw
        # (Canvas.create_* fails in withdrawn/unmapped windows on Python 3.14)
        self._root.deiconify()
        self._root.update_idletasks()
        self._settings_win = SettingsWindow(
            container=self._root, show_home=True,
            on_optimize=self._optimize_from_input,
            on_retry=self._retry_input,
            on_hotkey_change=self._restart_hotkey,
        )
        self._settings_win._on_clear_conversation = self._clear_conversation
        if hasattr(self._settings_win, "render_history"):
            self._settings_win.render_history(getattr(self, "_conversation", []))

    def _check_accessibility(self):
        """Open System Settings → Accessibility once if not yet trusted."""
        if SYSTEM != "Darwin":
            return
        if getattr(self, "_accessibility_prompted", False):
            return  # Already opened Settings this session — don't spam
        try:
            import ctypes
            ax = ctypes.cdll.LoadLibrary(
                "/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices"
            )
            ax.AXIsProcessTrusted.restype = ctypes.c_bool
            if ax.AXIsProcessTrusted():
                self._accessibility_prompted = True
                return  # Already granted — do nothing
            # Open Settings exactly once
            self._accessibility_prompted = True
            subprocess.run(
                ["open",
                 "x-apple.systempreferences:com.apple.preference.security"
                 "?Privacy_Accessibility"],
                check=False,
            )
        except Exception:
            pass


    def run(self):
        # Only generate icon in dev mode — frozen builds have the icon already bundled.
        # Re-generating overwrites it with a runtime-generated file that the OS
        # doesn't pick up for the Dock/Accessibility panel.
        if not getattr(sys, "frozen", False):
            gen_icon()

        self._root = tk.Tk()
        self._root.title("KPrompter")

        # Hide root initially on all platforms:
        # - Linux/Windows: users interact via tray icon
        # - macOS: avoid showing an empty window during the setup wizard
        self._root.withdraw()

        if is_first_run():
            wizard = SetupWizard(parent_root=self._root)
            wizard.run()

        cfg = load_config()
        if not cfg.get("api_key") and cfg.get("provider") != "ollama":
            print("[KPrompter] Warning: No API key set. Open Settings to add one.")

        self._start_hotkey_listener()

        if SYSTEM == "Darwin":
            # macOS: pystray's Icon.run() calls [NSApplication run] which
            # conflicts with tkinter's mainloop (also owns NSApplication).
            # Skip the tray icon entirely — keep the root window visible
            # with a status UI and native menu bar instead.
            # IMPORTANT: Do NOT import tray.py here — even importing pystray
            # on macOS initializes AppKit and causes SIGTRAP crashes.
            self._tray = None
            self._setup_macos_menu()
            self._setup_macos_window(cfg)  # deiconifies internally
            # macOS: close button (red X) hides window to dock.
            # Clicking the dock icon reopens it.  Quit via menu bar.
            self._root.protocol("WM_DELETE_WINDOW", self._root.withdraw)
            self._root.createcommand("tk::mac::ReopenApplication",
                                     self._root.deiconify)
            # Accessibility is checked inside _start_hotkey_macos when the tap fails.
        else:
            # Lazy import: tray.py imports pystray which touches AppKit on
            # macOS.  By importing only inside this non-Darwin branch we
            # guarantee pystray is NEVER loaded in the macOS process.
            from tray import build_tray
            try:
                self._tray = build_tray(
                    on_settings=self.open_settings,
                    on_log=self.open_settings,
                    on_quit=self.quit_app,
                )
            except Exception as e:
                print(f"[KPrompter] Warning: Could not create tray icon: {e}")
                self._tray = None

        print("[KPrompter] Running.")
        if self._tray:
            threading.Thread(target=self._run_tray_safe, daemon=True).start()
        self._root.mainloop()

    def _run_tray_safe(self):
        try:
            if self._tray:
                self._tray.run()
        except Exception as e:
            print(f"[KPrompter] Tray error: {e}")


if __name__ == "__main__":
    KPrompter().run()
