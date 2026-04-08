"""
KPrompter — main entry point
Hotkey → grab selection → optimize → paste back
"""
import threading
import platform
import tkinter as tk
import time

from config import load_config, is_first_run, PROVIDERS, get_best_model
from optimizer import optimize
from clipboard import get_selected_text, paste_text
from gui import SetupWizard, ResultPopup, SettingsWindow, LoadingPopup
from tray import build_tray
from icon_gen import generate as gen_icon

SYSTEM = platform.system()


class KPrompter:
    def __init__(self):
        self._busy = False
        self._conversation: list = []
        self._tray = None
        self._root = None
        self._spinner = None
        self._listener = None

    # ── Hotkey via pynput ────────────────────────────────────────────────────

    def _parse_hotkey(self, hotkey_str: str):
        """Parse 'ctrl+alt+g' into a frozenset of pynput keys."""
        from pynput import keyboard as kb
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

    def _start_hotkey_listener(self):
        from pynput import keyboard as kb
        cfg = load_config()
        hotkey_str = cfg.get("hotkey", "ctrl+alt+g")
        target = self._parse_hotkey(hotkey_str)
        pressed = set()

        def _normalize(key):
            """Collapse left/right variants and normalize char case."""
            # Collapse modifier variants (alt_l→alt, ctrl_l→ctrl, etc.)
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

        self._listener = kb.Listener(on_press=on_press, on_release=on_release)
        self._listener.daemon = True
        self._listener.start()
        print(f"[KPrompter] Listening for hotkey: {hotkey_str}")

    # ── Main flow ─────────────────────────────────────────────────────────────

    def _run_flow(self):
        self._busy = True
        try:
            time.sleep(0.08)  # small delay so key release doesn't interfere
            text, original_cb = get_selected_text()
            if not text.strip():
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
                # Efficiency: Cap history to last 6 messages (3 turns) to save tokens.
                # In "continuation" mode, LLMs rarely need more than the last few interactions
                # to understand the immediate context, drastically cutting API costs.
                if len(self._conversation) > 6:
                    self._conversation = self._conversation[-6:]
        finally:
            self._busy = False

    def _ask_first_message_mode(self) -> bool:
        result = {"value": True}
        done = threading.Event()

        def ask():
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

        self._root.after(0, lambda: ResultPopup(
            questions, is_question=True,
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
        self._spinner = LoadingPopup()

    def _stop_spinner(self):
        if self._root and self._spinner:
            self._root.after(0, self._spinner.close)
            self._spinner = None

    def _show_error(self, msg):
        import tkinter.messagebox as mb
        if self._root:
            self._root.after(0, lambda m=msg: mb.showerror("KPrompter Error", m))

    def open_settings(self):
        if self._root:
            self._root.after(0, SettingsWindow)

    def quit_app(self):
        if self._listener:
            self._listener.stop()
        if self._tray:
            self._tray.stop()
        if self._root:
            self._root.after(0, self._root.quit)

    def run(self):
        gen_icon()

        self._root = tk.Tk()
        self._root.withdraw()
        self._root.title("KPrompter")

        if is_first_run():
            wizard = SetupWizard(parent=self._root)
            self._root.wait_window(wizard.root)

        cfg = load_config()
        if not cfg.get("api_key") and cfg.get("provider") != "ollama":
            print("[KPrompter] Warning: No API key set. Open Settings to add one.")

        self._start_hotkey_listener()

        # macOS: Disable tray icon to prevent Tkinter thread conflicts that cause endless crashing loops
        if SYSTEM != "Darwin":
            self._tray = build_tray(
                on_settings=self.open_settings,
                on_log=self.open_settings,
                on_quit=self.quit_app,
            )
            if self._tray:
                threading.Thread(target=self._tray.run, daemon=True).start()
            else:
                print("[KPrompter] pystray not available — running without tray icon.")
        else:
            print("[KPrompter] Running on macOS — tray icon disabled to prevent Tkinter thread lock.")

        print("[KPrompter] Running.")
        self._root.mainloop()


if __name__ == "__main__":
    KPrompter().run()
