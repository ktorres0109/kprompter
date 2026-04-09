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

# ── Modern Dark Palette ──────────────────────────────────────────────────────
BG        = "#0f1117"     # deep dark background
BG2       = "#161922"     # card / elevated surface
BG3       = "#1c2030"     # input fields
BG_HOVER  = "#222738"     # subtle hover
BORDER    = "#2a3045"     # borders
BORDER_F  = "#4a90e2"     # focused border
ACCENT    = "#4a90e2"     # primary blue accent
ACCENT_H  = "#3a7bd5"     # accent hover
ACCENT2   = "#22d3ee"     # secondary cyan accent
GREEN     = "#34d399"     # success green
GREEN_H   = "#2ab883"     # success hover
TEXT      = "#e4e8f1"     # primary text
TEXT_DIM  = "#6b7a99"     # secondary text
TEXT_MUTED= "#4a5568"     # muted / placeholder text
RED       = "#ef4444"     # error red
YELLOW    = "#f59e0b"     # warning yellow
ORANGE    = "#f97316"     # badges

_is_mac = SYSTEM == "Darwin"
_is_win = SYSTEM == "Windows"
FONT_MONO    = ("SF Mono", 11)      if _is_mac else ("Cascadia Code", 11)   if _is_win else ("JetBrains Mono", 11)
FONT_UI      = ("SF Pro Text", 11)  if _is_mac else ("Segoe UI", 11)        if _is_win else ("Inter", 11)
FONT_UI_SM   = (FONT_UI[0], 10)
FONT_UI_MED  = (FONT_UI[0], 12)
FONT_HEADING = (FONT_UI[0], 22, "bold")
FONT_SUB     = (FONT_UI[0], 14, "bold")
FONT_MONO_SM = (FONT_MONO[0], 10)
FONT_MONO_LG = (FONT_MONO[0], 14, "bold")

# Corner radius simulation via padding and frames
CARD_PAD = 16
CARD_IPADY = 12
CARD_IPADX = 16


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
    elif accent:
        bg, fg, hov = ACCENT, "#ffffff", ACCENT_H
    else:
        bg, fg, hov = BG3, TEXT, BG_HOVER
    font = (*FONT_UI[:2], "bold") if accent or danger else FONT_UI
    if small:
        font = FONT_UI_SM
    px = 10 if small else 18
    py = 4 if small else 8
    b = tk.Label(parent, text=text, bg=bg, fg=fg,
                 font=font, cursor="hand2",
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
        self._hotkey_var   = tk.StringVar(value=self.cfg.get("hotkey", "ctrl+alt+g"))
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
            has_free = any(m["free"] for m in info.get("models", []))
            badge_text = "FREE" if has_free else "PAID"
            badge_color = GREEN if has_free else ORANGE

            row = _card(self.container, pady=10, padx=14)
            row.pack(fill="x", pady=4)
            row.configure(cursor="hand2")

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
        provider = self._provider_var.get()
        self._header(3, "Pick a Model",
                     "FREE models cost nothing. PAID models bill your account.")

        _label(self.container, "Model").pack(anchor="w")
        _spacer(self.container, 6).pack()

        self._model_cb = _model_combobox(self.container, provider, self._model_var)
        self._model_cb.pack(anchor="w", fill="x")

        _spacer(self.container, 16).pack()

        best = get_best_model(provider)
        rec = _card(self.container, pady=12, padx=16)
        rec.pack(fill="x")
        tk.Label(rec, text="Recommended", bg=BG2, fg=TEXT_DIM,
                 font=FONT_UI_SM).pack(side="left")
        tk.Label(rec, text=best, bg=BG2, fg=GREEN,
                 font=FONT_MONO).pack(side="left", padx=10)

        _spacer(self.container, 10).pack()

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
        rec = "Cmd+Option+G recommended on macOS" if _is_mac else "Ctrl+Alt+G recommended"
        _sublabel(self.container, rec).pack(anchor="w")
        self._nav()

    def _reset_hotkey(self):
        d = "ctrl+cmd+g" if _is_mac else "ctrl+alt+g"
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
        self._pressed.add(e.keysym.lower())
        if hasattr(self, '_hotkey_display'):
            self._hotkey_display.configure(text="+".join(sorted(self._pressed)))

    def _on_key_release(self, e):
        if not self._recording:
            return
        if len(self._pressed) >= 2:
            combo = "+".join(sorted(self._pressed))
            self._hotkey_var.set(combo)
            if hasattr(self, '_rec_status'):
                self._rec_status.configure(text="Hotkey saved!", fg=GREEN)
            self._recording = False
            self.root.unbind("<KeyPress>")
            self.root.unbind("<KeyRelease>")
        self._pressed.discard(e.keysym.lower())

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
                  "Right-click the tray icon for settings anytime.").pack(anchor="w")

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
# RESULT / QUESTION POPUP
# ══════════════════════════════════════════════════════════════════════════════

class ResultPopup:
    def __init__(self, parent=None, text="", is_question=False, on_answer=None, original_text=""):
        if parent:
            self.root = tk.Toplevel(parent)
        else:
            self.root = tk.Toplevel()
        _style_root(self.root, "KPrompter", 660, 500 if is_question else 380, resizable=True)
        self.root.lift()
        self.root.attributes("-topmost", True)
        self.on_answer = on_answer
        self._build(text, is_question)

    def _build(self, text, is_question):
        root = self.root
        root.configure(bg=BG)

        # Header bar
        hdr = tk.Frame(root, bg=BG2, pady=10, padx=18)
        hdr.pack(fill="x")

        # Logo
        tk.Label(hdr, text="K>", bg=BG2, fg=ACCENT,
                 font=FONT_MONO_LG).pack(side="left")

        tag = "Clarification Needed" if is_question else "Prompt Optimized"
        tag_color = ACCENT2 if is_question else GREEN
        tk.Label(hdr, text=tag, bg=BG2, fg=tag_color,
                 font=(*FONT_UI[:2], "bold")).pack(side="left", padx=12)

        # Close button
        x_btn = tk.Label(hdr, text="✕", bg=BG2, fg=TEXT_DIM,
                         font=FONT_UI_MED, cursor="hand2", padx=6)
        x_btn.bind("<Button-1>", lambda e: root.destroy())
        x_btn.bind("<Enter>", lambda e: x_btn.configure(fg=RED))
        x_btn.bind("<Leave>", lambda e: x_btn.configure(fg=TEXT_DIM))
        x_btn.pack(side="right")

        # Body
        body = tk.Frame(root, bg=BG, padx=18, pady=14)
        body.pack(fill="both", expand=True)

        st = scrolledtext.ScrolledText(
            body, bg=BG3, fg=TEXT, font=FONT_MONO,
            relief="flat", bd=0, wrap="word",
            insertbackground=ACCENT,
            selectbackground=ACCENT, selectforeground="#ffffff",
            highlightthickness=2, highlightbackground=BORDER,
            highlightcolor=ACCENT,
            padx=12, pady=12,
        )
        st.insert("1.0", text)
        st.configure(state="normal" if is_question else "disabled")
        st.pack(fill="both", expand=True)
        self._st = st

        if is_question:
            _spacer(body, 10).pack()
            tk.Label(body, text="Your answer:", bg=BG, fg=TEXT,
                     font=(*FONT_UI[:2], "bold")).pack(anchor="w")
            _spacer(body, 4).pack()
            self._answer_box = tk.Text(
                body, bg=BG3, fg=TEXT, font=FONT_MONO, height=3,
                relief="flat", bd=0, insertbackground=ACCENT,
                highlightthickness=2, highlightbackground=BORDER,
                highlightcolor=ACCENT,
                padx=10, pady=8,
            )
            self._answer_box.pack(fill="x")

        # Footer
        ftr = tk.Frame(root, bg=BG2, padx=18, pady=10)
        ftr.pack(fill="x")

        if is_question:
            _btn(ftr, "Send Answer", self._send_answer).pack(side="right")
            _btn(ftr, "Cancel", root.destroy, accent=False).pack(side="right", padx=8)
        else:
            _btn(ftr, "Copy", self._copy, accent=False).pack(side="right")
            _btn(ftr, "Dismiss", root.destroy, accent=False).pack(side="right", padx=8)

    def _copy(self):
        text = self._st.get("1.0", "end").strip()
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
        except Exception:
            pass

    def _send_answer(self):
        if not hasattr(self, '_answer_box'):
            return
        answer = self._answer_box.get("1.0", "end").strip()
        if self.on_answer and answer:
            self.root.destroy()
            self.on_answer(answer)


# ══════════════════════════════════════════════════════════════════════════════
# SETTINGS WINDOW
# ══════════════════════════════════════════════════════════════════════════════

class SettingsWindow:
    def __init__(self, parent=None):
        if parent:
            self.root = tk.Toplevel(parent)
        else:
            self.root = tk.Toplevel()
        _style_root(self.root, "KPrompter — Settings", 700, 580, resizable=True)
        self.root.lift()
        self.root.attributes("-topmost", True)
        self.cfg = load_config()
        self._build()

    def _build(self):
        style = ttk.Style()
        if not _is_mac:
            style.theme_use("default")
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", background=BG2, foreground=TEXT_DIM,
                        font=FONT_UI, padding=[16, 8])
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
        pad = tk.Frame(f, bg=BG, padx=24, pady=20)
        pad.pack(fill="both", expand=True)
        return pad

    # ── General ───────────────────────────────────────────────────────────────
    def _tab_general(self, nb):
        pad = self._pad(nb, "General")

        # Section header
        tk.Label(pad, text="Hotkey Configuration", bg=BG, fg=TEXT,
                 font=FONT_SUB).pack(anchor="w")
        _spacer(pad, 8).pack()

        _label(pad, "Keyboard shortcut").pack(anchor="w")
        _spacer(pad, 4).pack()
        hk_var = tk.StringVar(value=self.cfg.get("hotkey", "ctrl+alt+g"))
        _entry(pad, textvariable=hk_var).pack(anchor="w", ipady=7)
        _spacer(pad, 6).pack()
        _sublabel(pad, "Restart KPrompter after changing the hotkey.").pack(anchor="w")

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
            self.cfg["hotkey"] = hk_var.get()
            self.cfg["logging_enabled"] = log_var.get()
            try:
                self.cfg["log_max_entries"] = int(log_n_var.get())
            except ValueError:
                pass
            save_config(self.cfg)
            messagebox.showinfo("KPrompter", "Settings saved. Restart to apply hotkey changes.")
        _btn(pad, "Save Settings", save).pack(anchor="w")

    # ── Provider ─────────────────────────────────────────────────────────────
    def _tab_provider(self, nb):
        pad = self._pad(nb, "Provider")
        prov_var = tk.StringVar(value=self.cfg.get("provider", "openrouter"))
        model_var = tk.StringVar(value=self.cfg.get("model", ""))
        _model_cb_ref = [None]

        tk.Label(pad, text="AI Provider", bg=BG, fg=TEXT,
                 font=FONT_SUB).pack(anchor="w")
        _spacer(pad, 8).pack()

        prov_opts = {k: v["name"] for k, v in PROVIDERS.items()}
        prov_frame = tk.Frame(pad, bg=BG)
        prov_frame.pack(anchor="w")
        for key, name in prov_opts.items():
            tk.Radiobutton(prov_frame, text=name, variable=prov_var, value=key,
                           bg=BG, fg=TEXT, selectcolor=BG3,
                           activebackground=BG, activeforeground=TEXT,
                           font=FONT_UI, highlightthickness=0).pack(side="left", padx=6)

        _spacer(pad, 14).pack()
        _divider(pad).pack(fill="x")
        _spacer(pad, 14).pack()

        tk.Label(pad, text="API Key", bg=BG, fg=TEXT,
                 font=FONT_SUB).pack(anchor="w")
        _spacer(pad, 6).pack()
        key_var = tk.StringVar(value=self.cfg.get("api_key", ""))
        key_entry = _entry(pad, textvariable=key_var, show="*", width=48)
        key_entry.pack(anchor="w", ipady=7)

        _spacer(pad, 14).pack()
        _divider(pad).pack(fill="x")
        _spacer(pad, 14).pack()

        tk.Label(pad, text="Model", bg=BG, fg=TEXT,
                 font=FONT_SUB).pack(anchor="w")
        _spacer(pad, 6).pack()

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

        _spacer(pad, 18).pack()

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
        _btn(pad, "Save Provider", save).pack(anchor="w")

    # ── System Prompt ─────────────────────────────────────────────────────────
    def _tab_prompt(self, nb):
        pad = self._pad(nb, "System Prompt")

        tk.Label(pad, text="System Prompt", bg=BG, fg=TEXT,
                 font=FONT_SUB).pack(anchor="w")
        _spacer(pad, 4).pack()
        _sublabel(pad, "Edit the optimizer prompt. Reset to restore the default.").pack(anchor="w")
        _spacer(pad, 10).pack()

        st = scrolledtext.ScrolledText(
            pad, bg=BG3, fg=TEXT, font=FONT_MONO_SM,
            relief="flat", bd=0, wrap="word",
            insertbackground=ACCENT,
            highlightthickness=2, highlightbackground=BORDER,
            highlightcolor=ACCENT,
            padx=10, pady=10, height=14,
        )
        st.insert("1.0", get_system_prompt())
        st.pack(fill="both", expand=True)
        _spacer(pad, 12).pack()

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

        tk.Label(pad, text="Session Log", bg=BG, fg=TEXT,
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
        _btn(pad, "Clear Log", do_clear, danger=True).pack(anchor="w")


# ══════════════════════════════════════════════════════════════════════════════
# LOADING SPINNER
# ══════════════════════════════════════════════════════════════════════════════

class LoadingPopup:
    def __init__(self, parent=None):
        if parent:
            self.root = tk.Toplevel(parent)
        else:
            self.root = tk.Toplevel()
        _style_root(self.root, "KPrompter", 280, 90)
        self.root.attributes("-topmost", True)
        self.root.overrideredirect(True)

        inner = tk.Frame(self.root, bg=BG2, highlightthickness=1,
                         highlightbackground=BORDER)
        inner.pack(fill="both", expand=True)

        self._lbl = tk.Label(inner, text="K>  Optimizing",
                             bg=BG2, fg=ACCENT,
                             font=FONT_MONO_LG)
        self._lbl.pack(expand=True)
        self._dots = 0
        self._id = None
        self._tick()

    def _tick(self):
        try:
            dots = "." * (self._dots % 4)
            self._lbl.configure(text=f"K>  Optimizing{dots}")
            self._dots += 1
            self._id = self.root.after(350, self._tick)
        except Exception:
            pass

    def close(self):
        try:
            if self._id:
                self.root.after_cancel(self._id)
            self.root.destroy()
        except Exception:
            pass
