"""
KPrompter — main entry point
Hotkey → grab selection → optimize → paste back
"""
import threading
import platform
import tkinter as tk
import sys
import time

from config import load_config, is_first_run, save_config, PROVIDERS
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
        self._root = None  # hidden tk root for spawning Toplevels

    # ── Hotkey handler ────────────────────────────────────────────────────────

    def on_hotkey(self):
        if self._busy:
            return
        self._busy = True
        threading.Thread(target=self._run_flow, daemon=True).start()

    def _run_flow(self):
        try:
            text, original_cb = get_selected_text()
            if not text.strip():
                self._busy = False
                return

            cfg = load_config()

            # Ask first-message mode
            is_first = self._ask_first_message_mode()

            # Show loading spinner
            spinner = None
            if self._root:
                self._root.after(0, lambda: self._start_spinner())

            try:
                result = optimize(text, is_first_message=is_first,
                                  conversation_history=self._conversation if not is_first else None)
            except Exception as e:
                self._stop_spinner()
                self._show_error(str(e))
                self._busy = False
                return

            self._stop_spinner()

            # Detect if result is a question (heuristic: ends with '?')
            lines = result.strip().splitlines()
            last_line = lines[-1].strip() if lines else ""
            is_question = last_line.endswith("?") or result.count("?") >= 2

            if is_question:
                self._show_question_popup(result, text, original_cb, is_first)
            else:
                # Paste it back and add to conversation history
                paste_text(result, original_cb)
                self._conversation.append({"role": "user", "content": text})
                self._conversation.append({"role": "assistant", "content": result})

        finally:
            self._busy = False

    def _ask_first_message_mode(self) -> bool:
        cfg = load_config()
        if cfg.get("first_message_default", True):
            # Non-blocking dialog via tk
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
                win.geometry(f"360x140+{(sw-360)//2}+{(sh-140)//2}")

                tk.Label(win, text="Is this the first message in a new project?",
                         bg="#0d0f13", fg="#e8eaf0",
                         font=("Menlo", 11) if SYSTEM == "Darwin" else ("Consolas", 11),
                         wraplength=320).pack(pady=(18, 10))

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

                for text, cmd, bg in [("Yes — new project", yes, "#4af0a0"),
                                       ("No — continuing", no, "#1a1e27")]:
                    fg = "#0d0f13" if bg == "#4af0a0" else "#e8eaf0"
                    tk.Button(row, text=text, command=cmd,
                              bg=bg, fg=fg, relief="flat", bd=0,
                              padx=12, pady=6, cursor="hand2").pack(side="left", padx=6)

                win.protocol("WM_DELETE_WINDOW", yes)

            self._root.after(0, ask)
            done.wait(timeout=30)
            return result["value"]
        return True

    def _show_question_popup(self, questions: str, original_text: str,
                              original_cb: str, is_first: bool):
        def on_answer(answer: str):
            combined = f"{original_text}\n\n[Answers to clarifying questions]\n{answer}"
            threading.Thread(
                target=self._run_with_text, args=(combined, original_cb, is_first),
                daemon=True
            ).start()

        self._root.after(0, lambda: ResultPopup(
            questions, is_question=True,
            on_answer=on_answer, original_text=original_text
        ))

    def _run_with_text(self, text: str, original_cb: str, is_first: bool):
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

    # ── Spinner helpers ───────────────────────────────────────────────────────

    def _start_spinner(self):
        self._spinner = LoadingPopup()

    def _stop_spinner(self):
        if self._root and hasattr(self, "_spinner"):
            self._root.after(0, self._spinner.close)

    def _show_error(self, msg: str):
        def _show():
            import tkinter.messagebox as mb
            mb.showerror("KPrompter Error", msg)
        if self._root:
            self._root.after(0, _show)

    # ── Tray menu handlers ────────────────────────────────────────────────────

    def open_settings(self):
        if self._root:
            self._root.after(0, SettingsWindow)

    def open_log(self):
        if self._root:
            self._root.after(0, lambda: SettingsWindow())  # opens on Log tab TODO

    def quit_app(self):
        if self._tray:
            self._tray.stop()
        if self._root:
            self._root.after(0, self._root.quit)

    # ── Main run ──────────────────────────────────────────────────────────────

    def run(self):
        # Generate icon if missing
        gen_icon()

        # First run → setup wizard
        if is_first_run():
            wizard = SetupWizard()
            wizard.run()

        cfg = load_config()
        if not cfg.get("api_key") and cfg.get("provider") != "ollama":
            print("[KPrompter] Warning: No API key configured. Open Settings to add one.")

        # Hidden tk root (needed to spawn Toplevels from threads)
        self._root = tk.Tk()
        self._root.withdraw()
        self._root.title("KPrompter")

        # Register hotkey
        hotkey = cfg.get("hotkey", "ctrl+alt+g")
        try:
            import keyboard
            keyboard.add_hotkey(hotkey, self.on_hotkey, suppress=False)
            print(f"[KPrompter] Hotkey registered: {hotkey}")
        except Exception as e:
            print(f"[KPrompter] Hotkey error: {e}")

        # Build tray
        self._tray = build_tray(
            on_settings=self.open_settings,
            on_log=self.open_log,
            on_quit=self.quit_app,
        )
        if self._tray:
            threading.Thread(target=self._tray.run, daemon=True).start()
        else:
            print("[KPrompter] pystray not available — running without tray icon.")

        print("[KPrompter] Running. Press your hotkey on selected text.")
        self._root.mainloop()


if __name__ == "__main__":
    KPrompter().run()
