import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import platform
import webbrowser
import threading
from config import (
    load_config, save_config, get_system_prompt, save_custom_prompt,
    reset_prompt_to_default, load_log, clear_log, is_first_run,
    PROVIDERS, CONFIG_DIR
)

SYSTEM = platform.system()

# ── Colors ────────────────────────────────────────────────────────────────────
BG       = "#0d0f13"
BG2      = "#13161c"
BG3      = "#1a1e27"
BORDER   = "#2a2f3d"
ACCENT   = "#4af0a0"      # terminal green
ACCENT2  = "#3dd8f0"      # cyan for secondary
TEXT     = "#e8eaf0"
TEXT_DIM = "#6b7280"
RED      = "#f05a5a"
FONT_MONO = ("JetBrains Mono", 11) if SYSTEM != "Windows" else ("Consolas", 11)
FONT_UI   = ("SF Pro Text", 11) if SYSTEM == "Darwin" else ("Segoe UI", 11) if SYSTEM == "Windows" else ("Ubuntu", 11)
FONT_BIG  = ("SF Pro Display", 18, "bold") if SYSTEM == "Darwin" else ("Segoe UI", 18, "bold")


def _style_root(root: tk.Tk, title: str, w: int, h: int, resizable=False):
    root.title(title)
    root.configure(bg=BG)
    root.resizable(resizable, resizable)
    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    x = (sw - w) // 2
    y = (sh - h) // 2
    root.geometry(f"{w}x{h}+{x}+{y}")
    if SYSTEM == "Darwin":
        root.tk.call("::tk::unsupported::MacWindowStyle", "style", root, "documentProc", "closeBox")


def _btn(parent, text, command, accent=True, **kw):
    fg = BG if accent else TEXT
    bg = ACCENT if accent else BG3
    hover = "#2dd880" if accent else BG2
    b = tk.Button(
        parent, text=text, command=command,
        bg=bg, fg=fg, activebackground=hover, activeforeground=fg,
        font=(*FONT_UI[:2], "bold") if accent else FONT_UI,
        relief="flat", bd=0, padx=14, pady=7, cursor="hand2", **kw
    )
    b.bind("<Enter>", lambda e: b.configure(bg=hover))
    b.bind("<Leave>", lambda e: b.configure(bg=bg))
    return b


def _entry(parent, textvariable=None, show=None, width=38):
    e = tk.Entry(
        parent, textvariable=textvariable, show=show,
        bg=BG3, fg=TEXT, insertbackground=ACCENT,
        relief="flat", bd=0, font=FONT_MONO,
        width=width, highlightthickness=1,
        highlightbackground=BORDER, highlightcolor=ACCENT,
    )
    return e


def _label(parent, text, dim=False, big=False, **kw):
    font = FONT_BIG if big else FONT_UI
    return tk.Label(
        parent, text=text,
        bg=BG, fg=TEXT_DIM if dim else TEXT,
        font=font, **kw
    )


def _divider(parent):
    return tk.Frame(parent, bg=BORDER, height=1)


# ══════════════════════════════════════════════════════════════════════════════
# SETUP WIZARD
# ══════════════════════════════════════════════════════════════════════════════

class SetupWizard:
    def __init__(self):
        self.root = tk.Tk()
        _style_root(self.root, "KPrompter — Setup", 560, 620)
        self.cfg = load_config()
        self.step = 0
        self.steps = [
            self._step_welcome,
            self._step_provider,
            self._step_apikey,
            self._step_hotkey,
            self._step_done,
        ]
        self._provider_var = tk.StringVar(value=self.cfg.get("provider", "openrouter"))
        self._key_var = tk.StringVar(value=self.cfg.get("api_key", ""))
        self._hotkey_var = tk.StringVar(value=self.cfg.get("hotkey", "ctrl+alt+g"))
        self._recording = False

        self.container = tk.Frame(self.root, bg=BG)
        self.container.pack(fill="both", expand=True, padx=32, pady=28)
        self._render()

    def _clear(self):
        for w in self.container.winfo_children():
            w.destroy()

    def _header(self, step_n, total, title, subtitle=None):
        # Step indicator
        ind = tk.Frame(self.container, bg=BG)
        ind.pack(anchor="w")
        for i in range(total):
            color = ACCENT if i == step_n else BORDER
            dot = tk.Frame(ind, bg=color, width=24 if i == step_n else 8, height=4)
            dot.pack(side="left", padx=2)

        tk.Frame(self.container, bg=BG, height=20).pack()
        _label(self.container, title, big=True).pack(anchor="w")
        if subtitle:
            tk.Frame(self.container, bg=BG, height=6).pack()
            _label(self.container, subtitle, dim=True).pack(anchor="w")
        tk.Frame(self.container, bg=BG, height=18).pack()
        _divider(self.container).pack(fill="x")
        tk.Frame(self.container, bg=BG, height=18).pack()

    def _nav(self, back=True, next_text="Continue →", next_cmd=None):
        row = tk.Frame(self.container, bg=BG)
        row.pack(side="bottom", fill="x", pady=(16, 0))
        if back and self.step > 0:
            _btn(row, "← Back", self._back, accent=False).pack(side="left")
        _btn(row, next_text, next_cmd or self._next).pack(side="right")

    def _next(self):
        self.step += 1
        self._render()

    def _back(self):
        self.step -= 1
        self._render()

    def _render(self):
        self._clear()
        self.steps[self.step]()

    # ── Step 0: Welcome ───────────────────────────────────────────────────────
    def _step_welcome(self):
        self._header(0, len(self.steps), "Welcome to KPrompter",
                     "Turn rough text into AI-ready prompts — instantly.")
        lines = [
            ("Select text anywhere", "Press your hotkey"),
            ("KPrompter optimizes it", "Paste it back automatically"),
        ]
        for a, b in lines:
            row = tk.Frame(self.container, bg=BG2, pady=12, padx=14)
            row.pack(fill="x", pady=5)
            row.configure(highlightthickness=1, highlightbackground=BORDER)
            tk.Label(row, text=f"  {a}", bg=BG2, fg=ACCENT, font=(*FONT_MONO[:2], "bold")).pack(side="left")
            tk.Label(row, text=f"→  {b}", bg=BG2, fg=TEXT_DIM, font=FONT_UI).pack(side="right", padx=8)
        tk.Frame(self.container, bg=BG, height=10).pack()
        _label(self.container,
               "This setup takes ~2 minutes. You can change everything later from the tray.",
               dim=True).pack(anchor="w")
        self._nav(back=False)

    # ── Step 1: Provider ──────────────────────────────────────────────────────
    def _step_provider(self):
        self._header(1, len(self.steps), "Choose a Provider",
                     "OpenRouter is recommended — it has free models and easy billing limits.")
        for key, info in PROVIDERS.items():
            is_free = bool(info.get("free_models"))
            badge = "  FREE" if is_free else "  PAID"
            badge_color = ACCENT if is_free else RED
            row = tk.Frame(self.container, bg=BG2, pady=10, padx=12, cursor="hand2")
            row.configure(highlightthickness=1, highlightbackground=BORDER)
            row.pack(fill="x", pady=4)

            rb = tk.Radiobutton(
                row, variable=self._provider_var, value=key,
                bg=BG2, activebackground=BG2,
                selectcolor=BG3, fg=TEXT,
                font=(*FONT_UI[:2], "bold"),
                text=info["name"],
                relief="flat", bd=0,
            )
            rb.pack(side="left")
            tk.Label(row, text=badge, bg=BG2, fg=badge_color,
                     font=(*FONT_MONO[:2], "bold", "italic")).pack(side="left")
            tk.Label(row, text=info["setup_tip"][:60] + "…" if len(info["setup_tip"]) > 60 else info["setup_tip"],
                     bg=BG2, fg=TEXT_DIM, font=(*FONT_UI[:1], 9)).pack(side="right", padx=6)

            # clicking anywhere on row selects it
            for widget in (row,):
                widget.bind("<Button-1>", lambda e, k=key: self._provider_var.set(k))

        self._nav()

    # ── Step 2: API Key ───────────────────────────────────────────────────────
    def _step_apikey(self):
        provider = self._provider_var.get()
        info = PROVIDERS[provider]
        self._header(2, len(self.steps), f"API Key — {info['name']}",
                     info["setup_tip"])

        if provider == "ollama":
            _label(self.container, "No API key needed for Ollama.").pack(anchor="w")
            _label(self.container, "Make sure Ollama is running: ollama serve", dim=True).pack(anchor="w")
            _btn(self.container, "Download Ollama →",
                 lambda: webbrowser.open(info["key_url"]), accent=False).pack(anchor="w", pady=10)
        else:
            _label(self.container, "Paste your API key below:").pack(anchor="w")
            tk.Frame(self.container, bg=BG, height=8).pack()
            key_entry = _entry(self.container, textvariable=self._key_var, show="•", width=46)
            key_entry.pack(fill="x")
            tk.Frame(self.container, bg=BG, height=12).pack()

            row = tk.Frame(self.container, bg=BG)
            row.pack(anchor="w")
            _btn(row, "Get API Key →",
                 lambda: webbrowser.open(info["key_url"]), accent=False).pack(side="left")

            if provider == "openrouter":
                _btn(row, "Set $0 Limit →",
                     lambda: webbrowser.open("https://openrouter.ai/credits"), accent=False).pack(side="left", padx=8)

            tk.Frame(self.container, bg=BG, height=12).pack()
            warn = tk.Frame(self.container, bg="#1a1008", pady=8, padx=10)
            warn.configure(highlightthickness=1, highlightbackground="#4a3000")
            warn.pack(fill="x")
            tk.Label(warn, text="  Set a spending or credit limit before using paid models.",
                     bg="#1a1008", fg="#f0a030", font=FONT_UI).pack(anchor="w")

        self._nav()

    # ── Step 3: Hotkey ────────────────────────────────────────────────────────
    def _step_hotkey(self):
        self._header(3, len(self.steps), "Set Your Hotkey",
                     "This hotkey grabs your selected text and runs KPrompter.")
        rec_frame = tk.Frame(self.container, bg=BG2, pady=20)
        rec_frame.configure(highlightthickness=1, highlightbackground=BORDER)
        rec_frame.pack(fill="x")

        self._hotkey_display = tk.Label(
            rec_frame, text=self._hotkey_var.get(),
            bg=BG2, fg=ACCENT, font=(*FONT_MONO[:1], 22, "bold")
        )
        self._hotkey_display.pack()

        self._rec_status = tk.Label(rec_frame, text="Click 'Record' then press your combo",
                                    bg=BG2, fg=TEXT_DIM, font=FONT_UI)
        self._rec_status.pack()

        tk.Frame(self.container, bg=BG, height=12).pack()
        btn_row = tk.Frame(self.container, bg=BG)
        btn_row.pack()
        _btn(btn_row, "Record Hotkey", self._start_recording, accent=True).pack(side="left", padx=4)
        _btn(btn_row, "Reset Default", self._reset_hotkey, accent=False).pack(side="left", padx=4)

        tk.Frame(self.container, bg=BG, height=14).pack()
        rec = "Cmd+Option+G recommended on macOS" if SYSTEM == "Darwin" else "Ctrl+Alt+G recommended"
        _label(self.container, rec, dim=True).pack(anchor="w")

        self._nav()

    def _reset_hotkey(self):
        default = "ctrl+cmd+g" if SYSTEM == "Darwin" else "ctrl+alt+g"
        self._hotkey_var.set(default)
        self._hotkey_display.configure(text=default)

    def _start_recording(self):
        if self._recording:
            return
        self._recording = True
        self._pressed = set()
        self._rec_status.configure(text="Listening… press your combo now", fg=ACCENT)
        self.root.bind("<KeyPress>", self._on_key_press)
        self.root.bind("<KeyRelease>", self._on_key_release)
        self.root.focus_force()

    def _on_key_press(self, e):
        if not self._recording:
            return
        self._pressed.add(e.keysym.lower())
        combo = "+".join(sorted(self._pressed))
        self._hotkey_display.configure(text=combo)

    def _on_key_release(self, e):
        if not self._recording:
            return
        if len(self._pressed) >= 2:
            combo = "+".join(sorted(self._pressed))
            self._hotkey_var.set(combo)
            self._rec_status.configure(text="Hotkey saved.", fg=ACCENT2)
            self._recording = False
            self.root.unbind("<KeyPress>")
            self.root.unbind("<KeyRelease>")
        self._pressed.discard(e.keysym.lower())

    # ── Step 4: Done ─────────────────────────────────────────────────────────
    def _step_done(self):
        provider = self._provider_var.get()
        self._save()
        self._header(4, len(self.steps), "You're all set.", "KPrompter is ready to go.")

        lines = [
            ("Provider", PROVIDERS[provider]["name"]),
            ("Model", self.cfg.get("model", PROVIDERS[provider]["default_model"])),
            ("Hotkey", self._hotkey_var.get()),
        ]
        for label, val in lines:
            row = tk.Frame(self.container, bg=BG2, pady=8, padx=12)
            row.configure(highlightthickness=1, highlightbackground=BORDER)
            row.pack(fill="x", pady=3)
            tk.Label(row, text=label, bg=BG2, fg=TEXT_DIM, font=FONT_UI, width=10, anchor="w").pack(side="left")
            tk.Label(row, text=val, bg=BG2, fg=ACCENT, font=(*FONT_MONO[:2], "bold")).pack(side="left")

        tk.Frame(self.container, bg=BG, height=16).pack()
        _label(self.container, "KPrompter runs in the system tray. Right-click the icon for settings.", dim=True).pack(anchor="w")

        row = tk.Frame(self.container, bg=BG)
        row.pack(side="bottom", fill="x", pady=(16, 0))
        _btn(row, "← Back", self._back, accent=False).pack(side="left")
        _btn(row, "Launch KPrompter", self.root.destroy, accent=True).pack(side="right")

    def _save(self):
        cfg = load_config()
        cfg["provider"] = self._provider_var.get()
        cfg["api_key"] = self._key_var.get()
        cfg["hotkey"] = self._hotkey_var.get()
        provider = cfg["provider"]
        if not cfg.get("model"):
            cfg["model"] = PROVIDERS[provider]["default_model"]
        save_config(cfg)
        self.cfg = cfg

    def run(self):
        self.root.mainloop()


# ══════════════════════════════════════════════════════════════════════════════
# POPUP — shows questions or result
# ══════════════════════════════════════════════════════════════════════════════

class ResultPopup:
    """Shows the optimized prompt (or clarifying questions) with copy/paste/dismiss."""

    def __init__(self, text: str, is_question: bool = False, on_answer=None, original_text: str = ""):
        self.root = tk.Toplevel()
        _style_root(self.root, "KPrompter", 620, 440 if is_question else 380, resizable=True)
        self.root.lift()
        self.root.attributes("-topmost", True)
        self.on_answer = on_answer
        self.original_text = original_text
        self._build(text, is_question)

    def _build(self, text: str, is_question: bool):
        root = self.root
        root.configure(bg=BG)

        # Header bar
        header = tk.Frame(root, bg=BG2, pady=8, padx=14)
        header.configure(highlightthickness=0)
        header.pack(fill="x")

        tag_text = "  Clarification Needed" if is_question else "  Prompt Optimized"
        tag_color = ACCENT2 if is_question else ACCENT
        tk.Label(header, text="K>", bg=BG2, fg=ACCENT,
                 font=(*FONT_MONO[:1], 13, "bold")).pack(side="left")
        tk.Label(header, text=tag_text, bg=BG2, fg=tag_color,
                 font=(*FONT_UI[:2], "bold")).pack(side="left", padx=8)
        tk.Button(header, text="✕", command=root.destroy, bg=BG2, fg=TEXT_DIM,
                  activebackground=BG2, activeforeground=RED,
                  relief="flat", bd=0, font=FONT_UI, cursor="hand2").pack(side="right")

        # Body
        body = tk.Frame(root, bg=BG, padx=16, pady=12)
        body.pack(fill="both", expand=True)

        st = scrolledtext.ScrolledText(
            body, bg=BG3, fg=TEXT, font=FONT_MONO,
            relief="flat", bd=0, wrap="word",
            insertbackground=ACCENT,
            selectbackground=ACCENT, selectforeground=BG,
            highlightthickness=1, highlightbackground=BORDER,
            padx=10, pady=10,
        )
        st.insert("1.0", text)
        st.configure(state="disabled" if not is_question else "normal")
        st.pack(fill="both", expand=True)
        self._st = st

        # Answer box (only for questions)
        if is_question:
            tk.Frame(body, bg=BG, height=8).pack()
            _label(body, "Your answer:").pack(anchor="w")
            tk.Frame(body, bg=BG, height=4).pack()
            self._answer_box = tk.Text(
                body, bg=BG3, fg=TEXT, font=FONT_MONO, height=3,
                relief="flat", bd=0, insertbackground=ACCENT,
                highlightthickness=1, highlightbackground=BORDER,
                padx=8, pady=6,
            )
            self._answer_box.pack(fill="x")

        # Footer
        footer = tk.Frame(root, bg=BG2, padx=14, pady=8)
        footer.pack(fill="x")

        if is_question:
            _btn(footer, "Send Answer →", self._send_answer).pack(side="right")
            _btn(footer, "Cancel", root.destroy, accent=False).pack(side="right", padx=6)
        else:
            _btn(footer, "Dismiss", root.destroy, accent=False).pack(side="right")
            _btn(footer, "Copy", self._copy, accent=False).pack(side="right", padx=6)

    def _copy(self):
        text = self._st.get("1.0", "end").strip()
        self.root.clipboard_clear()
        self.root.clipboard_append(text)

    def _send_answer(self):
        answer = self._answer_box.get("1.0", "end").strip()
        if self.on_answer and answer:
            self.root.destroy()
            self.on_answer(answer)


# ══════════════════════════════════════════════════════════════════════════════
# SETTINGS WINDOW
# ══════════════════════════════════════════════════════════════════════════════

class SettingsWindow:
    def __init__(self):
        self.root = tk.Toplevel()
        _style_root(self.root, "KPrompter — Settings", 640, 580, resizable=True)
        self.root.lift()
        self.root.attributes("-topmost", True)
        self.cfg = load_config()
        self._build()

    def _build(self):
        root = self.root

        nb = ttk.Notebook(root)
        nb.pack(fill="both", expand=True, padx=0, pady=0)

        style = ttk.Style()
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", background=BG2, foreground=TEXT_DIM,
                        font=FONT_UI, padding=[12, 6])
        style.map("TNotebook.Tab", background=[("selected", BG)],
                  foreground=[("selected", ACCENT)])

        self._tab_general(nb)
        self._tab_provider(nb)
        self._tab_prompt(nb)
        self._tab_log(nb)

    def _frame(self, nb, title):
        f = tk.Frame(nb, bg=BG)
        nb.add(f, text=f"  {title}  ")
        return f

    # ── General tab ───────────────────────────────────────────────────────────
    def _tab_general(self, nb):
        f = self._frame(nb, "General")
        pad = tk.Frame(f, bg=BG, padx=20, pady=20)
        pad.pack(fill="both", expand=True)

        _label(pad, "Hotkey").pack(anchor="w")
        tk.Frame(pad, bg=BG, height=6).pack()
        hk_var = tk.StringVar(value=self.cfg.get("hotkey", "ctrl+alt+g"))
        hk_entry = _entry(pad, textvariable=hk_var)
        hk_entry.pack(anchor="w")
        tk.Frame(pad, bg=BG, height=16).pack()

        log_var = tk.BooleanVar(value=self.cfg.get("logging_enabled", True))
        tk.Checkbutton(pad, text="Enable session logging", variable=log_var,
                       bg=BG, fg=TEXT, selectcolor=BG3, activebackground=BG,
                       activeforeground=TEXT, font=FONT_UI).pack(anchor="w")
        tk.Frame(pad, bg=BG, height=8).pack()

        _label(pad, "Max log entries").pack(anchor="w")
        log_n_var = tk.StringVar(value=str(self.cfg.get("log_max_entries", 100)))
        _entry(pad, textvariable=log_n_var, width=10).pack(anchor="w")
        tk.Frame(pad, bg=BG, height=20).pack()

        def save():
            self.cfg["hotkey"] = hk_var.get()
            self.cfg["logging_enabled"] = log_var.get()
            try:
                self.cfg["log_max_entries"] = int(log_n_var.get())
            except ValueError:
                pass
            save_config(self.cfg)
            messagebox.showinfo("KPrompter", "Settings saved. Restart to apply hotkey changes.")

        _btn(pad, "Save", save).pack(anchor="w")

    # ── Provider tab ─────────────────────────────────────────────────────────
    def _tab_provider(self, nb):
        f = self._frame(nb, "Provider")
        pad = tk.Frame(f, bg=BG, padx=20, pady=20)
        pad.pack(fill="both", expand=True)

        prov_var = tk.StringVar(value=self.cfg.get("provider", "openrouter"))
        _label(pad, "Provider").pack(anchor="w")
        tk.Frame(pad, bg=BG, height=6).pack()

        opt = ttk.Combobox(pad, textvariable=prov_var,
                           values=list(PROVIDERS.keys()), state="readonly", width=30)
        style = ttk.Style()
        style.configure("TCombobox", fieldbackground=BG3, background=BG3,
                        foreground=TEXT, selectbackground=ACCENT)
        opt.pack(anchor="w")
        tk.Frame(pad, bg=BG, height=14).pack()

        _label(pad, "API Key").pack(anchor="w")
        tk.Frame(pad, bg=BG, height=6).pack()
        key_var = tk.StringVar(value=self.cfg.get("api_key", ""))
        key_entry = _entry(pad, textvariable=key_var, show="•", width=46)
        key_entry.pack(anchor="w")
        tk.Frame(pad, bg=BG, height=14).pack()

        _label(pad, "Model").pack(anchor="w")
        tk.Frame(pad, bg=BG, height=6).pack()
        model_var = tk.StringVar(value=self.cfg.get("model", ""))
        model_entry = _entry(pad, textvariable=model_var, width=46)
        model_entry.pack(anchor="w")
        tk.Frame(pad, bg=BG, height=6).pack()

        def fill_default_model():
            p = prov_var.get()
            model_var.set(PROVIDERS[p]["default_model"])

        _btn(pad, "Fill Default Model", fill_default_model, accent=False).pack(anchor="w")
        tk.Frame(pad, bg=BG, height=16).pack()

        def save():
            self.cfg["provider"] = prov_var.get()
            self.cfg["api_key"] = key_var.get()
            self.cfg["model"] = model_var.get()
            save_config(self.cfg)
            messagebox.showinfo("KPrompter", "Provider settings saved.")

        _btn(pad, "Save", save).pack(anchor="w")

    # ── System Prompt tab ─────────────────────────────────────────────────────
    def _tab_prompt(self, nb):
        f = self._frame(nb, "System Prompt")
        pad = tk.Frame(f, bg=BG, padx=20, pady=16)
        pad.pack(fill="both", expand=True)

        _label(pad, "Edit the optimizer prompt. Reset to restore default.").pack(anchor="w")
        tk.Frame(pad, bg=BG, height=8).pack()

        st = scrolledtext.ScrolledText(
            pad, bg=BG3, fg=TEXT, font=(*FONT_MONO[:1], 10),
            relief="flat", bd=0, wrap="word",
            insertbackground=ACCENT,
            highlightthickness=1, highlightbackground=BORDER,
            padx=8, pady=8, height=16,
        )
        st.insert("1.0", get_system_prompt())
        st.pack(fill="both", expand=True)

        tk.Frame(pad, bg=BG, height=10).pack()
        btn_row = tk.Frame(pad, bg=BG)
        btn_row.pack(anchor="w")

        def save_prompt():
            save_custom_prompt(st.get("1.0", "end").strip())
            messagebox.showinfo("KPrompter", "System prompt saved.")

        def reset_prompt():
            if messagebox.askyesno("Reset", "Reset to default system prompt?"):
                reset_prompt_to_default()
                st.delete("1.0", "end")
                st.insert("1.0", get_system_prompt())

        _btn(btn_row, "Save Prompt", save_prompt).pack(side="left")
        _btn(btn_row, "Reset to Default", reset_prompt, accent=False).pack(side="left", padx=8)

    # ── Log tab ───────────────────────────────────────────────────────────────
    def _tab_log(self, nb):
        f = self._frame(nb, "Session Log")
        pad = tk.Frame(f, bg=BG, padx=20, pady=16)
        pad.pack(fill="both", expand=True)

        _label(pad, f"Log location: {CONFIG_DIR}", dim=True).pack(anchor="w")
        tk.Frame(pad, bg=BG, height=8).pack()

        st = scrolledtext.ScrolledText(
            pad, bg=BG3, fg=TEXT_DIM, font=(*FONT_MONO[:1], 10),
            relief="flat", bd=0, wrap="word",
            highlightthickness=1, highlightbackground=BORDER,
            padx=8, pady=8, height=16,
        )
        entries = load_log()
        if entries:
            import json as _json
            for e in reversed(entries[-50:]):
                ts = e.get("timestamp", "")[:19]
                provider = e.get("provider", "?")
                mode = e.get("mode", "?")
                ic = e.get("input_chars", 0)
                oc = e.get("output_chars", 0)
                st.insert("end", f"{ts}  [{provider}]  {mode}  {ic}→{oc} chars\n")
        else:
            st.insert("end", "No log entries yet.")
        st.configure(state="disabled")
        st.pack(fill="both", expand=True)

        tk.Frame(pad, bg=BG, height=10).pack()

        def do_clear():
            if messagebox.askyesno("Clear Log", "Delete all log entries?"):
                clear_log()
                st.configure(state="normal")
                st.delete("1.0", "end")
                st.insert("1.0", "Log cleared.")
                st.configure(state="disabled")

        _btn(pad, "Clear Log", do_clear, accent=False).pack(anchor="w")


# ══════════════════════════════════════════════════════════════════════════════
# Loading spinner popup
# ══════════════════════════════════════════════════════════════════════════════

class LoadingPopup:
    def __init__(self):
        self.root = tk.Toplevel()
        _style_root(self.root, "KPrompter", 260, 90)
        self.root.attributes("-topmost", True)
        self.root.overrideredirect(True)
        tk.Frame(self.root, bg=BG, height=10).pack()
        self._lbl = tk.Label(self.root, text="K>  Optimizing…", bg=BG, fg=ACCENT,
                             font=(*FONT_MONO[:1], 13, "bold"))
        self._lbl.pack()
        self._dots = 0
        self._tick()

    def _tick(self):
        dots = "." * (self._dots % 4)
        self._lbl.configure(text=f"K>  Optimizing{dots}")
        self._dots += 1
        self._after_id = self.root.after(350, self._tick)

    def close(self):
        try:
            self.root.after_cancel(self._after_id)
            self.root.destroy()
        except Exception:
            pass
