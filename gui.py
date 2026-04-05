import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import platform
import webbrowser
import threading
from config import (
    load_config, save_config, get_system_prompt, save_custom_prompt,
    reset_prompt_to_default, load_log, clear_log, is_first_run,
    PROVIDERS, CONFIG_DIR, get_best_model, get_model_labels,
)

SYSTEM = platform.system()

# ── Palette ───────────────────────────────────────────────────────────────────
BG       = "#0d0f13"
BG2      = "#13161c"
BG3      = "#1c2030"
BORDER   = "#2a2f3d"
ACCENT   = "#4af0a0"
ACCENT2  = "#3dd8f0"
TEXT     = "#e8eaf0"
TEXT_DIM = "#8892a4"
RED      = "#f05a5a"
YELLOW   = "#f0c040"

_is_mac = SYSTEM == "Darwin"
_is_win = SYSTEM == "Windows"
FONT_MONO = ("Menlo", 11)      if _is_mac else ("Consolas", 11)   if _is_win else ("DejaVu Sans Mono", 11)
FONT_UI   = ("SF Pro Text", 11) if _is_mac else ("Segoe UI", 11)   if _is_win else ("Ubuntu", 11)
FONT_BIG  = ("SF Pro Display", 20, "bold") if _is_mac else ("Segoe UI", 18, "bold")
FONT_MONO_SM = (FONT_MONO[0], 10)


def _center(win, w, h):
    win.update_idletasks()
    sw = win.winfo_screenwidth()
    sh = win.winfo_screenheight()
    win.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")


def _style_root(root, title, w, h, resizable=False):
    root.title(title)
    root.configure(bg=BG)
    root.resizable(resizable, resizable)
    _center(root, w, h)


def _btn(parent, text, command, accent=True, small=False, **kw):
    fg  = BG   if accent else TEXT
    bg  = ACCENT if accent else BG3
    hov = "#2dd880" if accent else "#222840"
    font = (*FONT_UI[:2], "bold") if accent else FONT_UI
    if small:
        font = (FONT_UI[0], 10)
    b = tk.Button(parent, text=text, command=command,
                  bg=bg, fg=fg, activebackground=hov, activeforeground=fg,
                  font=font, relief="flat", bd=0,
                  padx=10 if small else 14, pady=4 if small else 7,
                  cursor="hand2", **kw)
    b.bind("<Enter>", lambda e: b.configure(bg=hov))
    b.bind("<Leave>", lambda e: b.configure(bg=bg))
    return b


def _entry(parent, textvariable=None, show=None, width=38):
    return tk.Entry(parent, textvariable=textvariable, show=show,
                    bg=BG3, fg=TEXT, insertbackground=ACCENT,
                    relief="flat", bd=0, font=FONT_MONO, width=width,
                    highlightthickness=1, highlightbackground=BORDER,
                    highlightcolor=ACCENT)


def _label(parent, text, dim=False, big=False, color=None, **kw):
    fg = color or (TEXT_DIM if dim else TEXT)
    font = FONT_BIG if big else FONT_UI
    return tk.Label(parent, text=text, bg=BG, fg=fg, font=font, **kw)


def _divider(parent):
    return tk.Frame(parent, bg=BORDER, height=1)


def _card(parent, **kw):
    f = tk.Frame(parent, bg=BG2, highlightthickness=1,
                 highlightbackground=BORDER, **kw)
    return f


# ── Model Combobox helper ─────────────────────────────────────────────────────

def _model_combobox(parent, provider: str, model_var: tk.StringVar) -> ttk.Combobox:
    models = get_model_labels(provider)
    labels = []
    for label, mid, free in models:
        tag = "  [FREE]" if free else "  [PAID]"
        labels.append(f"{label}{tag}")

    style = ttk.Style()
    style.theme_use("default")
    style.configure("Model.TCombobox",
                    fieldbackground=BG3, background=BG3,
                    foreground=TEXT, selectbackground=ACCENT,
                    selectforeground=BG, arrowcolor=ACCENT,
                    borderwidth=0, relief="flat")
    style.map("Model.TCombobox",
              fieldbackground=[("readonly", BG3)],
              foreground=[("readonly", TEXT)],
              selectbackground=[("readonly", ACCENT)])

    cb = ttk.Combobox(parent, textvariable=model_var,
                      values=labels, state="readonly",
                      style="Model.TCombobox", width=42)

    # Pre-select current model or best free
    cfg_model = load_config().get("model", "")
    selected_idx = 0
    for i, (label, mid, free) in enumerate(models):
        if mid == cfg_model:
            selected_idx = i
            break
    if labels:
        cb.current(selected_idx)

    # Store mapping label→id on the widget for retrieval
    cb._model_map = {f"{label}{'  [FREE]' if free else '  [PAID]'}": mid
                     for label, mid, free in models}
    return cb


# ══════════════════════════════════════════════════════════════════════════════
# SETUP WIZARD
# ══════════════════════════════════════════════════════════════════════════════

class SetupWizard:
    def __init__(self):
        self.root = tk.Tk()
        _style_root(self.root, "KPrompter — Setup", 580, 580)
        self.cfg = load_config()
        self.step = 0
        self.steps = [self._step_welcome, self._step_provider,
                      self._step_apikey, self._step_model,
                      self._step_hotkey, self._step_done]
        self._provider_var = tk.StringVar(value=self.cfg.get("provider", "openrouter"))
        self._key_var      = tk.StringVar(value=self.cfg.get("api_key", ""))
        self._hotkey_var   = tk.StringVar(value=self.cfg.get("hotkey", "ctrl+alt+g"))
        self._model_var    = tk.StringVar(value=self.cfg.get("model", ""))
        self._model_cb     = None
        self._recording    = False
        self._pressed      = set()

        self._provider_var.trace_add("write", self._on_provider_change)

        self.container = tk.Frame(self.root, bg=BG)
        self.container.pack(fill="both", expand=True, padx=32, pady=24)
        self._render()

    def _on_provider_change(self, *_):
        p = self._provider_var.get()
        best = get_best_model(p)
        self._model_var.set(best)

    def _clear(self):
        for w in self.container.winfo_children():
            w.destroy()

    def _header(self, step_n, title, subtitle=None):
        total = len(self.steps)
        ind = tk.Frame(self.container, bg=BG)
        ind.pack(anchor="w")
        for i in range(total):
            c = ACCENT if i == step_n else BORDER
            w = 28 if i == step_n else 8
            tk.Frame(ind, bg=c, width=w, height=4).pack(side="left", padx=2)

        tk.Frame(self.container, bg=BG, height=18).pack()
        _label(self.container, title, big=True).pack(anchor="w")
        if subtitle:
            tk.Frame(self.container, bg=BG, height=5).pack()
            _label(self.container, subtitle, dim=True).pack(anchor="w")
        tk.Frame(self.container, bg=BG, height=16).pack()
        _divider(self.container).pack(fill="x")
        tk.Frame(self.container, bg=BG, height=14).pack()

    def _nav(self, back=True, next_text="Continue →", next_cmd=None):
        row = tk.Frame(self.container, bg=BG)
        row.pack(side="bottom", fill="x", pady=(12, 0))
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
        self._header(0, "Welcome to KPrompter",
                     "Turn rough text into AI-ready prompts — one hotkey, any app.")
        for a, b in [("Select text anywhere", "Press your hotkey"),
                     ("KPrompter optimizes it", "Pastes it back automatically")]:
            row = _card(self.container, pady=12, padx=14)
            row.pack(fill="x", pady=5)
            tk.Label(row, text=f"  {a}", bg=BG2, fg=ACCENT,
                     font=(*FONT_MONO[:2], "bold")).pack(side="left")
            tk.Label(row, text=f"→  {b}", bg=BG2, fg=TEXT_DIM,
                     font=FONT_UI).pack(side="right", padx=8)
        tk.Frame(self.container, bg=BG, height=10).pack()
        _label(self.container, "Setup takes ~2 minutes. You can change everything later from the tray.",
               dim=True).pack(anchor="w")
        self._nav(back=False)

    # ── Step 1: Provider ──────────────────────────────────────────────────────
    def _step_provider(self):
        self._header(1, "Choose a Provider",
                     "OpenRouter is recommended — free models, easy billing limits.")
        for key, info in PROVIDERS.items():
            has_free = any(m["free"] for m in info.get("models", []))
            badge = "FREE" if has_free else "PAID"
            badge_color = ACCENT if has_free else YELLOW

            row = _card(self.container, pady=9, padx=12)
            row.pack(fill="x", pady=4)
            row.configure(cursor="hand2")

            rb = tk.Radiobutton(row, variable=self._provider_var, value=key,
                                bg=BG2, activebackground=BG2,
                                selectcolor=BG3, fg=TEXT,
                                font=(*FONT_UI[:2], "bold"),
                                text=info["name"], relief="flat", bd=0)
            rb.pack(side="left")
            tk.Label(row, text=f"  [{badge}]", bg=BG2, fg=badge_color,
                     font=(*FONT_MONO_SM, "bold")).pack(side="left")
            tip = info["setup_tip"][:55] + "…" if len(info["setup_tip"]) > 55 else info["setup_tip"]
            tk.Label(row, text=tip, bg=BG2, fg=TEXT_DIM,
                     font=(FONT_UI[0], 9)).pack(side="right", padx=6)
            row.bind("<Button-1>", lambda e, k=key: self._provider_var.set(k))
        self._nav()

    # ── Step 2: API Key ───────────────────────────────────────────────────────
    def _step_apikey(self):
        provider = self._provider_var.get()
        info = PROVIDERS[provider]
        self._header(2, f"API Key — {info['name']}", info["setup_tip"])

        if provider == "ollama":
            _label(self.container, "No API key needed for Ollama.").pack(anchor="w")
            tk.Frame(self.container, bg=BG, height=6).pack()
            _label(self.container, "Make sure Ollama is running:  ollama serve", dim=True).pack(anchor="w")
            tk.Frame(self.container, bg=BG, height=10).pack()
            _btn(self.container, "Download Ollama →",
                 lambda: webbrowser.open(info["key_url"]), accent=False).pack(anchor="w")
        else:
            _label(self.container, "Paste your API key:").pack(anchor="w")
            tk.Frame(self.container, bg=BG, height=6).pack()
            key_entry = _entry(self.container, textvariable=self._key_var, show="•", width=48)
            key_entry.pack(fill="x")
            tk.Frame(self.container, bg=BG, height=10).pack()

            btn_row = tk.Frame(self.container, bg=BG)
            btn_row.pack(anchor="w")
            _btn(btn_row, "Get API Key →",
                 lambda: webbrowser.open(info["key_url"]), accent=False).pack(side="left")
            if provider == "openrouter":
                _btn(btn_row, "Set $0 Limit →",
                     lambda: webbrowser.open("https://openrouter.ai/credits"),
                     accent=False).pack(side="left", padx=8)

            tk.Frame(self.container, bg=BG, height=12).pack()
            warn = tk.Frame(self.container, bg="#1a140a",
                            highlightthickness=1, highlightbackground="#5a3a00",
                            pady=8, padx=10)
            warn.pack(fill="x")
            tk.Label(warn, text="  Set a spending or credit limit before using any paid model.",
                     bg="#1a140a", fg=YELLOW, font=FONT_UI).pack(anchor="w")
        self._nav()

    # ── Step 3: Model picker ──────────────────────────────────────────────────
    def _step_model(self):
        provider = self._provider_var.get()
        self._header(3, "Pick a Model",
                     "FREE models cost nothing. PAID models bill your account.")

        _label(self.container, "Model:").pack(anchor="w")
        tk.Frame(self.container, bg=BG, height=6).pack()

        self._model_cb = _model_combobox(self.container, provider, self._model_var)
        self._model_cb.pack(anchor="w", fill="x")

        tk.Frame(self.container, bg=BG, height=14).pack()

        # Best free recommendation card
        best = get_best_model(provider)
        rec = _card(self.container, pady=10, padx=12)
        rec.pack(fill="x")
        tk.Label(rec, text="  Recommended free pick:", bg=BG2, fg=TEXT_DIM,
                 font=FONT_UI).pack(side="left")
        tk.Label(rec, text=f"  {best}", bg=BG2, fg=ACCENT,
                 font=(*FONT_MONO[:2], "bold")).pack(side="left")

        tk.Frame(self.container, bg=BG, height=8).pack()

        def use_best():
            best_label = ""
            for label, mid, free in get_model_labels(provider):
                if mid == best:
                    tag = "  [FREE]" if free else "  [PAID]"
                    best_label = f"{label}{tag}"
                    break
            if best_label:
                self._model_var.set(best_label)
                self._model_cb.set(best_label)

        _btn(self.container, "Use Recommended", use_best, accent=False).pack(anchor="w")
        self._nav()

    # ── Step 4: Hotkey ────────────────────────────────────────────────────────
    def _step_hotkey(self):
        self._header(4, "Set Your Hotkey",
                     "Grabs selected text and runs KPrompter.")
        rec_frame = _card(self.container, pady=20)
        rec_frame.pack(fill="x")

        self._hotkey_display = tk.Label(rec_frame, text=self._hotkey_var.get(),
                                        bg=BG2, fg=ACCENT,
                                        font=(FONT_MONO[0], 22, "bold"))
        self._hotkey_display.pack()
        self._rec_status = tk.Label(rec_frame,
                                    text="Click 'Record' then press your combo",
                                    bg=BG2, fg=TEXT_DIM, font=FONT_UI)
        self._rec_status.pack()

        tk.Frame(self.container, bg=BG, height=12).pack()
        btn_row = tk.Frame(self.container, bg=BG)
        btn_row.pack()
        _btn(btn_row, "Record Hotkey", self._start_recording).pack(side="left", padx=4)
        _btn(btn_row, "Reset Default", self._reset_hotkey, accent=False).pack(side="left", padx=4)

        tk.Frame(self.container, bg=BG, height=12).pack()
        rec = "Cmd+Option+G recommended on macOS" if _is_mac else "Ctrl+Alt+G recommended"
        _label(self.container, rec, dim=True).pack(anchor="w")
        self._nav()

    def _reset_hotkey(self):
        d = "ctrl+cmd+g" if _is_mac else "ctrl+alt+g"
        self._hotkey_var.set(d)
        self._hotkey_display.configure(text=d)

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
        self._hotkey_display.configure(text="+".join(sorted(self._pressed)))

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

    # ── Step 5: Done ──────────────────────────────────────────────────────────
    def _step_done(self):
        self._save()
        self._header(5, "You're all set.", "KPrompter is ready to go.")

        cfg = load_config()
        provider = cfg.get("provider", "openrouter")
        for label, val in [
            ("Provider", PROVIDERS[provider]["name"]),
            ("Model",    cfg.get("model", "")),
            ("Hotkey",   cfg.get("hotkey", "")),
        ]:
            row = _card(self.container, pady=8, padx=12)
            row.pack(fill="x", pady=3)
            tk.Label(row, text=label, bg=BG2, fg=TEXT_DIM,
                     font=FONT_UI, width=10, anchor="w").pack(side="left")
            tk.Label(row, text=val, bg=BG2, fg=ACCENT,
                     font=(*FONT_MONO[:2], "bold")).pack(side="left")

        tk.Frame(self.container, bg=BG, height=14).pack()
        _label(self.container,
               "KPrompter runs in the system tray. Right-click the icon for settings.",
               dim=True).pack(anchor="w")

        row = tk.Frame(self.container, bg=BG)
        row.pack(side="bottom", fill="x", pady=(12, 0))
        _btn(row, "← Back", self._back, accent=False).pack(side="left")
        _btn(row, "Launch KPrompter", self.root.destroy).pack(side="right")

    def _save(self):
        # Resolve selected model label → model id
        model_id = self.cfg.get("model", "")
        if self._model_cb:
            selected_label = self._model_var.get()
            model_id = self._model_cb._model_map.get(selected_label, selected_label)

        provider = self._provider_var.get()
        if not model_id:
            model_id = get_best_model(provider)

        cfg = load_config()
        cfg["provider"] = provider
        cfg["api_key"]  = self._key_var.get()
        cfg["hotkey"]   = self._hotkey_var.get()
        cfg["model"]    = model_id
        save_config(cfg)
        self.cfg = cfg

    def run(self):
        self.root.mainloop()


# ══════════════════════════════════════════════════════════════════════════════
# RESULT / QUESTION POPUP
# ══════════════════════════════════════════════════════════════════════════════

class ResultPopup:
    def __init__(self, text, is_question=False, on_answer=None, original_text=""):
        self.root = tk.Toplevel()
        _style_root(self.root, "KPrompter", 640, 460 if is_question else 360, resizable=True)
        self.root.lift()
        self.root.attributes("-topmost", True)
        self.on_answer = on_answer
        self._build(text, is_question)

    def _build(self, text, is_question):
        root = self.root
        root.configure(bg=BG)

        # Header
        hdr = tk.Frame(root, bg=BG2, pady=8, padx=14)
        hdr.pack(fill="x")
        tag = "  Clarification Needed" if is_question else "  Prompt Optimized"
        tag_color = ACCENT2 if is_question else ACCENT
        tk.Label(hdr, text="K>", bg=BG2, fg=ACCENT,
                 font=(*FONT_MONO[:1], 13, "bold")).pack(side="left")
        tk.Label(hdr, text=tag, bg=BG2, fg=tag_color,
                 font=(*FONT_UI[:2], "bold")).pack(side="left", padx=8)
        tk.Button(hdr, text="✕", command=root.destroy, bg=BG2, fg=TEXT_DIM,
                  activebackground=BG2, activeforeground=RED,
                  relief="flat", bd=0, font=FONT_UI, cursor="hand2").pack(side="right")

        # Body
        body = tk.Frame(root, bg=BG, padx=14, pady=10)
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
        st.configure(state="normal" if is_question else "disabled")
        st.pack(fill="both", expand=True)
        self._st = st

        if is_question:
            tk.Frame(body, bg=BG, height=8).pack()
            tk.Label(body, text="Your answer:", bg=BG, fg=TEXT,
                     font=FONT_UI).pack(anchor="w")
            tk.Frame(body, bg=BG, height=4).pack()
            self._answer_box = tk.Text(
                body, bg=BG3, fg=TEXT, font=FONT_MONO, height=3,
                relief="flat", bd=0, insertbackground=ACCENT,
                highlightthickness=1, highlightbackground=BORDER,
                padx=8, pady=6,
            )
            self._answer_box.pack(fill="x")

        # Footer
        ftr = tk.Frame(root, bg=BG2, padx=14, pady=8)
        ftr.pack(fill="x")
        if is_question:
            _btn(ftr, "Send Answer →", self._send_answer).pack(side="right")
            _btn(ftr, "Cancel", root.destroy, accent=False).pack(side="right", padx=6)
        else:
            _btn(ftr, "Dismiss", root.destroy, accent=False).pack(side="right")
            _btn(ftr, "Copy", self._copy, accent=False).pack(side="right", padx=6)

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
        _style_root(self.root, "KPrompter — Settings", 660, 560, resizable=True)
        self.root.lift()
        self.root.attributes("-topmost", True)
        self.cfg = load_config()
        self._build()

    def _build(self):
        style = ttk.Style()
        style.theme_use("default")
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", background=BG2, foreground=TEXT_DIM,
                        font=FONT_UI, padding=[12, 6])
        style.map("TNotebook.Tab",
                  background=[("selected", BG)],
                  foreground=[("selected", ACCENT)])

        nb = ttk.Notebook(self.root)
        nb.pack(fill="both", expand=True)
        self._tab_general(nb)
        self._tab_provider(nb)
        self._tab_prompt(nb)
        self._tab_log(nb)

    def _pad(self, nb, title):
        f = tk.Frame(nb, bg=BG)
        nb.add(f, text=f"  {title}  ")
        pad = tk.Frame(f, bg=BG, padx=20, pady=18)
        pad.pack(fill="both", expand=True)
        return pad

    # ── General ───────────────────────────────────────────────────────────────
    def _tab_general(self, nb):
        pad = self._pad(nb, "General")
        _label(pad, "Hotkey").pack(anchor="w")
        tk.Frame(pad, bg=BG, height=5).pack()
        hk_var = tk.StringVar(value=self.cfg.get("hotkey", "ctrl+alt+g"))
        _entry(pad, textvariable=hk_var).pack(anchor="w")
        tk.Frame(pad, bg=BG, height=14).pack()

        log_var = tk.BooleanVar(value=self.cfg.get("logging_enabled", True))
        tk.Checkbutton(pad, text="Enable session logging", variable=log_var,
                       bg=BG, fg=TEXT, selectcolor=BG3,
                       activebackground=BG, activeforeground=TEXT,
                       font=FONT_UI).pack(anchor="w")
        tk.Frame(pad, bg=BG, height=8).pack()

        _label(pad, "Max log entries").pack(anchor="w")
        log_n_var = tk.StringVar(value=str(self.cfg.get("log_max_entries", 100)))
        _entry(pad, textvariable=log_n_var, width=10).pack(anchor="w")
        tk.Frame(pad, bg=BG, height=18).pack()

        def save():
            self.cfg["hotkey"] = hk_var.get()
            self.cfg["logging_enabled"] = log_var.get()
            try:
                self.cfg["log_max_entries"] = int(log_n_var.get())
            except ValueError:
                pass
            save_config(self.cfg)
            messagebox.showinfo("KPrompter", "Saved. Restart to apply hotkey changes.")
        _btn(pad, "Save", save).pack(anchor="w")

    # ── Provider ─────────────────────────────────────────────────────────────
    def _tab_provider(self, nb):
        pad = self._pad(nb, "Provider")
        prov_var = tk.StringVar(value=self.cfg.get("provider", "openrouter"))
        model_var = tk.StringVar(value=self.cfg.get("model", ""))
        _model_cb_ref = [None]

        _label(pad, "Provider").pack(anchor="w")
        tk.Frame(pad, bg=BG, height=5).pack()

        prov_opts = {k: v["name"] for k, v in PROVIDERS.items()}
        prov_frame = tk.Frame(pad, bg=BG)
        prov_frame.pack(anchor="w")
        for key, name in prov_opts.items():
            tk.Radiobutton(prov_frame, text=name, variable=prov_var, value=key,
                           bg=BG, fg=TEXT, selectcolor=BG3,
                           activebackground=BG, activeforeground=TEXT,
                           font=FONT_UI).pack(side="left", padx=6)

        tk.Frame(pad, bg=BG, height=12).pack()
        _label(pad, "API Key").pack(anchor="w")
        tk.Frame(pad, bg=BG, height=5).pack()
        key_var = tk.StringVar(value=self.cfg.get("api_key", ""))
        key_entry = _entry(pad, textvariable=key_var, show="•", width=48)
        key_entry.pack(anchor="w")

        tk.Frame(pad, bg=BG, height=12).pack()
        _label(pad, "Model").pack(anchor="w")
        tk.Frame(pad, bg=BG, height=5).pack()

        model_frame = tk.Frame(pad, bg=BG)
        model_frame.pack(anchor="w", fill="x")

        def refresh_model_cb(provider):
            for w in model_frame.winfo_children():
                w.destroy()
            cb = _model_combobox(model_frame, provider, model_var)
            cb.pack(anchor="w", fill="x")
            _model_cb_ref[0] = cb

        refresh_model_cb(prov_var.get())

        def on_prov_change(*_):
            p = prov_var.get()
            model_var.set(get_best_model(p))
            refresh_model_cb(p)
        prov_var.trace_add("write", on_prov_change)

        tk.Frame(pad, bg=BG, height=16).pack()

        def save():
            cb = _model_cb_ref[0]
            model_id = model_var.get()
            if cb and hasattr(cb, "_model_map"):
                model_id = cb._model_map.get(model_var.get(), model_var.get())
            self.cfg["provider"] = prov_var.get()
            self.cfg["api_key"]  = key_var.get()
            self.cfg["model"]    = model_id
            save_config(self.cfg)
            messagebox.showinfo("KPrompter", "Provider settings saved.")
        _btn(pad, "Save", save).pack(anchor="w")

    # ── System Prompt ─────────────────────────────────────────────────────────
    def _tab_prompt(self, nb):
        pad = self._pad(nb, "System Prompt")
        _label(pad, "Edit the optimizer prompt. Reset to restore the default.").pack(anchor="w")
        tk.Frame(pad, bg=BG, height=8).pack()

        st = scrolledtext.ScrolledText(
            pad, bg=BG3, fg=TEXT, font=FONT_MONO_SM,
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

        def save_p():
            save_custom_prompt(st.get("1.0", "end").strip())
            messagebox.showinfo("KPrompter", "System prompt saved.")

        def reset_p():
            if messagebox.askyesno("Reset", "Reset to default system prompt?"):
                reset_prompt_to_default()
                st.delete("1.0", "end")
                st.insert("1.0", get_system_prompt())

        _btn(btn_row, "Save Prompt", save_p).pack(side="left")
        _btn(btn_row, "Reset to Default", reset_p, accent=False).pack(side="left", padx=8)

    # ── Log ───────────────────────────────────────────────────────────────────
    def _tab_log(self, nb):
        pad = self._pad(nb, "Session Log")
        _label(pad, f"Location: {CONFIG_DIR}", dim=True).pack(anchor="w")
        tk.Frame(pad, bg=BG, height=8).pack()

        st = scrolledtext.ScrolledText(
            pad, bg=BG3, fg=TEXT_DIM, font=FONT_MONO_SM,
            relief="flat", bd=0, wrap="word",
            highlightthickness=1, highlightbackground=BORDER,
            padx=8, pady=8, height=14,
        )
        entries = load_log()
        if entries:
            for e in reversed(entries[-50:]):
                ts = e.get("timestamp", "")[:19]
                line = (f"{ts}  [{e.get('provider','?')}]  "
                        f"{e.get('mode','?')}  "
                        f"{e.get('input_chars',0)}→{e.get('output_chars',0)} chars\n")
                st.insert("end", line)
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
# LOADING SPINNER
# ══════════════════════════════════════════════════════════════════════════════

class LoadingPopup:
    def __init__(self):
        self.root = tk.Toplevel()
        _style_root(self.root, "KPrompter", 240, 80)
        self.root.attributes("-topmost", True)
        self.root.overrideredirect(True)
        self._lbl = tk.Label(self.root, text="K>  Optimizing",
                             bg=BG, fg=ACCENT,
                             font=(*FONT_MONO[:1], 13, "bold"))
        self._lbl.pack(expand=True)
        self._dots = 0
        self._tick()

    def _tick(self):
        self._lbl.configure(text=f"K>  Optimizing{'.' * (self._dots % 4)}")
        self._dots += 1
        self._id = self.root.after(350, self._tick)

    def close(self):
        try:
            self.root.after_cancel(self._id)
            self.root.destroy()
        except Exception:
            pass
