import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import platform
import subprocess
import webbrowser
import threading
import os
import re
from config import (
    load_config, save_config,
    load_log, clear_log, is_first_run,
    get_custom_instructions, save_custom_instructions,
    PROVIDERS, CONFIG_DIR, get_best_model, get_model_labels,
)

SYSTEM = platform.system()

# ── KPrompter Terminal Palette ──────────────────────────────────────────────
BG        = "#1c1c1e"     # systemBackground (macOS dark)
BG2       = "#2c2c2e"     # elevated surface
BG3       = "#3a3a3c"     # inputs / tertiary
BG_HOVER  = "#48484a"     # hover
BORDER    = "#48484a"     # borders
ACCENT    = "#4af0a0"     # terminal neon green (matches icon)
ACCENT_H  = "#3dd88e"     # accent hover
ACCENT2   = "#4af0a0"     # secondary green
BTN       = "#2e4a3e"     # green-tinted neutral button
BTN_H     = "#3a5f4e"     # green-tinted button hover
TAB_ACT   = "#2e4a3e"     # active tab (green tint)
TAB_ACTH  = "#3a5f4e"     # active tab hover
GREEN     = "#4af0a0"     # success green
GREEN_H   = "#3dd88e"
TEXT      = "#e8ffe8"     # slightly warm white with green tint
TEXT_DIM  = "#7a9e8a"     # muted green-grey
RED       = "#ff453a"     # macOS red
ORANGE    = "#ff9f0a"
YELLOW    = "#ffd60a"
HEADER_GRN = "#4af0a0"   # icon green
HEADER_CYN = "#4af0a0"   # was cyan — now same terminal green

_is_mac = SYSTEM == "Darwin"
_is_win = SYSTEM == "Windows"
FONT_MONO    = ("SF Mono", 10)      if _is_mac else ("Cascadia Code", 10)   if _is_win else ("JetBrains Mono", 10)
FONT_UI      = ("SF Pro Text", 10)  if _is_mac else ("Segoe UI", 10)        if _is_win else ("Inter", 10)
FONT_UI_SM   = (FONT_UI[0], 9)
FONT_UI_MED  = (FONT_UI[0], 11)
FONT_HEADING = (FONT_UI[0], 18, "bold")
FONT_SUB     = (FONT_UI[0], 12, "bold")
FONT_MONO_SM = (FONT_MONO[0], 10)
FONT_MONO_LG = (FONT_MONO[0], 12, "bold")

CARD_IPADY = 12
CARD_IPADX = 16


_MOD_ORDER = ["ctrl", "cmd", "alt", "shift"]

# macOS Option-key character substitutions (US QWERTY layout).
# When Option is held, pressing a letter produces a Unicode character instead
# of the letter itself.  tkinter's keysym reflects this (e.g. "copyright" for
# Option+G).  We normalise these back to the base ASCII key so that hotkey
# strings like "ctrl+alt+g" stay readable and parseable.
_MAC_OPT_CHARS: dict[str, str] = {
    # char → base key
    "©": "g", "®": "r", "ß": "s", "∂": "d", "ƒ": "f",
    "å": "a", "∫": "b", "ç": "c", "˙": "h", "∆": "j",
    "˚": "k", "¬": "l", "µ": "m", "ø": "o", "π": "p",
    "œ": "q", "†": "t", "√": "v", "∑": "w", "≈": "x",
    "¥": "y", "ω": "z", "Ω": "z",
    # tkinter keysym names for the same chars
    "copyright":  "g", "registered": "r", "ssharp": "s",
    "partialderivative": "d", "function": "f",
    "aring": "a", "integral": "b", "ccedilla": "c",
    "abovedot": "h", "greek_delta": "j",  "increment": "j",
    "ringabove": "k", "notsign": "l",
    "mu": "m", "oslash": "o", "greek_pi": "p", "pi": "p",
    "oe": "q", "dagger": "t", "radical": "v",
    "summation": "w", "approxeq": "x",
    "yen": "y", "greek_omega": "z", "omega": "z",
}


def _normalize_key(keysym: str, char: str) -> str:
    """Return the base key name, normalising macOS Option-key substitutions."""
    if _is_mac:
        k = _MAC_OPT_CHARS.get(keysym, _MAC_OPT_CHARS.get(char, keysym))
        return k
    return keysym


def _mod_order(mods: set) -> list:
    """Return modifier keys sorted in conventional order."""
    ordered = [m for m in _MOD_ORDER if m in mods]
    ordered += sorted(m for m in mods if m not in _MOD_ORDER)
    return ordered


def _alt_label() -> str:
    """On macOS 'alt' key is called 'option'."""
    return "option" if _is_mac else "alt"


def _hotkey_display(hotkey: str) -> str:
    """Normalise hotkey string for display: use 'option' on macOS."""
    if _is_mac:
        return hotkey.replace("alt", "option")
    return hotkey


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


def _btn(parent, text, command, accent=True, small=False, danger=False, **kw):
    """Create a styled button (using Label for cross-platform color control)."""
    if danger:
        bg, fg, hov = RED, "#ffffff", "#dc2626"
    else:
        bg, fg, hov = BTN, TEXT, BTN_H
    font = (*FONT_UI[:2], "bold")
    if small:
        font = FONT_UI_SM
    px = 10 if small else 18
    py = 4 if small else 8
    b = tk.Label(parent, text=text, bg=bg, fg=fg,
                 font=font,
                 padx=px, pady=py,
                 relief="flat", bd=0, **kw)
    b.bind("<Button-1>", lambda e: command())
    b.bind("<Enter>", lambda e: b.configure(bg=hov))
    b.bind("<Leave>", lambda e: b.configure(bg=bg))
    return b


def _entry(parent, textvariable=None, show=None, width=38):
    e = tk.Entry(parent, textvariable=textvariable, show=show,
                 bg=BG3, fg=TEXT, insertbackground=ACCENT,
                 relief="flat", bd=0, font=FONT_MONO, width=width,
                 highlightthickness=2, highlightbackground=BORDER,
                 highlightcolor=ACCENT)
    return e


def _label(parent, text, dim=False, big=False, color=None, bg_color=None, **kw):
    fg = color or (TEXT_DIM if dim else TEXT)
    font = FONT_HEADING if big else FONT_UI
    return tk.Label(parent, text=text, bg=bg_color or BG, fg=fg, font=font, **kw)


def _sublabel(parent, text, **kw):
    return tk.Label(parent, text=text, bg=BG, fg=TEXT_DIM, font=FONT_UI_SM, **kw)


def _divider(parent, color=None):
    return tk.Frame(parent, bg=color or BORDER, height=1)


def _card(parent, bg_color=None, **kw):
    f = tk.Frame(parent, bg=bg_color or BG2, highlightthickness=1,
                 highlightbackground=BORDER, **kw)
    return f


def _spacer(parent, h=12):
    return tk.Frame(parent, bg=BG, height=h)


def _badge(parent, text, color=GREEN, bg_color=BG2):
    return tk.Label(parent, text=text, bg=bg_color, fg=color,
                    font=(FONT_MONO[0], 9, "bold"),
                    padx=6, pady=1)


# ── Pill Button (canvas-drawn capsule, no cursor) ────────────────────────────
# NOTE: Window must be deiconified before any _PillBtn is created, because
# Canvas.create_* fails in withdrawn/unmapped windows (Python 3.14+).

class _PillBtn(tk.Canvas):
    """Capsule-shaped button drawn on Canvas — no custom cursor."""
    def __init__(self, parent, text, command=None,
                 bg=BTN, fg=TEXT, hover_bg=BTN_H,
                 fnt=None, padx=16, pady=6, parent_bg=None, **kw):
        from tkinter import font as tkfont
        _fnt = fnt or (*FONT_UI[:2], "bold")
        fm = tkfont.Font(family=_fnt[0], size=_fnt[1],
                         weight=_fnt[2] if len(_fnt) > 2 else "normal")
        tw = fm.measure(text)
        th = fm.metrics("linespace")
        w = tw + padx * 2
        h = th + pady * 2
        _pbg = parent_bg or BG2
        super().__init__(parent, width=w, height=h,
                         bg=_pbg, highlightthickness=0, **kw)
        self._bg  = bg
        self._hov = hover_bg
        self._fg  = fg
        self._txt = text
        self._fnt = _fnt
        self._cmd = command
        self._w2, self._h2 = w, h
        self._draw(bg)
        if command:
            self.bind("<Button-1>", lambda e: command())
        self.bind("<Enter>", lambda e: self._draw(self._hov))
        self.bind("<Leave>", lambda e: self._draw(self._bg))

    def _draw(self, fill):
        self.delete("all")
        r = self._h2 // 2
        w, h = self._w2, self._h2
        self.create_oval(0, 0, h, h, fill=fill, outline=fill)
        self.create_oval(w - h, 0, w, h, fill=fill, outline=fill)
        self.create_rectangle(r, 0, w - r, h, fill=fill, outline=fill)
        self.create_text(w // 2, h // 2, text=self._txt,
                         fill=self._fg, font=self._fnt)

    def set_state(self, active: bool, active_bg=TAB_ACT):
        self._bg  = active_bg if active else BTN
        self._hov = TAB_ACTH if active else BTN_H
        self._draw(self._bg)


# ── Model Combobox helper ─────────────────────────────────────────────────────

def _model_combobox(parent, provider: str, model_var: tk.StringVar) -> ttk.Combobox:
    models = get_model_labels(provider)
    labels = []
    for label, mid, free in models:
        tag = "  [FREE]" if free else "  [PAID]"
        labels.append(f"{label}{tag}")

    style = ttk.Style()
    # Only switch to "default" theme on non-macOS; on macOS the "aqua" theme
    # handles native widget rendering and overriding it breaks visuals.
    if not _is_mac:
        style.theme_use("default")
    style.configure("Model.TCombobox",
                    fieldbackground=BG3, background=BG3,
                    foreground=TEXT, selectbackground=ACCENT,
                    selectforeground="#ffffff", arrowcolor=ACCENT,
                    borderwidth=0, relief="flat")
    style.map("Model.TCombobox",
              fieldbackground=[("readonly", BG3)],
              foreground=[("readonly", TEXT)],
              selectbackground=[("readonly", ACCENT)])

    cb = ttk.Combobox(parent, textvariable=model_var,
                      values=labels, state="readonly",
                      style="Model.TCombobox", width=42)

    cfg_model = load_config().get("model", "")
    selected_idx = 0
    for i, (label, mid, free) in enumerate(models):
        if mid == cfg_model:
            selected_idx = i
            break
    if labels:
        cb.current(selected_idx)

    cb._model_map = {f"{label}{'  [FREE]' if free else '  [PAID]'}": mid
                     for label, mid, free in models}
    return cb


# ══════════════════════════════════════════════════════════════════════════════
# SETUP WIZARD
# ══════════════════════════════════════════════════════════════════════════════

class SetupWizard:
    def __init__(self, parent_root=None):
        self.parent_root = parent_root
        if self.parent_root:
            self.root = tk.Toplevel(self.parent_root)
        else:
            self.root = tk.Tk()
        _style_root(self.root, "KPrompter — Setup", 620, 600)
        self.cfg = load_config()
        self.step = 0
        self.steps = [self._step_welcome, self._step_provider,
                      self._step_apikey, self._step_model,
                      self._step_hotkey, self._step_done]
        self._provider_var = tk.StringVar(value=self.cfg.get("provider", "openrouter"))
        self._key_var      = tk.StringVar(value=self.cfg.get("api_key", ""))
        self._hotkey_var   = tk.StringVar(value=_hotkey_display(self.cfg.get("hotkey", "cmd+option+k" if _is_mac else "ctrl+alt+k")))
        self._model_var    = tk.StringVar(value=self.cfg.get("model", ""))
        self._model_cb     = None
        self._recording    = False
        self._pressed      = set()

        self._provider_var.trace_add("write", self._on_provider_change)

        self.container = tk.Frame(self.root, bg=BG)
        self.container.pack(fill="both", expand=True, padx=36, pady=28)
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

        # Progress bar
        prog_frame = tk.Frame(self.container, bg=BG)
        prog_frame.pack(fill="x", anchor="w")
        for i in range(total):
            is_current = i == step_n
            is_done = i < step_n
            if is_current:
                c, w = ACCENT, 36
            elif is_done:
                c, w = GREEN, 12
            else:
                c, w = BORDER, 12
            tk.Frame(prog_frame, bg=c, width=w, height=4).pack(side="left", padx=2, pady=2)

        _spacer(self.container, 20).pack()

        # Step number
        _sublabel(self.container,
                  f"STEP {step_n + 1} OF {total}").pack(anchor="w")
        _spacer(self.container, 4).pack()

        # Title
        _label(self.container, title, big=True).pack(anchor="w")
        if subtitle:
            _spacer(self.container, 6).pack()
            _label(self.container, subtitle, dim=True).pack(anchor="w")
        _spacer(self.container, 16).pack()
        _divider(self.container).pack(fill="x")
        _spacer(self.container, 16).pack()

    def _nav(self, back=True, next_text="Continue", next_cmd=None):
        row = tk.Frame(self.container, bg=BG, pady=4)
        row.pack(side="bottom", fill="x", pady=(12, 0))
        if back and self.step > 0:
            _btn(row, "Back", self._back, accent=False).pack(side="left")
        _btn(row, next_text, next_cmd or self._next).pack(side="right")

    def _next(self):
        self.step += 1
        self._render()

    def _back(self):
        self.step -= 1
        self._render()

    def _render(self):
        self._clear()
        if 0 <= self.step < len(self.steps):
            self.steps[self.step]()

    # ── Step 0: Welcome ───────────────────────────────────────────────────────
    def _step_welcome(self):
        self._header(0, "Welcome to KPrompter",
                     "Transform rough text into AI-ready prompts — one hotkey, any app.")

        steps_data = [
            ("1", "Select text anywhere", "Highlight text in any application"),
            ("2", "Press your hotkey", "KPrompter captures and optimizes it"),
            ("3", "Get optimized prompt", "Pasted back automatically"),
        ]
        for num, title, desc in steps_data:
            row = _card(self.container, pady=CARD_IPADY, padx=CARD_IPADX)
            row.pack(fill="x", pady=5)

            # Step number circle
            num_lbl = tk.Label(row, text=num, bg=ACCENT, fg="#ffffff",
                               font=(*FONT_UI[:2], "bold"),
                               width=3, height=1)
            num_lbl.pack(side="left", padx=(0, 14))

            text_frame = tk.Frame(row, bg=BG2)
            text_frame.pack(side="left", fill="x", expand=True)
            tk.Label(text_frame, text=title, bg=BG2, fg=TEXT,
                     font=(*FONT_UI[:2], "bold"), anchor="w").pack(anchor="w")
            tk.Label(text_frame, text=desc, bg=BG2, fg=TEXT_DIM,
                     font=FONT_UI_SM, anchor="w").pack(anchor="w")

        _spacer(self.container, 14).pack()
        _label(self.container,
               "Setup takes about 2 minutes. Everything can be changed later.",
               dim=True).pack(anchor="w")
        self._nav(back=False, next_text="Get Started")

    # ── Step 1: Provider ──────────────────────────────────────────────────────
    def _step_provider(self):
        self._header(1, "Choose a Provider",
                     "OpenRouter is recommended — free models, easy billing limits.")
        for key, info in PROVIDERS.items():
            has_free = info.get("is_free", False) or any(
                m["free"] for m in info.get("models", []))
            badge_text = "FREE" if has_free else "PAID"
            badge_color = GREEN if has_free else ORANGE

            row = _card(self.container, pady=10, padx=14)
            row.pack(fill="x", pady=4)
            row.configure()

            rb = tk.Radiobutton(row, variable=self._provider_var, value=key,
                                bg=BG2, activebackground=BG2,
                                selectcolor=BG3, fg=TEXT,
                                font=(*FONT_UI[:2], "bold"),
                                text=info["name"], relief="flat", bd=0,
                                highlightthickness=0)
            rb.pack(side="left")
            _badge(row, badge_text, color=badge_color).pack(side="left", padx=6)

            tip = info["setup_tip"][:50] + "..." if len(info["setup_tip"]) > 50 else info["setup_tip"]
            tk.Label(row, text=tip, bg=BG2, fg=TEXT_DIM,
                     font=FONT_UI_SM).pack(side="right", padx=6)
            row.bind("<Button-1>", lambda e, k=key: self._provider_var.set(k))
        self._nav()

    # ── Step 2: API Key ───────────────────────────────────────────────────────
    def _step_apikey(self):
        provider = self._provider_var.get()
        info = PROVIDERS[provider]
        self._header(2, f"API Key — {info['name']}", info["setup_tip"])

        if provider == "ollama":
            card = _card(self.container, pady=16, padx=18)
            card.pack(fill="x")
            tk.Label(card, text="No API key needed", bg=BG2, fg=GREEN,
                     font=(*FONT_UI[:2], "bold")).pack(anchor="w")
            _spacer(card, 4).pack()
            tk.Label(card, text="Make sure Ollama is running:  ollama serve",
                     bg=BG2, fg=TEXT_DIM, font=FONT_MONO_SM).pack(anchor="w")
            _spacer(self.container, 14).pack()
            _btn(self.container, "Download Ollama",
                 lambda: webbrowser.open(info["key_url"]), accent=False).pack(anchor="w")
        else:
            _label(self.container, "Paste your API key:").pack(anchor="w")
            _spacer(self.container, 6).pack()
            key_entry = _entry(self.container, textvariable=self._key_var, show="*", width=48)
            key_entry.pack(fill="x", ipady=8)
            _spacer(self.container, 12).pack()

            btn_row = tk.Frame(self.container, bg=BG)
            btn_row.pack(anchor="w")
            _btn(btn_row, "Get API Key",
                 lambda: webbrowser.open(info["key_url"]), accent=False).pack(side="left")
            if provider == "openrouter":
                _btn(btn_row, "Set $0 Limit",
                     lambda: webbrowser.open("https://openrouter.ai/credits"),
                     accent=False).pack(side="left", padx=8)

            _spacer(self.container, 16).pack()

            # Warning card
            warn = tk.Frame(self.container, bg="#2a1a00",
                            highlightthickness=1, highlightbackground=YELLOW,
                            pady=12, padx=16)
            warn.pack(fill="x")
            tk.Label(warn, text="⚠  Set a spending limit before using paid models.",
                     bg="#2a1a00", fg=YELLOW, font=(*FONT_UI[:2], "bold")).pack(anchor="w")
        self._nav()

    # ── Step 3: Model picker ──────────────────────────────────────────────────
    def _step_model(self):
        from config import fetch_gemini_models
        provider = self._provider_var.get()
        self._header(3, "Pick a Model",
                     "FREE models cost nothing. PAID models bill your account.")

        _label(self.container, "Model").pack(anchor="w")
        _spacer(self.container, 6).pack()

        model_frame = tk.Frame(self.container, bg=BG)
        model_frame.pack(anchor="w", fill="x")
        status_lbl = tk.Label(self.container, text="", bg=BG, fg=TEXT_DIM,
                              font=FONT_UI_SM)
        status_lbl.pack(anchor="w")

        def _build_static():
            for w in model_frame.winfo_children():
                w.destroy()
            status_lbl.configure(text="")
            self._model_cb = _model_combobox(model_frame, provider, self._model_var)
            self._model_cb.pack(anchor="w", fill="x")

        def _build_dynamic(models):
            for w in model_frame.winfo_children():
                w.destroy()
            if not models:
                status_lbl.configure(text="Using built-in model list (API key needed to refresh)", fg=ORANGE)
                _build_static()
                return
            status_lbl.configure(text=f"{len(models)} models fetched", fg=GREEN)
            cb = ttk.Combobox(model_frame, textvariable=self._model_var,
                              values=models, state="readonly",
                              style="Model.TCombobox", width=42)
            cur = self._model_var.get()
            if cur in models:
                cb.set(cur)
            else:
                cb.current(0)
                self._model_var.set(models[0])
            cb._model_map = {m: m for m in models}
            cb.pack(anchor="w", fill="x")
            self._model_cb = cb

        def _fetch_gemini():
            status_lbl.configure(text="Fetching models…", fg=TEXT_DIM)
            api_key = self._key_var.get().strip() if hasattr(self, "_key_var") else ""
            def _do():
                models = fetch_gemini_models(api_key)
                model_frame.after(0, lambda: _build_dynamic(models))
            threading.Thread(target=_do, daemon=True).start()

        if provider == "gemini":
            _fetch_gemini()
        else:
            _build_static()

        _spacer(self.container, 16).pack()

        best = get_best_model(provider)
        rec = _card(self.container, pady=12, padx=16)
        rec.pack(fill="x")
        tk.Label(rec, text="Recommended", bg=BG2, fg=TEXT_DIM,
                 font=FONT_UI_SM).pack(side="left")
        tk.Label(rec, text=best, bg=BG2, fg=GREEN,
                 font=FONT_MONO).pack(side="left", padx=10)

        _spacer(self.container, 10).pack()

        btn_row = tk.Frame(self.container, bg=BG)
        btn_row.pack(anchor="w")

        def use_best():
            if provider == "gemini":
                self._model_var.set(best)
                if self._model_cb and best in self._model_cb["values"]:
                    self._model_cb.set(best)
            else:
                best_label = ""
                for label, mid, free in get_model_labels(provider):
                    if mid == best:
                        tag = "  [FREE]" if free else "  [PAID]"
                        best_label = f"{label}{tag}"
                        break
                if best_label:
                    self._model_var.set(best_label)
                    self._model_cb.set(best_label)

        _btn(btn_row, "Use Recommended", use_best, accent=False).pack(side="left", padx=(0, 8))
        if provider == "gemini":
            _btn(btn_row, "↺ Refresh", _fetch_gemini, accent=False, small=True).pack(side="left")
        self._nav()

    # ── Step 4: Hotkey ────────────────────────────────────────────────────────
    def _step_hotkey(self):
        self._header(4, "Set Your Hotkey",
                     "This key combination triggers KPrompter on selected text.")

        rec_frame = _card(self.container, pady=24, padx=20)
        rec_frame.pack(fill="x")

        self._hotkey_display = tk.Label(rec_frame, text=self._hotkey_var.get(),
                                        bg=BG2, fg=ACCENT,
                                        font=FONT_MONO_LG)
        self._hotkey_display.pack()
        _spacer(rec_frame, 4).pack()
        self._rec_status = tk.Label(rec_frame,
                                    text="Click Record, then press your key combination",
                                    bg=BG2, fg=TEXT_DIM, font=FONT_UI_SM)
        self._rec_status.pack()

        _spacer(self.container, 14).pack()
        btn_row = tk.Frame(self.container, bg=BG)
        btn_row.pack()
        _btn(btn_row, "Record Hotkey", self._start_recording).pack(side="left", padx=4)
        _btn(btn_row, "Reset Default", self._reset_hotkey, accent=False).pack(side="left", padx=4)

        _spacer(self.container, 14).pack()
        rec = "Cmd+Option+K recommended on macOS" if _is_mac else "Ctrl+Alt+K recommended"
        _sublabel(self.container, rec).pack(anchor="w")
        self._nav()

    def _reset_hotkey(self):
        d = "cmd+option+k" if _is_mac else "ctrl+alt+k"
        self._hotkey_var.set(d)
        if hasattr(self, '_hotkey_display'):
            self._hotkey_display.configure(text=d)

    def _start_recording(self):
        if self._recording:
            return
        self._recording = True
        self._pressed = set()
        if hasattr(self, '_rec_status'):
            self._rec_status.configure(text="Listening... press your combo now", fg=ACCENT2)
        self.root.bind("<KeyPress>", self._on_key_press)
        self.root.bind("<KeyRelease>", self._on_key_release)
        self.root.focus_force()

    def _on_key_press(self, e):
        if not self._recording:
            return
        k = _normalize_key(e.keysym.lower(), e.char)
        _alt = _alt_label()
        MOD_MAP = {
            "control_l": "ctrl", "control_r": "ctrl",
            "alt_l": _alt,       "alt_r": _alt,
            "shift_l": "shift",  "shift_r": "shift",
            "super_l": "cmd",    "super_r": "cmd",
            "meta_l": "cmd",     "meta_r": "cmd",
        }
        if k in MOD_MAP:
            self._pressed.add(MOD_MAP[k])
            if hasattr(self, '_hotkey_display'):
                self._hotkey_display.configure(
                    text="+".join(_mod_order(self._pressed)) + "+…")
            return
        # Non-modifier — finalise
        parts = _mod_order(self._pressed)
        parts.append(k)
        combo = "+".join(parts)
        self._hotkey_var.set(combo)
        if hasattr(self, '_hotkey_display'):
            self._hotkey_display.configure(text=combo)
        if hasattr(self, '_rec_status'):
            self._rec_status.configure(text="Hotkey saved!", fg=GREEN)
        self._recording = False
        self.root.unbind("<KeyPress>")
        self.root.unbind("<KeyRelease>")

    def _on_key_release(self, e):
        if not self._recording:
            return
        k = e.keysym.lower()
        _alt = _alt_label()
        MOD_MAP = {
            "control_l": "ctrl", "control_r": "ctrl",
            "alt_l": _alt,       "alt_r": _alt,
            "shift_l": "shift",  "shift_r": "shift",
            "super_l": "cmd",    "super_r": "cmd",
            "meta_l": "cmd",     "meta_r": "cmd",
        }
        if k in MOD_MAP:
            self._pressed.discard(MOD_MAP[k])

    # ── Step 5: Done ──────────────────────────────────────────────────────────
    def _step_done(self):
        self._save()
        self._header(5, "You're all set!", "KPrompter is ready to optimize your prompts.")

        cfg = load_config()
        provider = cfg.get("provider", "openrouter")
        for icon, label, val in [
            ("⚡", "Provider", PROVIDERS.get(provider, {}).get("name", provider)),
            ("🤖", "Model",    cfg.get("model", "")),
            ("⌨", "Hotkey",   cfg.get("hotkey", "")),
        ]:
            row = _card(self.container, pady=10, padx=14)
            row.pack(fill="x", pady=3)
            tk.Label(row, text=f"  {icon}  {label}", bg=BG2, fg=TEXT_DIM,
                     font=FONT_UI, width=16, anchor="w").pack(side="left")
            tk.Label(row, text=val, bg=BG2, fg=ACCENT,
                     font=FONT_MONO).pack(side="left")

        _spacer(self.container, 16).pack()

        tip_card = _card(self.container, pady=12, padx=16)
        tip_card.pack(fill="x")
        tk.Label(tip_card, text="Quick Start", bg=BG2, fg=GREEN,
                 font=(*FONT_UI[:2], "bold")).pack(anchor="w")
        _spacer(tip_card, 4).pack()
        tk.Label(tip_card,
                 text="1. Select text in any app\n2. Press your hotkey\n3. KPrompter optimizes and pastes it back",
                 bg=BG2, fg=TEXT_DIM, font=FONT_UI_SM,
                 justify="left").pack(anchor="w")

        _spacer(self.container, 6).pack()
        _sublabel(self.container,
                  "Open Settings from the KPrompter window to change preferences anytime.").pack(anchor="w")

        row = tk.Frame(self.container, bg=BG)
        row.pack(side="bottom", fill="x", pady=(12, 0))
        _btn(row, "Back", self._back, accent=False).pack(side="left")
        _btn(row, "Launch KPrompter", self.root.destroy).pack(side="right")

    def _save(self):
        model_id = self.cfg.get("model", "")
        if self._model_cb:
            selected_label = self._model_var.get()
            model_id = getattr(self._model_cb, '_model_map', {}).get(selected_label, selected_label)

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
        if self.parent_root:
            self.root.wait_window()
        else:
            self.root.mainloop()




# ══════════════════════════════════════════════════════════════════════════════
def insert_markdown(st, text, base_font=("SF Mono", 11), align="left", text_color="#ffffff", bg_color="#2c2c2e"):
    """A lightweight markdown-like renderer for Tkinter ScrolledText."""
    st.tag_configure("h1", font=(base_font[0], base_font[1]+4, "bold"), foreground=text_color)
    st.tag_configure("h2", font=(base_font[0], base_font[1]+2, "bold"), foreground=text_color)
    st.tag_configure("h3", font=(base_font[0], base_font[1], "bold"), foreground=text_color)
    st.tag_configure("bold", font=(base_font[0], base_font[1], "bold"))
    st.tag_configure("italic", font=(base_font[0], base_font[1], "italic"))
    st.tag_configure("code", background="#1c1c1e", foreground="#ffd60a", font=base_font)
    st.tag_configure("pre", background="#1c1c1e", foreground="#ffffff", font=base_font)
    
    st.tag_configure(align, justify=align)
    
    lines = text.splitlines()
    in_pre = False
    for line in lines:
        if line.strip().startswith("```"):
            in_pre = not in_pre
            continue
        
        if in_pre:
            st.insert("end", line + "\n", ("pre", align))
            continue
            
        if line.startswith("# "):
            st.insert("end", line[2:] + "\n", ("h1", align))
            continue
        elif line.startswith("## "):
            st.insert("end", line[3:] + "\n", ("h2", align))
            continue
        elif line.startswith("### "):
            st.insert("end", line[4:] + "\n", ("h3", align))
            continue
            
        tokens = re.split(r"(\*\*.*?\*\*|\*.*?\*|`.*?`)", line)
        for t in tokens:
            if t.startswith("**") and t.endswith("**") and len(t) > 3:
                st.insert("end", t[2:-2], ("bold", align))
            elif t.startswith("*") and t.endswith("*") and len(t) > 1 and not t == "**":
                st.insert("end", t[1:-1], ("italic", align))
            elif t.startswith("`") and t.endswith("`") and len(t) > 1:
                st.insert("end", t[1:-1], ("code", align))
            else:
                st.insert("end", t, align)
        # Using double escaping for newlines because we are writing inside a python multi-line string inside python
        st.insert("end", "\n", align)

    if lines:
        st.delete("end-1c", "end")


# ══════════════════════════════════════════════════════════════════════════════
# PILL TEXT INPUT COMPONENT
# ══════════════════════════════════════════════════════════════════════════════

class _PillText(tk.Canvas):
    """Rounded pill text input.
    • No white/grey OS focus ring — accent-green border on focus instead.
    • Auto-grows vertically as content increases (up to _MAX_H px).
    • Scrolls within the pill once the max height is reached.
    """
    _MIN_H = 52    # px — resting height (~2 lines)
    _MAX_H = 200   # px — cap before internal scroll kicks in
    _PAD_X = 14    # horizontal inner padding
    _PAD_Y = 10    # vertical inner padding

    def __init__(self, master, bg, fg, font, height_lines=2, radius=16, **kwargs):
        super().__init__(master,
                         bg=master.cget('bg'),
                         highlightthickness=0, bd=0, relief="flat",
                         height=self._MIN_H, **kwargs)
        self.radius     = radius
        self.fill_color = bg
        self.fg         = fg
        self._focused   = False
        self.bind("<Configure>", self._on_resize)

        self.text_widget = tk.Text(
            self, bg=bg, fg=fg, bd=0, highlightthickness=0,
            relief="flat", font=font, insertbackground=ACCENT,
            wrap="word", undo=True,
        )
        self.text_widget_window = self.create_window(
            self._PAD_X, self._PAD_Y, anchor="nw", window=self.text_widget
        )

        # Auto-grow on every keypress and after paste
        self.text_widget.bind("<KeyRelease>", lambda e: self._auto_resize())
        self.text_widget.bind("<<Paste>>",    lambda e: self.after(20, self._auto_resize))

        # Green accent border on focus, fade on blur
        self.text_widget.bind("<FocusIn>",    self._on_focus_in)
        self.text_widget.bind("<FocusOut>",   self._on_focus_out)

    # ── Drawing ────────────────────────────────────────────────────────────

    def _draw_bg(self, w, h):
        tk.Canvas.delete(self, "bg")
        r   = self.radius
        col = self.fill_color
        # Subtle green glow border on focus; invisible (same as fill) when idle
        brd = ACCENT if self._focused else BG3
        self.create_polygon(
            r, 0, w-r, 0, w-r, 0,
            w, 0, w, r, w, r,
            w, h-r, w, h-r, w, h,
            w-r, h, w-r, h,
            r, h, r, h, 0, h,
            0, h-r, 0, h-r, 0, r,
            0, r, 0, 0, r, 0,
            smooth=True, fill=col, outline=brd, width=2, tags="bg",
        )
        self.tag_lower("bg")

    def _on_resize(self, e):
        w, h = e.width, e.height
        self._draw_bg(w, h)
        self.itemconfig(self.text_widget_window,
                        width=max(1,  w - self._PAD_X * 2),
                        height=max(1, h - self._PAD_Y * 2))

    # ── Focus visuals ──────────────────────────────────────────────────────

    def _on_focus_in(self, e=None):
        self._focused = True
        self._draw_bg(self.winfo_width(), self.winfo_height())

    def _on_focus_out(self, e=None):
        self._focused = False
        self._draw_bg(self.winfo_width(), self.winfo_height())

    # ── Auto-grow ──────────────────────────────────────────────────────────

    def _auto_resize(self):
        """Expand pill height to fit content; cap at _MAX_H then scroll."""
        try:
            n = int(self.text_widget.count("1.0", "end", "displaylines")[0] or 1)
        except Exception:
            n = int(self.text_widget.index("end-1c").split(".")[0])

        info = self.text_widget.dlineinfo("1.0")
        lh   = info[3] if info else 20   # height of one display line in px
        target = int(min(self._MAX_H, max(self._MIN_H, n * lh + self._PAD_Y * 2 + 4)))
        if abs(target - self.winfo_height()) > 2:
            self.configure(height=target)

    # ── Public API ─────────────────────────────────────────────────────────

    def get_text(self):
        return self.text_widget.get("1.0", "end")

    def clear_text(self):
        self.text_widget.delete("1.0", "end")
        self.after(10, self._auto_resize)   # snap back to min height

    def focus_set(self):
        self.text_widget.focus_set()

    def bind_text(self, seq, fn):
        """Bind a keyboard event to the inner Text widget."""
        self.text_widget.bind(seq, fn)


# ══════════════════════════════════════════════════════════════════════════════
# SETTINGS WINDOW
# ══════════════════════════════════════════════════════════════════════════════

class SettingsWindow:
    def __init__(self, parent=None, container=None, back_cb=None, show_home=False, on_optimize=None, on_retry=None, on_hotkey_change=None):
        self._back_cb = back_cb
        self._show_home = show_home
        self._on_optimize = on_optimize
        self._on_retry = on_retry
        self._on_hotkey_change = on_hotkey_change
        self._nb = None
        if container is not None:
            # Embedded in the main window's container frame
            self.root = container.winfo_toplevel()
            self._frame = tk.Frame(container, bg=BG)
            self._frame.pack(fill="both", expand=True)
        else:
            if parent:
                self.root = tk.Toplevel(parent)
            else:
                self.root = tk.Toplevel()
            _style_root(self.root, "KPrompter — Settings", 700, 580, resizable=True)
            self.root.lift()
            self._frame = self.root
        self.cfg = load_config()
        self._build()

    def _build(self):
        # ── Header: rounded pill bar ───────────────────────────────────────
        tabbar = tk.Frame(self._frame, bg=BG2, height=52)
        tabbar.pack(fill="x")
        tabbar.pack_propagate(False)

        # K> logo — full terminal green to match icon
        logo_frame = tk.Frame(tabbar, bg=BG2)
        logo_frame.place(x=16, rely=0.5, anchor="w")
        tk.Label(logo_frame, text="K", font=(FONT_MONO[0], 13, "bold"),
                 bg=BG2, fg=HEADER_CYN).pack(side="left")
        tk.Label(logo_frame, text=">", font=(FONT_MONO[0], 13, "bold"),
                 bg=BG2, fg=HEADER_GRN).pack(side="left")

        # Pill tabs — centered in the FULL bar (place: relx=0.5)
        inner = tk.Frame(tabbar, bg=BG2)
        inner.place(relx=0.5, rely=0.5, anchor="center")

        # ── Thin model-name strip below header ────────────────────────────
        self._model_strip = tk.Frame(self._frame, bg=BG, height=26)
        self._model_strip.pack(fill="x")
        self._model_strip.pack_propagate(False)
        self._model_lbl = tk.Label(
            self._model_strip, text="",
            bg=BG, fg=TEXT_DIM, font=FONT_UI_SM,
        )
        self._model_lbl.place(relx=0.5, rely=0.5, anchor="center")

        # ── Tab content frames ────────────────────────────────────────────
        content = tk.Frame(self._frame, bg=BG)
        content.pack(fill="both", expand=True)

        tabs_order = []
        if self._show_home:
            tabs_order.append("Home")
        tabs_order += ["General", "Provider", "Instructions", "Logs"]

        frames = {}
        for tab_name in tabs_order:
            f = tk.Frame(content, bg=BG)
            frames[tab_name] = f

        if "Home" in frames:
            self._tab_home(frames["Home"])
        self._tab_general(frames["General"])
        self._tab_provider(frames["Provider"])
        self._tab_instructions(frames["Instructions"])
        self._tab_log(frames["Logs"])

        # ── Tab switching ─────────────────────────────────────────────────
        self._tab_frames = frames
        self._tab_pill_btns: list = []

        def switch(name):
            for f in frames.values():
                f.pack_forget()
            frames[name].pack(fill="both", expand=True)
            for btn in self._tab_pill_btns:
                btn.set_state(btn._txt == name)
            if name == "Provider" and hasattr(self, "_refresh_provider_models"):
                self._refresh_provider_models()

        self._switch_tab = switch

        for tab_name in tabs_order:
            pb = _PillBtn(inner, tab_name,
                          command=lambda n=tab_name: switch(n),
                          bg=BG3, fg=TEXT_DIM, hover_bg=BTN_H,
                          fnt=(FONT_UI[0], 10, "bold"),
                          padx=14, pady=5, parent_bg=BG2)
            pb.pack(side="left", padx=2)
            self._tab_pill_btns.append(pb)

        switch(tabs_order[0])
        self._nb = None

    # ── Home tab ──────────────────────────────────────────────────────────────
    def _tab_home(self, frame):
        self._home_container = frame
        self._refresh_home_vars()

        # Build Welcome Frame
        self._welcome_frame = tk.Frame(frame, bg=BG)

        # Top Spacer - pushes content to center
        tk.Frame(self._welcome_frame, bg=BG).pack(side="top", fill="both", expand=True)

        # Title: K> in icon colors + " Chat?"
        title_frame = tk.Frame(self._welcome_frame, bg=BG)
        title_frame.pack(side="top", pady=(0, 20))
        tk.Label(title_frame, text="K", font=(FONT_MONO[0], 22, "bold"),
                 bg=BG, fg=HEADER_CYN).pack(side="left")
        tk.Label(title_frame, text=">", font=(FONT_MONO[0], 22, "bold"),
                 bg=BG, fg=HEADER_GRN).pack(side="left")
        tk.Label(title_frame, text="  Chat?", bg=BG, fg="#c8fce8",
                 font=(FONT_UI[0], 22)).pack(side="left")

        # Rounded pill text input
        self._w_input = _PillText(self._welcome_frame, bg=BG3, fg=TEXT, font=FONT_MONO_SM, height_lines=2)
        self._w_input.pack(side="top", fill="x", padx=60, pady=10)
        self._w_input.bind_text("<Return>",       lambda e: (self._trigger_optimize(self._w_input), "break")[1])
        self._w_input.bind_text("<Shift-Return>",  lambda e: None)

        w_btn_row = tk.Frame(self._welcome_frame, bg=BG)
        w_btn_row.pack(side="top", fill="x", padx=60, pady=6)
        _PillBtn(w_btn_row, "Optimize →", command=lambda: self._trigger_optimize(self._w_input),
                 bg=BTN, fg=ACCENT, hover_bg=BTN_H, fnt=(*FONT_UI[:2], "bold"),
                 padx=20, pady=6, parent_bg=BG).pack(side="right")

        # Bottom Spacer
        tk.Frame(self._welcome_frame, bg=BG).pack(side="top", fill="both", expand=True)

        # Chat Feed Frame
        self._chat_frame = tk.Frame(frame, bg=BG, padx=14, pady=10)
        from tkinter import scrolledtext
        self._home_chat = scrolledtext.ScrolledText(
            self._chat_frame, bg=BG, fg=TEXT, font=FONT_MONO_SM,
            relief="flat", bd=0, wrap="word", padx=10, pady=10,
        )
        self._home_chat.pack(fill="both", expand=True)
        self._home_chat.configure(state="disabled")

        # Persistent bottom input bar
        self._input_frame = tk.Frame(frame, bg=BG, padx=20, pady=10)

        self._home_input = _PillText(self._input_frame, bg=BG3, fg=TEXT, font=FONT_MONO_SM, height_lines=2)
        self._home_input.pack(side="top", fill="x", pady=(0, 8))
        self._home_input.bind_text("<Return>",      lambda e: (self._trigger_optimize(self._home_input), "break")[1])
        self._home_input.bind_text("<Shift-Return>", lambda e: None)

        btn_row = tk.Frame(self._input_frame, bg=BG)
        btn_row.pack(side="bottom", fill="x", pady=(6, 0))

        self._send_btn = _PillBtn(btn_row, "Optimize →", command=lambda: self._trigger_optimize(self._home_input),
                 bg=BTN, fg=ACCENT, hover_bg=BTN_H, fnt=(*FONT_UI[:2], "bold"),
                 padx=20, pady=6, parent_bg=BG)
        self._send_btn.pack(side="right")

        def _clear_chat():
            self.render_history([])
            if hasattr(self, '_on_clear_conversation') and self._on_clear_conversation:
                self._on_clear_conversation()
        _btn(btn_row, "Clear Chat", _clear_chat, accent=False, small=True).pack(side="left")

        # Show welcome frame by default
        self._welcome_frame.pack(fill="both", expand=True)

    def _trigger_optimize(self, text_widget):
        # Support both plain tk.Text and _PillText
        if isinstance(text_widget, _PillText):
            text = text_widget.get_text().strip()
            if not text:
                return
            text_widget.clear_text()
        else:
            text = text_widget.get("1.0", "end").strip()
            if not text:
                return
            text_widget.delete("1.0", "end")
        
        # We enforce transition to chat mode
        self._welcome_frame.pack_forget()
        self._input_frame.pack(side="bottom", fill="x")
        self._chat_frame.pack(side="top", fill="both", expand=True)
        
        if self._on_optimize:
            self._on_optimize(text)

    def render_history(self, conversation):
        if not conversation:
            self._chat_frame.pack_forget()
            self._input_frame.pack_forget()
            self._welcome_frame.pack(fill="both", expand=True)
            try:
                self._w_input.focus_set()
            except Exception:
                pass
        else:
            self._welcome_frame.pack_forget()
            self._input_frame.pack(side="bottom", fill="x")
            self._chat_frame.pack(side="top", fill="both", expand=True)
            
            self._home_chat.configure(state="normal")
            self._home_chat.delete("1.0", "end")
            self._home_chat.configure(state="disabled")
            for msg in conversation:
                if msg["role"] == "user":
                    self.append_user_message(msg["content"], is_history=True)
                elif msg["role"] == "assistant":
                    self.append_ai_message(msg["content"], is_history=True)
            self._home_chat.yview_moveto(1)
            try:
                self._home_input.focus_set()
            except Exception:
                pass
            

    def _copy_text(self, text):
        import subprocess
        try:
            subprocess.run(["pbcopy"], input=text.encode(), check=False, timeout=3)
        except:
            pass

    def append_user_message(self, text, is_history=False):
        if not is_history:
            self._ensure_chat_mode()
        self._home_chat.configure(state="normal")
        self._home_chat.tag_configure("right", justify="right")
        self._home_chat.tag_configure("bold", font=(*FONT_MONO_SM[:2], "bold"))
        self._home_chat.tag_configure("user_bg", justify="right", background="#2e4a3e", foreground=ACCENT, spacing1=5, spacing3=5, font=FONT_MONO_SM, lmargin1=40, lmargin2=40)
        
        self._home_chat.insert("end", "\n\nYou\n", ("right", "bold"))
        self._home_chat.insert("end", text, "user_bg")
        self._home_chat.insert("end", "\n", "right")

        btn_bar = tk.Frame(self._home_chat, bg=BG)
        _btn(btn_bar, "Copy", lambda t=text: self._copy_text(t), accent=False, small=True).pack(side="right", padx=2)
        if hasattr(self, '_on_retry') and self._on_retry:
            _btn(btn_bar, "Retry", lambda t=text: self._on_retry(t), accent=False, small=True).pack(side="right", padx=2)
        
        self._home_chat.window_create("end", window=btn_bar, align="baseline")
        if not is_history:
            self._home_chat.yview_moveto(1)
            self._home_chat.update_idletasks()
        self._home_chat.configure(state="disabled")

    def append_ai_message(self, text, is_history=False):
        self._home_chat.configure(state="normal")
        self._home_chat.tag_configure("left", justify="left")
        self._home_chat.tag_configure("bold", font=(*FONT_MONO_SM[:2], "bold"))
        
        self._home_chat.insert("end", "\n\nAI\n", ("left", "bold"))
        insert_markdown(self._home_chat, text, align="left", bg_color=BG)
        self._home_chat.insert("end", "\n", "left")

        btn_bar = tk.Frame(self._home_chat, bg=BG)
        _btn(btn_bar, "Copy Model Answer", lambda t=text: self._copy_text(t), accent=False, small=True).pack(side="left", padx=2)
        
        self._home_chat.window_create("end", window=btn_bar, align="baseline")
        if not is_history:
            self._home_chat.yview_moveto(1)
            self._home_chat.update_idletasks()
        self._home_chat.configure(state="disabled")

    def show_typing(self):
        self._home_chat.configure(state="normal")
        self._home_chat.tag_configure("left", justify="left")
        self._typing_mark = self._home_chat.index("end-1c")
        self._home_chat.insert("end", "\n\n[AI is thinking...]", ("left", "italic"))
        self._home_chat.yview_moveto(1)
        self._home_chat.update_idletasks()
        self._home_chat.configure(state="disabled")
        
    def hide_typing(self):
        if hasattr(self, '_typing_mark'):
            self._home_chat.configure(state="normal")
            self._home_chat.delete(self._typing_mark, "end")
            self._home_chat.configure(state="disabled")

    def _refresh_home_vars(self):
        cfg = load_config()
        self.cfg = cfg
        model = cfg.get("model", "")
        model_short = (model.split("/")[-1].split(":")[0]) if model else ""
        if hasattr(self, "_model_lbl"):
            self._model_lbl.configure(text=model_short or model or "")

    def switch_to_settings(self):
        """Switch to the General tab."""
        if hasattr(self, "_switch_tab"):
            self._switch_tab("General")

    def _ensure_chat_mode(self):
        """Switch from the welcome screen to the chat feed view.
        Called by the hotkey flow so messages appear in the Home tab
        even when the user hasn't typed anything in the app yet.
        """
        if hasattr(self, "_welcome_frame"):
            self._welcome_frame.pack_forget()
        if hasattr(self, "_chat_frame"):
            self._chat_frame.pack(side="top", fill="both", expand=True)
        if hasattr(self, "_input_frame"):
            self._input_frame.pack(side="bottom", fill="x")
        # Bring the Home tab to front if we're on another tab
        if self._show_home and hasattr(self, "_switch_tab"):
            self._switch_tab("Home")

    def _pad(self, frame):
        pad = tk.Frame(frame, bg=BG, padx=24, pady=20)
        pad.pack(fill="both", expand=True)
        return pad

    # ── General ───────────────────────────────────────────────────────────────
    def _tab_general(self, frame):
        pad = self._pad(frame)

        # Section header
        tk.Label(pad, text="Hotkey Configuration", bg=BG, fg=TEXT,
                 font=FONT_SUB).pack(anchor="w")
        _spacer(pad, 8).pack()

        _label(pad, "Keyboard shortcut").pack(anchor="w")
        _spacer(pad, 4).pack()

        hk_var = tk.StringVar(value=_hotkey_display(self.cfg.get("hotkey", "cmd+option+k" if _is_mac else "ctrl+alt+k")))

        hk_row = tk.Frame(pad, bg=BG)
        hk_row.pack(anchor="w")

        # Read-only display of current combo
        hk_display = _entry(hk_row, textvariable=hk_var, width=24)
        hk_display.configure(state="readonly")
        hk_display.pack(side="left", ipady=7)

        _recording = [False]
        _pressed_mods = [set()]

        def _finish_record(combo):
            _recording[0] = False
            hk_var.set(combo)
            record_btn.configure(text="Record", bg=ACCENT)
            try:
                self.root.unbind("<KeyPress>")
                self.root.unbind("<KeyRelease>")
            except Exception:
                pass

        _alt = _alt_label()

        def _on_key_press(e):
            if not _recording[0]:
                return
            k = _normalize_key(e.keysym.lower(), e.char)
            MOD_MAP = {
                "control_l": "ctrl", "control_r": "ctrl",
                "alt_l": _alt,       "alt_r": _alt,
                "shift_l": "shift",  "shift_r": "shift",
                "super_l": "cmd",    "super_r": "cmd",
                "meta_l": "cmd",     "meta_r": "cmd",
            }
            if k in MOD_MAP:
                _pressed_mods[0].add(MOD_MAP[k])
                # Show partial combo while holding modifiers
                hk_var.set("+".join(_mod_order(_pressed_mods[0])) + "+…")
                return
            # Non-modifier key — build final combo
            order = _mod_order(_pressed_mods[0])
            order.append(k)
            _finish_record("+".join(order))

        def _on_key_release(e):
            if not _recording[0]:
                return
            k = e.keysym.lower()
            MOD_MAP = {
                "control_l": "ctrl", "control_r": "ctrl",
                "alt_l": _alt,       "alt_r": _alt,
                "shift_l": "shift",  "shift_r": "shift",
                "super_l": "cmd",    "super_r": "cmd",
                "meta_l": "cmd",     "meta_r": "cmd",
            }
            if k in MOD_MAP:
                _pressed_mods[0].discard(MOD_MAP[k])

        def start_record():
            if _recording[0]:
                return
            _recording[0] = True
            _pressed_mods[0].clear()
            hk_var.set("Press your combo…")
            record_btn.configure(text="Listening…", bg=RED)
            self.root.bind("<KeyPress>", _on_key_press)
            self.root.bind("<KeyRelease>", _on_key_release)
            self.root.focus_force()

        record_btn = _btn(hk_row, "Record", start_record, small=True)
        record_btn.pack(side="left", padx=(8, 0))

        _spacer(pad, 6).pack()
        _sublabel(pad, "Click Save Settings to apply the new hotkey immediately.").pack(anchor="w")

        _spacer(pad, 18).pack()
        _divider(pad).pack(fill="x")
        _spacer(pad, 18).pack()

        # Logging section
        tk.Label(pad, text="Logging", bg=BG, fg=TEXT,
                 font=FONT_SUB).pack(anchor="w")
        _spacer(pad, 8).pack()

        log_var = tk.BooleanVar(value=self.cfg.get("logging_enabled", True))
        tk.Checkbutton(pad, text="Enable session logging", variable=log_var,
                       bg=BG, fg=TEXT, selectcolor=BG3,
                       activebackground=BG, activeforeground=TEXT,
                       font=FONT_UI, highlightthickness=0).pack(anchor="w")
        _spacer(pad, 8).pack()

        _label(pad, "Max log entries").pack(anchor="w")
        _spacer(pad, 4).pack()
        log_n_var = tk.StringVar(value=str(self.cfg.get("log_max_entries", 100)))
        _entry(pad, textvariable=log_n_var, width=10).pack(anchor="w", ipady=7)

        _spacer(pad, 20).pack()

        def save():
            new_hotkey = hk_var.get()
            self.cfg["hotkey"] = new_hotkey
            self.cfg["logging_enabled"] = log_var.get()
            try:
                self.cfg["log_max_entries"] = int(log_n_var.get())
            except ValueError:
                pass
            save_config(self.cfg)
            self._refresh_home_vars()
            if self._on_hotkey_change:
                self._on_hotkey_change(new_hotkey)
                messagebox.showinfo("KPrompter", "Settings saved. Hotkey updated.")
            else:
                messagebox.showinfo("KPrompter", "Settings saved.")
        _btn(pad, "Save Settings", save).pack(anchor="w")

    # ── Provider ─────────────────────────────────────────────────────────────
    def _tab_provider(self, frame):
        from config import fetch_ollama_models, fetch_gemini_models
        pad = self._pad(frame)

        prov_var  = tk.StringVar(value=self.cfg.get("provider", "openrouter"))
        model_var = tk.StringVar(value=self.cfg.get("model", ""))
        key_var   = tk.StringVar(value=self.cfg.get("api_key", ""))
        url_var   = tk.StringVar(value=self.cfg.get("ollama_url", "http://localhost:11434"))
        _model_cb_ref = [None]

        # ── Provider radio buttons ────────────────────────────────────────
        tk.Label(pad, text="AI Provider", bg=BG, fg=TEXT,
                 font=FONT_SUB).pack(anchor="w")
        _spacer(pad, 8).pack()
        prov_frame = tk.Frame(pad, bg=BG)
        prov_frame.pack(anchor="w")
        for key, info in PROVIDERS.items():
            tk.Radiobutton(prov_frame, text=info["name"], variable=prov_var, value=key,
                           bg=BG, fg=TEXT, selectcolor=BG3,
                           activebackground=BG, activeforeground=TEXT,
                           font=FONT_UI, highlightthickness=0).pack(side="left", padx=6)

        _spacer(pad, 14).pack()
        _divider(pad).pack(fill="x")
        _spacer(pad, 14).pack()

        # ── Cloud frame: API key (hidden for Ollama) ──────────────────────
        cloud_frame = tk.Frame(pad, bg=BG)
        tk.Label(cloud_frame, text="API Key", bg=BG, fg=TEXT,
                 font=FONT_SUB).pack(anchor="w")
        _spacer(cloud_frame, 6).pack()
        _entry(cloud_frame, textvariable=key_var, show="*", width=48).pack(anchor="w", ipady=7)
        _spacer(cloud_frame, 14).pack()
        _divider(cloud_frame).pack(fill="x")
        _spacer(cloud_frame, 14).pack()

        # ── Ollama frame: URL (shown only for Ollama) ─────────────────────
        ollama_frame = tk.Frame(pad, bg=BG)
        tk.Label(ollama_frame, text="Ollama URL", bg=BG, fg=TEXT,
                 font=FONT_SUB).pack(anchor="w")
        _spacer(ollama_frame, 4).pack()
        _sublabel(ollama_frame, "Address of your local Ollama instance.").pack(anchor="w")
        _spacer(ollama_frame, 6).pack()
        _entry(ollama_frame, textvariable=url_var, width=38).pack(anchor="w", ipady=7)
        _spacer(ollama_frame, 14).pack()
        _divider(ollama_frame).pack(fill="x")
        _spacer(ollama_frame, 14).pack()

        # ── Model section (always visible) ────────────────────────────────
        model_hdr_row = tk.Frame(pad, bg=BG)
        model_hdr_row.pack(anchor="w", fill="x")
        tk.Label(model_hdr_row, text="Model", bg=BG, fg=TEXT,
                 font=FONT_SUB).pack(side="left")
        model_status = tk.Label(model_hdr_row, text="", bg=BG, fg=TEXT_DIM,
                                font=FONT_UI_SM)
        model_status.pack(side="left", padx=8)

        _spacer(pad, 6).pack()
        model_frame = tk.Frame(pad, bg=BG)
        model_frame.pack(anchor="w", fill="x")

        def _build_cloud_cb(p):
            for w in model_frame.winfo_children():
                w.destroy()
            model_status.configure(text="")
            cb = _model_combobox(model_frame, p, model_var)
            cb.pack(anchor="w", fill="x")
            _model_cb_ref[0] = cb

        def _build_dynamic_cb(models, error_msg="Not reachable"):
            """Build a combobox from a raw list of model ID strings."""
            for w in model_frame.winfo_children():
                w.destroy()
            if not models:
                p = prov_var.get()
                if p == "gemini":
                    model_status.configure(text="Fetch failed — showing built-in list", fg=ORANGE)
                    _build_cloud_cb(p)
                else:
                    model_status.configure(text=error_msg, fg=RED)
                    _model_cb_ref[0] = None
                return
            model_status.configure(text=f"{len(models)} model(s) found", fg=GREEN)
            cb = ttk.Combobox(model_frame, textvariable=model_var,
                              values=models, state="readonly",
                              style="Model.TCombobox", width=42)
            if model_var.get() in models:
                cb.set(model_var.get())
            elif models:
                cb.current(0)
                model_var.set(models[0])
            cb._model_map = {m: m for m in models}
            cb.pack(anchor="w", fill="x")
            _model_cb_ref[0] = cb

        def _build_ollama_cb(models):
            _build_dynamic_cb(models, "Ollama not reachable — is it running?")

        def refresh_ollama(*_):
            model_status.configure(text="Fetching…", fg=TEXT_DIM)
            url = url_var.get()
            def _fetch():
                models = fetch_ollama_models(url)
                pad.after(0, lambda: _build_ollama_cb(models))
            threading.Thread(target=_fetch, daemon=True).start()

        def refresh_gemini(*_):
            key = key_var.get().strip()
            if not key:
                model_status.configure(text="No key — showing built-in models", fg=ORANGE)
                _build_cloud_cb("gemini")
                return
            model_status.configure(text="Fetching…", fg=TEXT_DIM)
            def _fetch():
                models = fetch_gemini_models(key)
                pad.after(0, lambda: _build_dynamic_cb(models, "Could not fetch models — check API key"))
            threading.Thread(target=_fetch, daemon=True).start()

        def show_provider(p):
            if p == "ollama":
                cloud_frame.pack_forget()
                ollama_frame.pack(anchor="w", fill="x", before=model_hdr_row)
                refresh_ollama()
            else:
                ollama_frame.pack_forget()
                cloud_frame.pack(anchor="w", fill="x", before=model_hdr_row)
                if p == "gemini" and key_var.get().strip():
                    refresh_gemini()
                else:
                    _build_cloud_cb(p)

        show_provider(prov_var.get())

        def on_prov_change(*_):
            p = prov_var.get()
            if p != "ollama":
                model_var.set(get_best_model(p))
            show_provider(p)
        prov_var.trace_add("write", on_prov_change)

        def refresh_models(*_):
            p = prov_var.get()
            if p == "ollama":
                refresh_ollama()
            elif p == "gemini":
                refresh_gemini()
            else:
                model_status.configure(text="")
                _build_cloud_cb(p)

        # Store so the tab-switch hook can trigger a refresh
        self._refresh_provider_models = refresh_models

        _spacer(pad, 10).pack()
        btn_row = tk.Frame(pad, bg=BG)
        btn_row.pack(anchor="w")
        _btn(btn_row, "↺ Refresh Models", refresh_models, accent=False, small=True).pack(side="left")
        _spacer(pad, 14).pack()

        def save():
            cb = _model_cb_ref[0]
            model_id = model_var.get()
            if cb and hasattr(cb, "_model_map"):
                model_id = cb._model_map.get(model_var.get(), model_var.get())
            self.cfg["provider"]   = prov_var.get()
            self.cfg["api_key"]    = key_var.get()
            self.cfg["model"]      = model_id
            self.cfg["ollama_url"] = url_var.get()
            save_config(self.cfg)
            self._refresh_home_vars()
            messagebox.showinfo("KPrompter", "Provider settings saved.")
        _btn(pad, "Save Provider", save).pack(anchor="w")

    # ── Instructions ─────────────────────────────────────────────────────────
    def _tab_instructions(self, frame):
        pad = self._pad(frame)

        tk.Label(pad, text="Custom Instructions", bg=BG, fg=TEXT,
                 font=FONT_SUB).pack(anchor="w")
        _spacer(pad, 4).pack()
        _sublabel(pad,
                  "Tell the AI about you — name, role, tone, context. "
                  "Applied to every optimization.").pack(anchor="w")
        _spacer(pad, 10).pack()

        PLACEHOLDER = (
            "Example:\n"
            "My name is Kelvin. I'm an undergrad at UC Berkeley studying CS and Data Science.\n"
            "I prefer concise, professional tone. Use active voice. Avoid filler phrases.\n"
            "When writing emails, keep them short and direct."
        )

        st = scrolledtext.ScrolledText(
            pad, bg=BG3, fg=TEXT, font=FONT_MONO_SM,
            relief="flat", bd=0, wrap="word",
            insertbackground=ACCENT,
            highlightthickness=2, highlightbackground=BORDER,
            highlightcolor=ACCENT,
            padx=10, pady=10, height=14,
        )
        saved = get_custom_instructions()
        if saved:
            st.insert("1.0", saved)
        else:
            st.insert("1.0", PLACEHOLDER)
            st.configure(fg=TEXT_DIM)

        def _focus_in(e):
            if st.get("1.0", "end").strip() == PLACEHOLDER.strip():
                st.delete("1.0", "end")
                st.configure(fg=TEXT)

        def _focus_out(e):
            if not st.get("1.0", "end").strip():
                st.insert("1.0", PLACEHOLDER)
                st.configure(fg=TEXT_DIM)

        st.bind("<FocusIn>", _focus_in)
        st.bind("<FocusOut>", _focus_out)
        st.pack(fill="both", expand=True)
        _spacer(pad, 12).pack()

        def save_i():
            text = st.get("1.0", "end").strip()
            if text == PLACEHOLDER.strip():
                text = ""
            save_custom_instructions(text)
            messagebox.showinfo("KPrompter", "Custom instructions saved.")

        _btn(pad, "Save", save_i).pack(anchor="w")

    # ── Log ───────────────────────────────────────────────────────────────────
    def _tab_log(self, frame):
        pad = self._pad(frame)

        tk.Label(pad, text="Logs", bg=BG, fg=TEXT,
                 font=FONT_SUB).pack(anchor="w")
        _spacer(pad, 4).pack()
        _sublabel(pad, f"Location: {CONFIG_DIR}").pack(anchor="w")
        _spacer(pad, 10).pack()

        st = scrolledtext.ScrolledText(
            pad, bg=BG3, fg=TEXT_DIM, font=FONT_MONO_SM,
            relief="flat", bd=0, wrap="word",
            highlightthickness=2, highlightbackground=BORDER,
            padx=10, pady=10, height=14,
        )
        entries = load_log()
        if entries:
            for e in reversed(entries[-50:]):
                ts = e.get("timestamp", "")[:19]
                line = (f"{ts}  [{e.get('provider','?')}]  "
                        f"{e.get('mode','?')}  "
                        f"{e.get('input_chars',0)} → {e.get('output_chars',0)} chars\n")
                st.insert("end", line)
        else:
            st.insert("end", "No log entries yet.\n\nEntries will appear here after you use KPrompter.")
        st.configure(state="disabled")
        st.pack(fill="both", expand=True)
        _spacer(pad, 12).pack()

        def do_clear():
            if messagebox.askyesno("Clear Log", "Delete all log entries?"):
                clear_log()
                st.configure(state="normal")
                st.delete("1.0", "end")
                st.insert("1.0", "Log cleared.")
                st.configure(state="disabled")

        def open_log_dir():
            if platform.system() == "Darwin":
                subprocess.run(["open", CONFIG_DIR], check=False)
            elif platform.system() == "Windows":
                os.startfile(CONFIG_DIR)
            else:
                subprocess.run(["xdg-open", CONFIG_DIR], check=False)

        btn_row = tk.Frame(pad, bg=BG)
        btn_row.pack(anchor="w")
        _btn(btn_row, "Clear Log", do_clear, danger=True).pack(side="left")
        _btn(btn_row, "Open Logs Folder", open_log_dir, accent=False).pack(side="left", padx=(8, 0))


# ══════════════════════════════════════════════════════════════════════════════
# PROJECT WINDOW
# ══════════════════════════════════════════════════════════════════════════════

class ProjectWindow:
    """A standalone project window with its own conversation context."""

    def __init__(self, root, on_optimize=None, project_name="New Project"):
        self.project_name = project_name
        self.conversation: list = []
        self.busy = False
        self._on_optimize = on_optimize
        self._on_retry = None

        self.win = tk.Toplevel(root)
        self.win.title(f"KPrompter — {project_name}")
        self.win.configure(bg=BG)
        self.win.minsize(500, 400)
        w, h = 640, 520
        sw = self.win.winfo_screenwidth()
        sh = self.win.winfo_screenheight()
        self.win.geometry(f"{w}x{h}+{(sw-w)//2+30}+{(sh-h)//2+30}")
        self.win.resizable(True, True)
        self._build()

    def _build(self):
        # Header bar: K> + editable project name
        hdr = tk.Frame(self.win, bg=BG2, height=48)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        tk.Label(hdr, text="K>", font=(FONT_MONO[0], 13, "bold"),
                 bg=BG2, fg=ACCENT).place(x=14, rely=0.5, anchor="w")

        self._name_var = tk.StringVar(value=self.project_name)
        name_entry = tk.Entry(hdr, textvariable=self._name_var,
                              bg=BG2, fg=TEXT, relief="flat", bd=0,
                              insertbackground=TEXT, disabledforeground=TEXT_DIM,
                              font=(FONT_UI[0], 11, "bold"), width=28)
        name_entry.place(relx=0.5, rely=0.5, anchor="center")
        name_entry.bind("<Return>",   lambda e: self._update_name())
        name_entry.bind("<FocusOut>", lambda e: self._update_name())

        _divider(self.win).pack(fill="x")

        # Body
        body = tk.Frame(self.win, bg=BG, padx=22, pady=14)
        body.pack(fill="both", expand=True)

        tk.Label(body, text="Paste your prompt, then click Optimize.",
                 bg=BG, fg=TEXT_DIM, font=FONT_UI_SM).pack(anchor="w")
        _spacer(body, 8).pack()

        self._input = tk.Text(
            body, bg=BG3, fg=TEXT, font=FONT_MONO,
            relief="flat", bd=0, wrap="word",
            insertbackground=TEXT,
            highlightthickness=1, highlightbackground=BORDER,
            padx=12, pady=10,
        )
        self._input.pack(fill="both", expand=True)
        _spacer(body, 12).pack()

        btn_row = tk.Frame(body, bg=BG)
        btn_row.pack(fill="x")

        _btn(btn_row, "Clear History", self._clear, small=True).pack(side="left")
        _btn(btn_row, "Optimize →", self._optimize).pack(side="right")

    def _update_name(self):
        name = self._name_var.get().strip() or "Project"
        self.project_name = name
        self.win.title(f"KPrompter — {name}")

    def _optimize(self):
        text = self._input.get("1.0", "end").strip()
        if text and self._on_optimize and not self.busy:
            self._on_optimize(text, self)

    def _clear(self):
        self.conversation = []
        messagebox.showinfo("KPrompter", "Conversation history cleared.")


# ══════════════════════════════════════════════════════════════════════════════
# LOADING SPINNER
# ══════════════════════════════════════════════════════════════════════════════

class LoadingPopup:
    """Small transparent pill at the top-right of the screen while the AI is working."""

    _BAR_BG  = "#1c1c1e"
    _W, _H   = 220, 36

    def __init__(self, parent=None):
        self.root = tk.Toplevel()
        self.root.withdraw()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        if SYSTEM == "Darwin":
            self.root.attributes("-alpha", 0.88)

        sw = self.root.winfo_screenwidth()
        x  = sw - self._W - 20
        y  = 20
        self.root.geometry(f"{self._W}x{self._H}+{x}+{y}")

        outer = tk.Frame(self.root, bg=self._BAR_BG,
                         highlightthickness=1, highlightbackground=BORDER)
        outer.pack(fill="both", expand=True)

        row = tk.Frame(outer, bg=self._BAR_BG)
        row.pack(fill="x", padx=10, pady=(6, 2))
        tk.Label(row, text="K>", bg=self._BAR_BG, fg=ACCENT,
                 font=(FONT_MONO[0], 9, "bold")).pack(side="left")
        self._lbl = tk.Label(row, text=" optimizing", bg=self._BAR_BG, fg=TEXT_DIM,
                              font=(FONT_UI[0], 9))
        self._lbl.pack(side="left")

        style = ttk.Style()
        style.configure("KPill.Horizontal.TProgressbar",
                        troughcolor=BORDER, background=ACCENT, thickness=2)
        self._pb = ttk.Progressbar(outer, style="KPill.Horizontal.TProgressbar",
                                    mode="indeterminate")
        self._pb.pack(fill="x", padx=10, pady=(0, 6))
        self._pb.start(10)

        self._dots = 0
        self._id   = None
        self._tick()
        self.root.deiconify()

    def _tick(self):
        try:
            self._lbl.configure(text=" optimizing" + "." * (self._dots % 4))
            self._dots += 1
            self._id = self.root.after(400, self._tick)
        except Exception:
            pass

    def close(self):
        try:
            if self._id:
                self.root.after_cancel(self._id)
            self._pb.stop()
            self.root.destroy()
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════════════════
# QUESTION POPUP — shown when the AI has a clarifying question
# ══════════════════════════════════════════════════════════════════════════════

class QuestionPopup:
    """Small floating window that shows the AI's question and lets the user
    type an answer.  The main KPrompter window is never shown.

    on_answer(str) is called with the user's reply when they submit.
    Dismissing without answering calls on_answer("").
    """

    _W = 480

    def __init__(self, parent, question_text: str, on_answer=None):
        self._on_answer = on_answer
        self._answered  = False

        self.root = tk.Toplevel(parent)
        self.root.title("KPrompter — Question")
        self.root.configure(bg=BG)
        self.root.resizable(False, False)
        self.root.attributes("-topmost", True)

        # ── Question label ────────────────────────────────────────────────────
        pad = tk.Frame(self.root, bg=BG)
        pad.pack(fill="both", expand=True, padx=18, pady=(16, 10))

        tk.Label(pad, text="K>  AI has a question:", bg=BG, fg=ACCENT,
                 font=(FONT_MONO[0], 9, "bold"), anchor="w").pack(fill="x")
        _spacer(pad, 6).pack()

        # Show the AI's question text (word-wrapped)
        q_label = tk.Label(pad, text=question_text,
                           bg=BG2, fg=TEXT,
                           font=FONT_UI, wraplength=self._W - 36,
                           justify="left", anchor="nw",
                           padx=10, pady=10)
        q_label.pack(fill="x")

        _spacer(pad, 10).pack()

        # ── Answer entry ──────────────────────────────────────────────────────
        tk.Label(pad, text="Your answer:", bg=BG, fg=TEXT_DIM,
                 font=FONT_UI_SM, anchor="w").pack(fill="x")
        _spacer(pad, 4).pack()

        # Multi-line Text widget: Enter=submit, Shift+Enter=newline
        self._text = tk.Text(pad, height=4, width=52,
                             bg=BG3, fg=TEXT, insertbackground=ACCENT,
                             relief="flat", bd=0, font=FONT_MONO,
                             highlightthickness=2, highlightbackground=BORDER,
                             highlightcolor=ACCENT, wrap="word",
                             padx=8, pady=6)
        self._text.pack(fill="x")
        self._text.focus_set()

        # Enter submits; Shift+Enter inserts a real newline
        self._text.bind("<Return>",       self._on_return)
        self._text.bind("<Shift-Return>", self._on_shift_return)

        _spacer(pad, 10).pack()

        # ── Buttons ───────────────────────────────────────────────────────────
        btn_row = tk.Frame(pad, bg=BG)
        btn_row.pack(anchor="e")

        _btn(btn_row, "Skip",   self._skip,   accent=False, small=True).pack(side="left", padx=(0, 6))
        _btn(btn_row, "Submit", self._submit, accent=True,  small=True).pack(side="left")

        self.root.bind("<Escape>",  lambda e: self._skip())
        self.root.protocol("WM_DELETE_WINDOW", self._skip)

        # ── Centre on screen ──────────────────────────────────────────────────
        self.root.update_idletasks()
        h = self.root.winfo_reqheight()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x  = (sw - self._W) // 2
        y  = (sh - h) // 3
        self.root.geometry(f"{self._W}x{h}+{x}+{y}")
        self.root.deiconify()

    def _on_return(self, event):
        """Enter alone submits."""
        self._submit()
        return "break"  # prevent the newline from being inserted

    def _on_shift_return(self, event):
        """Shift+Enter inserts a newline."""
        self._text.insert("insert", "\n")
        return "break"

    def _submit(self):
        if self._answered:
            return
        self._answered = True
        answer = self._text.get("1.0", "end-1c").strip()
        try:
            self.root.destroy()
        except Exception:
            pass
        if self._on_answer:
            self._on_answer(answer)

    def _skip(self):
        if self._answered:
            return
        self._answered = True
        try:
            self.root.destroy()
        except Exception:
            pass
        if self._on_answer:
            self._on_answer("")
