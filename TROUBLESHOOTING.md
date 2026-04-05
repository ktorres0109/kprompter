# Troubleshooting KPrompter

## macOS: "App can't be opened because it's from an unidentified developer"

This happens because the app isn't notarized with Apple yet. Two ways to fix it:

**Option A — Right-click method (easiest):**
1. In Finder, right-click (or Control+click) `KPrompter.app`
2. Click **Open** from the menu
3. Click **Open** again in the dialog
4. Done — macOS remembers this and won't ask again

**Option B — Terminal (one command):**
```bash
xattr -cr /Applications/KPrompter.app
```
Then open normally.

---

## macOS: Hotkey does nothing / doesn't fire

KPrompter needs Accessibility permission to listen for global hotkeys.

1. Open **System Settings → Privacy & Security → Accessibility**
2. Click the **+** button
3. Add **Terminal** (if running from source) or **KPrompter** (if using the .app)
4. Toggle it on
5. Restart KPrompter

If you already added it and it still doesn't work, try removing it and re-adding it — macOS sometimes caches stale permissions.

---

## macOS: Nothing pastes after optimization

Same as above — System Events (used for paste) also needs Accessibility.
Check that whichever app you're typing in isn't blocking programmatic input (some secure password fields do this by design).

---

## All platforms: "API error 401 / Unauthorized"

Your API key is wrong or expired.
- Go to Settings → Provider → re-paste your API key
- Make sure there are no leading/trailing spaces in the key

## All platforms: "API error 429 / Rate limited"

You've hit the free tier limit for the day.
- Switch to a different free model in Settings → Provider → Model
- Or wait until the limit resets (usually midnight UTC)

---

## Ollama: Connection refused

Make sure Ollama is running:
```bash
ollama serve
```
And that you've pulled a model:
```bash
ollama pull llama3
```

---

## Still broken?

Open an issue at https://github.com/ktorres0109/kprompter/issues
Include your OS, Python version (`python3 --version`), and the error message.
