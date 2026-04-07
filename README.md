# K> KPrompter

**Turn rough text into AI-ready prompts — instantly, with one hotkey.**

KPrompter sits in your system tray and watches for your hotkey. Select any text, press it, and KPrompter rewrites it into a structured, token-efficient prompt — then pastes it back in place. Works with any app, any AI.

---

## What it does

Most people type rough, vague prompts. KPrompter turns those into structured prompts that actually work:

| Before | After |
|--------|-------|
| `fix my login bug` | Role + context + task + constraints + verify step |
| `explain recursion` | Tutor-style prompt with check questions and format spec |
| `write me a script` | Full scoped prompt with requirements, style, output format |

It also knows when you're mid-project. First message? Full setup. Continuing? Just the delta — no wasted tokens.

---

## Quick Install

### macOS (Homebrew) - Recommended

The easiest way to install on macOS without getting Apple's Gatekeeper "app is damaged" warnings is to use Homebrew:

```bash
brew install --cask https://raw.githubusercontent.com/ktorres0109/kprompter/main/Casks/kprompter.rb
```

### macOS (Manual Install)

1. Download `KPrompter.dmg` from the [latest release](https://github.com/ktorres0109/kprompter/releases/latest)
2. Double-click the `.dmg` file to mount it
3. Drag `KPrompter.app` to your **Applications** folder
4. **First launch only:** right-click (or Control-click) `KPrompter.app` → click **Open** → click **Open** again in the dialog

> macOS blocks apps from unknown developers by default. Right-click → Open bypasses this once. After that, double-click works normally.

### macOS / Linux (from source)

```bash
curl -sSL https://raw.githubusercontent.com/ktorres0109/kprompter/main/install.sh | bash
```

Then run:

```bash
kprompter
```

### Windows (PowerShell)

```powershell
irm https://raw.githubusercontent.com/ktorres0109/kprompter/main/install.ps1 | iex
```

Then run:

```
kprompter
```

### Manual install (all platforms)

Requirements: Python 3.9+

```bash
git clone https://github.com/ktorres0109/kprompter
cd kprompter
python -m venv .venv

# macOS/Linux:
source .venv/bin/activate

# Windows:
.venv\Scripts\activate

pip install -r requirements.txt
python main.py
```

---

## First Run — Setup Wizard

On first launch, KPrompter walks you through a 4-step setup:

1. **Welcome** — overview of what KPrompter does
2. **Provider** — pick your AI backend (see options below)
3. **API Key** — paste your key; free models highlighted
4. **Hotkey** — record your key combo by pressing it live

The wizard shows free vs paid badges for each provider and links directly to billing limit pages so you don't get surprised by charges.

After setup, KPrompter runs in the background via a system tray icon.

---

## Supported Providers

| Provider | Free option | Needs key | Notes |
|----------|-------------|-----------|-------|
| **OpenRouter** (default) | Yes — free models available | Yes | Recommended. Set a $0 credit limit. |
| **Ollama** | Yes — fully local | No | No billing risk. Requires local model. |
| **Anthropic** | No | Yes | Claude models. Set a spending limit. |
| **OpenAI** | No | Yes | GPT models. Set a usage limit. |
| **Gemini** | Yes (limited) | Yes | Google AI Studio key. |

### Recommended: OpenRouter (free tier)

1. Go to [openrouter.ai](https://openrouter.ai) → create an account
2. Go to **Settings → Credits → Set a $0 limit** (blocks paid models entirely)
3. Go to **Keys → Create API Key** → paste into KPrompter settings

Free models available on OpenRouter include:
- `mistralai/mistral-7b-instruct:free`
- `meta-llama/llama-3-8b-instruct:free`
- `google/gemma-2-9b-it:free`

### Alternative: Ollama (zero risk, fully local)

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull a model
ollama pull llama3

# Start Ollama (usually auto-starts)
ollama serve
```

Then set provider to `ollama` in KPrompter settings. No API key needed.

---

## Usage

### Basic flow

1. Select any text in any app
2. Press your hotkey (default: `Ctrl+Alt+G` / `Cmd+Option+G` on macOS)
3. KPrompter asks: **first message or continuing?**
   - **First message** → adds role, context, format, constraints
   - **Continuing** → outputs only the next instruction (no repeated setup)
4. If KPrompter needs clarification, a popup appears with questions — answer them
5. The optimized prompt replaces your selected text

### First message vs. continuation mode

This is the key to token efficiency.

**First message** — full structured prompt:
```
Role: You are a senior Python engineer.
Context: Working on a Flask REST API with SQLAlchemy.
Objective: Add rate limiting to the /login endpoint.
Constraints: Use flask-limiter. No changes to existing auth logic.
Output: Short plan (3-5 bullets), then minimal code diff.
Quality check: Confirm the limiter resets correctly on success.
```

**Continuation** — just the delta:
```
Now add the same rate limiting to /register. Reuse the same limiter instance.
```

No repeated role, no repeated context — just what changed.

---

## Changing Settings

Right-click the tray icon → **Settings**. Everything is configurable without editing files:

| Tab | What you can change |
|-----|---------------------|
| General | Hotkey, logging on/off, max log entries |
| Provider | Switch provider, API key, model |
| System Prompt | Edit or reset the optimizer prompt |
| Session Log | View or clear the log |

### Switching providers mid-use

1. Right-click tray → Settings → Provider tab
2. Change provider and paste new API key
3. Click Save — no restart needed

---

## System Prompt

The default system prompt tells KPrompter to:

- Detect task type (coding, math, writing, analysis)
- Ask 1–3 clarifying questions before optimizing if anything is ambiguous
- Apply KERNEL structure (Role / Context / Objective / Constraints / Format / Quality check)
- Use Claude Code workflow for coding tasks (Explore → Plan → Implement → Verify)
- Strip filler, fix typos, deduplicate rules
- Respect first-message vs. continuation mode

You can edit this freely in Settings → System Prompt. A reset button restores the default.

---

## Session Log

KPrompter keeps a lightweight log of each optimization run:

```json
{
  "timestamp": "2024-01-15T14:23:01",
  "provider": "openrouter",
  "model": "mistralai/mistral-7b-instruct:free",
  "mode": "first",
  "input_chars": 42,
  "output_chars": 380
}
```

No prompt content is stored — only metadata. The log is capped at your configured max entries (default: 100) so it never grows unbounded.

Disable logging: Settings → General → uncheck "Enable session logging".

View log location: listed in Settings → Session Log tab.

---

## File Locations

| Platform | Config dir |
|----------|-----------|
| macOS | `~/Library/Application Support/KPrompter/` |
| Linux | `~/.config/KPrompter/` |
| Windows | `%APPDATA%\KPrompter\` |

Files:

| File | Purpose |
|------|---------|
| `config.json` | All settings |
| `session_log.json` | Usage log (metadata only) |
| `system_prompt.txt` | Custom system prompt (if set) |

---

## Autostart

### macOS

System Settings → General → Login Items → Add KPrompter (or the `kprompter` launcher script).

### Linux

Add to your desktop autostart:

```bash
cp ~/.local/share/applications/kprompter.desktop ~/.config/autostart/
```

Or add to your shell profile:

```bash
echo 'kprompter &' >> ~/.bashrc
```

### Windows

Press `Win+R` → type `shell:startup` → create a shortcut to `kprompter.bat`.

---

## Hotkeys by Platform

| Platform | Recommended | Why |
|----------|-------------|-----|
| macOS | `Cmd+Option+G` | No known conflicts |
| Linux | `Ctrl+Alt+G` | No known conflicts |
| Windows | `Ctrl+Alt+G` | No known conflicts |

You can set any combo during setup or change it later in Settings → General.

---

## Troubleshooting

**"KPrompter is damaged" or "cannot be opened" on macOS**

This error typically occurs when downloading apps from outside the App Store or if the app's signature needs to be verified. Fix it in one step using Terminal:

```bash
xattr -cr /Applications/KPrompter.app
```

Alternatively, you can right-click (or Control-click) the app in your Applications folder → click **Open** → click **Open** again in the dialog to bypass Gatekeeper. This only needs to be done once.

---

**Hotkey not working on Linux**

```bash
# Install xdotool (required for clipboard on some systems)
sudo apt install xdotool xclip   # Debian/Ubuntu
sudo pacman -S xdotool xclip     # Arch
```

**Hotkey not working on macOS**

KPrompter needs Accessibility permissions:
System Settings → Privacy & Security → Accessibility → enable KPrompter (or Terminal if running from source)

**Nothing pastes back**

Check that your app allows programmatic paste. Some password managers and secure inputs block it by design.

**API errors**

- Check your API key in Settings → Provider
- If using OpenRouter: confirm the model name is correct (use the `Fill Default Model` button)
- If using Ollama: confirm `ollama serve` is running (`curl http://localhost:11434/`)

**Tray icon missing on Linux**

Install a system tray extension for your desktop environment:

- GNOME: install `gnome-shell-extension-appindicator`
- KDE: works out of the box

---

## Building from Source

### Generating the icon

```bash
python icon_gen.py
# Writes: assets/icon.svg and assets/icon.png
```

For best quality, install `cairosvg`:

```bash
pip install cairosvg
python icon_gen.py
```

### Running in development

```bash
python main.py
```

### Packaging with PyInstaller

```bash
pip install pyinstaller

# macOS
pyinstaller --onefile --windowed --icon assets/icon.png --name KPrompter main.py

# Linux
pyinstaller --onefile --icon assets/icon.png --name KPrompter main.py

# Windows
pyinstaller --onefile --windowed --icon assets/icon.ico --name KPrompter main.py
```

Output is in `dist/`.

---

## Project Structure

```
kprompter/
├── main.py           # Entry point, hotkey loop, orchestration
├── gui.py            # All windows: setup wizard, popups, settings
├── optimizer.py      # API calls to all providers
├── clipboard.py      # Cross-platform grab + paste
├── config.py         # Config, log, system prompt management
├── tray.py           # System tray icon and menu
├── icon_gen.py       # SVG/PNG icon generator (no external deps needed)
├── install.sh        # macOS/Linux one-liner installer
├── install.ps1       # Windows one-liner installer
├── requirements.txt
├── assets/
│   ├── icon.svg
│   └── icon.png
└── prompts/
    └── default.txt   # Default system prompt
```

---

## Privacy

- Your text is sent to whichever AI provider you configure
- KPrompter does not store prompt content anywhere — only metadata (char count, provider, timestamp)
- The session log can be disabled or cleared at any time
- No telemetry, no analytics, no external calls except to your chosen provider

---

## Contributing

PRs welcome. A few guidelines:

- Keep the UI clean — no feature creep on the tray menu
- New providers: add to `PROVIDERS` dict in `config.py`, handle in `optimizer.py`
- Don't break the no-restart-required settings flow

---

## License

MIT — do whatever you want, just don't remove attribution.

---

## Credits

Built by [Kelvin Salinas](https://github.com/ktorres0109). Powered by your AI of choice.
