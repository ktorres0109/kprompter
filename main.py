"""
KPrompter — main entry point
Hotkey → grab selection → optimize → paste back
"""
import threading
import platform
import tkinter as tk
import sys
import time

from config import load_config, is_first_run, save_config, PROVIDERS, get_best_model
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
        self._current_hotkey_combo = set()
        self._listener = None

    # ── Hotkey via pynput ────────────────────────────────────────────────────

    def _parse_hotkey(self, hotkey_str: str):
        """Parse 'ctrl+alt+g' into a set of pynput key names."""
        from pynput import keyboard as kb
        parts = hotkey_str.lower().replace("cmd", "command").replace("meta", "command").split("+")
        keys = set()
        for p in parts:
            p = p.strip()
            if p in ("ctrl", "control"):
                keys.add(kb.Key.ctrl)
            elif p == "alt":
                keys.add(kb.Key.alt)
            elif p in ("command", "cmd"):
                keys.add(kb.Key.cmd)
            elif p == "shift":
                keys.add(kb.Key.shift)
            elif len(p) == 1:
                keys.add(kb.KeyCode.from_char(p))
        return keys

    def _start_hotkey_listener(self):
        from pynput import keyboard as kb
        cfg = load_config()
        hotkey_str = cfg.get("hotkey", "ctrl+alt+g")
        target_combo = self._parse_hotkey(hotkey_str)
        pressed = set()

        def on_press(key):
            pressed.add(key)
            # Normalize: compare by str representation for char keys
            pressed_norm = set()
            for k in pressed:
                pressed_norm.add(k)
            target_norm = target_combo

            # Check match
            if self._combo_matches(pressed, target_combo):
                if not self._busy:
                    threading.Thread(target=self._run_flow, daemon=True).start()

        def on_release(key):
            pressed.discard(key)

        self._listener = kb.Listener(on_press=on_press, on_release=on_release)
        self._listener.daemon = True
        self._listener.start()
        print(f"[KPrompter] Hotkey listening: {hotkey_str}")

    def _combo_matches(self, pressed: set, target: set) -> bool:
        from pynput import keyboard as kb
        # Normalize pressed keys to compare correctly
        def norm(k):
            if isinstance(k, kb.KeyCode):
                return kb.KeyCode.from_char(k.char.lower()) if k.char else k
            return k
        pressed_norm = {norm(k) for k in pressed}
        target_norm = {norm(k) for k in target}
        return target_norm.issubset(pressed_norm)

    # ── Main flow ─────────────────────────────────────────────────────────────

    def _run_flow(self):
        self._busy = True
        try:
            time.sleep(0.05)
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
                self._busy = False
                return

            self._stop_spinner()

            lines = result.strip().splitlines()
            last_line = lines[-1].strip() if lines else ""
            is_question = last_line.endswith("?") or result.count("?") >= 2

            if is_question:
                self._show_question_popup(result, text, original_cb, is_first)
            else:
                paste_text(result, original_cb)
                self._conversation.append({"role": "user", "content": text})
                self._conversation.append({"role": "assistant", "content": result})
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
            sw = win.winfo_screenwidth()
            sh = win.winfo_screenheight()
            win.geometry(f"380x150+{(sw-380)//2}+{(sh-150)//2}")

            tk.Label(
                win, text="Is this the first message in a new project?",
                bg="#0d0f13", fg="#e8eaf0",
                font=("Menlo", 12) if SYSTEM == "Darwin" else ("Consolas", 11),
                wraplength=340,
            ).pack(pady=(22, 12))

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
                              cursor="hand2", font=("Menlo", 11) if SYSTEM == "Darwin" else ("Consolas", 10))
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
            questions, is_question=True, on_answer=on_answer,
            original_text=original_text,
        ))

    def _run_with_text(self, text, original_cb, is_first):
        self._busy = True
        try:
            result = optimize(text, is_first_message=is_first,
                              conversation_history=self._conversation if not is_first else None)
            paste_text(result, original_cb)
            self._conversation.append({"role": "user", "content": text})
            self._conversation.append({"role": "assistant", "content": result})
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
        def _show():
            import tkinter.messagebox as mb
            mb.showerror("KPrompter Error", msg)
        if self._root:
            self._root.after(0, _show)

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

        if is_first_run():
            wizard = SetupWizard()
            wizard.run()

        cfg = load_config()
        if not cfg.get("api_key") and cfg.get("provider") != "ollama":
            print("[KPrompter] Warning: No API key set. Open Settings to add one.")

        self._root = tk.Tk()
        self._root.withdraw()
        self._root.title("KPrompter")

        self._start_hotkey_listener()

        self._tray = build_tray(
            on_settings=self.open_settings,
            on_log=self.open_settings,
            on_quit=self.quit_app,
        )
        if self._tray:
            threading.Thread(target=self._tray.run, daemon=True).start()
        else:
            print("[KPrompter] pystray not available — running without tray.")

        print("[KPrompter] Running.")
        self._root.mainloop()


if __name__ == "__main__":
    KPrompter().run()
