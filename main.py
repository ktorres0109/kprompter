"""
KPrompter — main entry point
Hotkey → grab selection → optimize → paste back
"""
import threading
import platform
import tkinter as tk
import time
import os
import subprocess
import sys

from config import load_config, is_first_run, PROVIDERS, get_best_model
from optimizer import optimize
from clipboard import get_selected_text, paste_text
from gui import SetupWizard, ResultPopup, SettingsWindow, LoadingPopup
from icon_gen import generate as gen_icon

SYSTEM = platform.system()


class KPrompter:
    def __init__(self):
        self._busy = False
        self._conversation: list = []
        self._tray = None
        self._root = None
        self._spinner = None
        self._listener = None       # pynput listener (Linux/Windows)
        self._hotkey_proc = None    # hotkey subprocess (macOS)

    # ── Hotkey listener ───────────────────────────────────────────────────────

    def _start_hotkey_listener(self):
        cfg = load_config()
        hotkey_str = cfg.get("hotkey", "ctrl+alt+g")
        if SYSTEM == "Darwin":
            self._start_hotkey_macos(hotkey_str)
        else:
            self._start_hotkey_pynput(hotkey_str)

    # ── macOS: hotkey via subprocess (avoids AppKit on background thread) ──

    def _start_hotkey_macos(self, hotkey_str):
        """Launch hotkey_macos.py as a child process with its own Quartz loop.

        On macOS, pynput's Listener starts a background thread that initializes
        Quartz/AppKit, which crashes because tkinter already owns NSApplication
        on the main thread.  By running the CGEventTap in a separate *process*,
        the child has its own AppKit context and the parent stays clean.
        """
        script = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "hotkey_macos.py")
        try:
            self._hotkey_proc = subprocess.Popen(
                [sys.executable, script, hotkey_str],
                stdout=subprocess.PIPE,
                stderr=None,       # let stderr pass through to console
                bufsize=1,         # line-buffered
                text=True,
            )
        except Exception as e:
            print(f"[KPrompter] Warning: Could not start macOS hotkey subprocess: {e}")
            return

        # Make stdout non-blocking so tkinter polling never stalls
        import fcntl
        fd = self._hotkey_proc.stdout.fileno()
        flags = fcntl.fcntl(fd, fcntl.F_GETFL)
        fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

        print(f"[KPrompter] Listening for hotkey (macOS subprocess): {hotkey_str}")
        self._poll_hotkey_subprocess()

    def _poll_hotkey_subprocess(self):
        """Non-blocking poll of the hotkey subprocess, driven by tkinter after()."""
        if not hasattr(self, "_hotkey_proc") or self._hotkey_proc is None:
            return
        if self._hotkey_proc.poll() is not None:
            print("[KPrompter] macOS hotkey subprocess exited.")
            return
        try:
            line = self._hotkey_proc.stdout.readline()
            if line and line.strip() == "HOTKEY":
                if not self._busy:
                    threading.Thread(target=self._run_flow, daemon=True).start()
        except (IOError, OSError):
            pass  # non-blocking read, no data available
        # Re-schedule poll (every 100ms — responsive without burning CPU)
        if self._root:
            self._root.after(100, self._poll_hotkey_subprocess)

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

    def _run_flow(self):
        self._busy = True
        try:
            time.sleep(0.08)  # small delay so key release doesn't interfere
            text, original_cb = get_selected_text()
            if not text or not text.strip():
                self._busy = False
                return

            is_first = self._ask_first_message_mode()
            if self._root:
                self._root.after(0, self._start_spinner)

            try:
                result = optimize(
                    text,
                    is_first_message=is_first,
                    conversation_history=self._conversation if not is_first else None,
                )
            except Exception as e:
                self._stop_spinner()
                self._show_error(str(e))
                return

            self._stop_spinner()

            if not result or not result.strip():
                self._show_error("AI returned an empty response. Please try again.")
                return

            # Detect if model is asking clarifying questions
            q_count = result.count("?")
            last_line = result.strip().splitlines()[-1].strip() if result.strip() else ""
            is_question = last_line.endswith("?") or q_count >= 2

            if is_question:
                self._show_question_popup(result, text, original_cb, is_first)
            else:
                paste_text(result, original_cb)
                self._conversation.append({"role": "user", "content": text})
                self._conversation.append({"role": "assistant", "content": result})
                if len(self._conversation) > 6:
                    self._conversation = self._conversation[-6:]
        except Exception as e:
            self._stop_spinner()
            self._show_error(f"Unexpected error: {e}")
        finally:
            self._busy = False

    def _ask_first_message_mode(self) -> bool:
        if not self._root:
            return True
        result = {"value": True}
        done = threading.Event()

        def ask():
            try:
                win = tk.Toplevel(self._root)
                win.title("KPrompter")
                win.configure(bg="#0d0f13")
                win.attributes("-topmost", True)
                win.resizable(False, False)
                sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
                win.geometry(f"400x155+{(sw-400)//2}+{(sh-155)//2}")

                tk.Label(
                    win, text="Is this the first message in a new project?",
                    bg="#0d0f13", fg="#e8eaf0",
                    font=("Menlo", 12) if SYSTEM == "Darwin" else ("Consolas", 11),
                    wraplength=360,
                ).pack(pady=(24, 14))

                row = tk.Frame(win, bg="#0d0f13")
                row.pack()

                def yes():
                    result["value"] = True
                    win.destroy()
                    done.set()

                def no():
                    result["value"] = False
                    win.destroy()
                    done.set()

                for label, cmd, bg, fg in [
                    ("Yes — new project", yes, "#4af0a0", "#0d0f13"),
                    ("No — continuing",   no,  "#1a1e27", "#e8eaf0"),
                ]:
                    b = tk.Button(row, text=label, command=cmd, bg=bg, fg=fg,
                                  activebackground=bg, activeforeground=fg,
                                  relief="flat", bd=0, padx=14, pady=8,
                                  cursor="hand2",
                                  font=("Menlo", 11) if SYSTEM == "Darwin" else ("Consolas", 10))
                    b.pack(side="left", padx=8)

                win.protocol("WM_DELETE_WINDOW", yes)
            except Exception:
                done.set()

        self._root.after(0, ask)
        done.wait(timeout=30)
        return result["value"]

    def _show_question_popup(self, questions, original_text, original_cb, is_first):
        def on_answer(answer):
            combined = f"{original_text}\n\n[Answers to clarifying questions]\n{answer}"
            threading.Thread(
                target=self._run_with_text,
                args=(combined, original_cb, is_first),
                daemon=True,
            ).start()

        if self._root:
            self._root.after(0, lambda: ResultPopup(
                self._root, questions, is_question=True,
                on_answer=on_answer, original_text=original_text,
            ))

    def _run_with_text(self, text, original_cb, is_first):
        self._busy = True
        try:
            result = optimize(
                text, is_first_message=is_first,
                conversation_history=self._conversation if not is_first else None,
            )
            paste_text(result, original_cb)
            self._conversation.append({"role": "user", "content": text})
            self._conversation.append({"role": "assistant", "content": result})
            if len(self._conversation) > 6:
                self._conversation = self._conversation[-6:]
        except Exception as e:
            self._show_error(str(e))
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

    def open_settings(self):
        if self._root:
            self._root.after(0, lambda: SettingsWindow(self._root))

    def quit_app(self):
        if self._listener:
            try:
                self._listener.stop()
            except Exception:
                pass
        if self._hotkey_proc:
            try:
                self._hotkey_proc.terminate()
                self._hotkey_proc.wait(timeout=2)
            except Exception:
                try:
                    self._hotkey_proc.kill()
                except Exception:
                    pass
            self._hotkey_proc = None
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

    def _setup_macos_menu(self):
        """Create a tkinter menu bar on macOS to replace the pystray tray icon."""
        menubar = tk.Menu(self._root)
        app_menu = tk.Menu(menubar, name="apple", tearoff=0)
        app_menu.add_command(label="Settings…", command=self.open_settings)
        app_menu.add_separator()
        app_menu.add_command(label="Quit KPrompter", command=self.quit_app)
        menubar.add_cascade(menu=app_menu)
        self._root.config(menu=menubar)

    def _setup_macos_window(self, cfg):
        """Configure the root window as a visible status window on macOS.

        On macOS there is no tray icon, so the root window must remain
        visible for the user to interact with the app.
        """
        self._root.configure(bg="#0f1117")
        w, h = 420, 260
        sw = self._root.winfo_screenwidth()
        sh = self._root.winfo_screenheight()
        self._root.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")
        self._root.resizable(False, False)

        hotkey = cfg.get("hotkey", "ctrl+alt+g")
        provider = cfg.get("provider", "openrouter")
        model = cfg.get("model", "")

        tk.Label(
            self._root, text="K>", font=("Menlo", 36, "bold"),
            bg="#0f1117", fg="#4a90e2",
        ).pack(pady=(28, 4))

        tk.Label(
            self._root, text="KPrompter is running",
            font=("Menlo", 14), bg="#0f1117", fg="#e4e8f1",
        ).pack()

        tk.Label(
            self._root, text=f"Hotkey: {hotkey}",
            font=("Menlo", 12), bg="#0f1117", fg="#6b7a99",
        ).pack(pady=(12, 2))

        tk.Label(
            self._root, text=f"Provider: {provider}" + (f"  •  {model}" if model else ""),
            font=("Menlo", 11), bg="#0f1117", fg="#6b7a99",
        ).pack()

        btn_frame = tk.Frame(self._root, bg="#0f1117")
        btn_frame.pack(pady=(18, 0))
        tk.Button(
            btn_frame, text="Settings", command=self.open_settings,
            bg="#1c2030", fg="#e4e8f1", activebackground="#222738",
            activeforeground="#e4e8f1", relief="flat", bd=0,
            padx=16, pady=6, cursor="hand2", font=("Menlo", 11),
        ).pack(side="left", padx=6)
        tk.Button(
            btn_frame, text="Quit", command=self.quit_app,
            bg="#1c2030", fg="#e4e8f1", activebackground="#222738",
            activeforeground="#e4e8f1", relief="flat", bd=0,
            padx=16, pady=6, cursor="hand2", font=("Menlo", 11),
        ).pack(side="left", padx=6)

    def run(self):
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
            self._setup_macos_window(cfg)
            self._root.deiconify()
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
