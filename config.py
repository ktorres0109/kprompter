import json
import os
import sys
import platform
import threading
import tempfile
from pathlib import Path
from datetime import datetime

try:
    import requests
except ImportError:
    requests = None

try:
    import keyring as _keyring
except ImportError:
    _keyring = None

KEYCHAIN_SERVICE = "KPrompter"


def get_api_key(provider: str) -> str:
    """Retrieve API key for the given provider from macOS Keychain."""
    if not _keyring or not provider:
        return ""
    try:
        return _keyring.get_password(KEYCHAIN_SERVICE, provider) or ""
    except Exception:
        return ""


def save_api_key(provider: str, key: str):
    """Store API key in macOS Keychain — never written to config.json."""
    if not _keyring or not provider:
        return
    try:
        if key:
            _keyring.set_password(KEYCHAIN_SERVICE, provider, key)
        else:
            try:
                _keyring.delete_password(KEYCHAIN_SERVICE, provider)
            except Exception:
                pass
    except Exception:
        pass

_DEBUG = os.environ.get("KP_DEBUG") == "1"


def _dbg(msg: str):
    if _DEBUG:
        with open("/tmp/kp_debug.log", "a") as _f:
            _f.write(msg + "\n")


def get_bundle_dir() -> Path:
    """Return the base directory for bundled resources.

    Inside a PyInstaller bundle (frozen app), data files added via
    ``--add-data`` live under ``sys._MEIPASS``.  In a normal Python
    environment, fall back to the directory containing this file.
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).parent


def get_config_dir() -> Path:
    system = platform.system()
    if system == "Windows":
        base = Path(os.environ.get("APPDATA", Path.home()))
    elif system == "Darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    d = base / "KPrompter"
    d.mkdir(parents=True, exist_ok=True)
    return d

CONFIG_DIR = get_config_dir()
CONFIG_FILE = CONFIG_DIR / "config.json"
LOG_FILE = CONFIG_DIR / "session_log.json"
PROMPT_FILE = CONFIG_DIR / "system_prompt.txt"
INSTRUCTIONS_FILE = CONFIG_DIR / "custom_instructions.txt"
DEFAULT_SYSTEM_PROMPT_PATH = get_bundle_dir() / "prompts" / "default.txt"

DEFAULTS = {
    "provider": "openrouter",
    "model": "meta-llama/llama-3.3-70b-instruct:free",
    "hotkey": "cmd+option+k" if platform.system() == "Darwin" else "ctrl+alt+k",
    "logging_enabled": True,
    "log_max_entries": 100,
    "custom_system_prompt": None,
    "first_message_default": True,
    "ollama_url": "http://localhost:11434",
}


# Each provider has: name, base_url, models list (label, id, free?), best_free, key_url, setup_tip
PROVIDERS = {
    "openrouter": {
        "name": "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1",
        "best_free": "google/gemini-2.5-flash-preview:free",
        "models": [
            {"label": "Gemini 2.5 Flash Preview (free)", "id": "google/gemini-2.5-flash-preview:free",              "free": True},
            {"label": "Llama 4 Maverick (free)",       "id": "meta-llama/llama-4-maverick:free",                  "free": True},
            {"label": "Llama 4 Scout (free)",          "id": "meta-llama/llama-4-scout:free",                     "free": True},
            {"label": "DeepSeek V3 (free)",            "id": "deepseek/deepseek-chat-v3-0324:free",               "free": True},
            {"label": "DeepSeek R1 Zero (free)",       "id": "deepseek/deepseek-r1-zero:free",                    "free": True},
            {"label": "Mistral Small 3.1 24B (free)",  "id": "mistralai/mistral-small-3.1-24b-instruct:free",     "free": True},
            {"label": "Qwen3 Coder 480B (free)",       "id": "qwen/qwen3-coder:free",                             "free": True},
            {"label": "GPT-4o Mini",                   "id": "openai/gpt-4o-mini",                                "free": False},
            {"label": "Claude Haiku 4.5",              "id": "anthropic/claude-haiku-4-5",                        "free": False},
            {"label": "Claude Sonnet 4.6",             "id": "anthropic/claude-sonnet-4-6",                       "free": False},
        ],
        "key_url": "https://openrouter.ai/keys",
        "setup_tip": "Recommended. Set a $0 credit limit to block paid models entirely.",
    },
    "anthropic": {
        "name": "Anthropic",
        "base_url": "https://api.anthropic.com/v1",
        "best_free": "claude-haiku-4-5-20251001",
        "models": [
            {"label": "Claude Haiku 4.5 (cheapest)",   "id": "claude-haiku-4-5-20251001", "free": False},
            {"label": "Claude Sonnet 4.6",             "id": "claude-sonnet-4-6",         "free": False},
            {"label": "Claude Opus 4.6",               "id": "claude-opus-4-6",           "free": False},
        ],
        "key_url": "https://console.anthropic.com/settings/keys",
        "setup_tip": "Paid service. Set a spending limit under Account → Billing.",
    },
    "openai": {
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "best_free": "gpt-4o-mini",
        "models": [
            {"label": "GPT-4o Mini (cheapest)",   "id": "gpt-4o-mini",    "free": False},
            {"label": "GPT-4o",                   "id": "gpt-4o",         "free": False},
            {"label": "o4-mini",                  "id": "o4-mini",        "free": False},
        ],
        "key_url": "https://platform.openai.com/api-keys",
        "setup_tip": "Paid service. Set a usage limit under Billing → Limits.",
    },
    "gemini": {
        "name": "Google Gemini",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "best_free": "gemini-2.5-flash",
        "models": [
            {"label": "Gemini 2.5 Flash (free tier)",   "id": "gemini-2.5-flash",        "free": True},
            {"label": "Gemini 2.0 Flash (free tier)",   "id": "gemini-2.0-flash",        "free": True},
            {"label": "Gemini 2.0 Flash Lite",          "id": "gemini-2.0-flash-lite",   "free": True},
            {"label": "Gemini 1.5 Flash",               "id": "gemini-1.5-flash",        "free": True},
            {"label": "Gemini 1.5 Pro",                 "id": "gemini-1.5-pro",          "free": False},
        ],
        "key_url": "https://aistudio.google.com/apikey",
        "setup_tip": "Get a free key at aistudio.google.com. Set billing limits just in case.",
    },
    "ollama": {
        "name": "Ollama",
        "base_url": "http://localhost:11434/v1",
        "best_free": "",
        "is_free": True,       # no API key, no billing — always free
        "models": [],          # populated at runtime via fetch_ollama_models()
        "key_url": "https://ollama.com/download",
        "setup_tip": "No API key needed. Models are fetched from your running Ollama instance.",
    },
}


_openrouter_fetched = False
_openrouter_lock = threading.Lock()

def _fetch_openrouter_models_sync():
    """Fetch live free models from OpenRouter (called from background thread)."""
    global _openrouter_fetched
    if not requests or _openrouter_fetched:
        return
    with _openrouter_lock:
        if _openrouter_fetched:
            return
        try:
            response = requests.get("https://openrouter.ai/api/v1/models", timeout=5)
            data = response.json().get('data', [])
            free_models = [m['id'] for m in data if m.get('pricing', {}).get('prompt', "-1") == "0"]
            if free_models:
                current_ids = {m["id"] for m in PROVIDERS["openrouter"]["models"]}
                for mid in reversed(free_models):
                    if mid not in current_ids:
                        name_parts = mid.split("/")[-1].replace("-", " ").title()
                        label = f"{name_parts} (free live)"
                        PROVIDERS["openrouter"]["models"].insert(0, {"label": label, "id": mid, "free": True})
            _openrouter_fetched = True
        except Exception:
            _openrouter_fetched = True  # Don't retry on failure


def start_openrouter_fetch():
    """Kick off the OpenRouter model fetch in a background thread so the UI
    doesn't freeze.  Safe to call multiple times; subsequent calls are no-ops."""
    if _openrouter_fetched:
        return
    threading.Thread(target=_fetch_openrouter_models_sync, daemon=True).start()


def fetch_gemini_models(api_key: str) -> list:
    """Fetch available Gemini models via the REST API using the provided key.

    Returns a list of model-ID strings (e.g. ['gemini-2.0-flash', ...]) sorted
    alphabetically.  Only models that support generateContent are returned.
    Returns an empty list on any error.
    """
    if not requests or not api_key:
        return []
    try:
        resp = requests.get(
            "https://generativelanguage.googleapis.com/v1beta/models",
            params={"key": api_key},
            timeout=6,
        )
        resp.raise_for_status()
        models = []
        for m in resp.json().get("models", []):
            name = m.get("name", "")                           # "models/gemini-2.0-flash"
            methods = m.get("supportedGenerationMethods", [])
            if "generateContent" in methods and "gemini" in name.lower():
                model_id = name.removeprefix("models/")        # "gemini-2.0-flash"
                models.append(model_id)
        return sorted(models)
    except Exception:
        return []


def fetch_ollama_models(base_url: str = None) -> list:
    """Return list of model name strings from the running Ollama instance.

    Hits GET <base_url>/api/tags — the native Ollama endpoint (not /v1).
    Returns an empty list if Ollama is not running or unreachable.
    """
    if not requests:
        return []
    if base_url is None:
        base_url = load_config().get("ollama_url", "http://localhost:11434")
    url = base_url.rstrip("/") + "/api/tags"
    try:
        resp = requests.get(url, timeout=3)
        resp.raise_for_status()
        data = resp.json()
        return [m["name"] for m in data.get("models", [])]
    except Exception:
        return []


def get_best_model(provider: str) -> str:
    return PROVIDERS.get(provider, {}).get("best_free", "")


def get_model_labels(provider: str) -> list:
    """Returns list of (label, model_id, is_free) tuples for UI dropdowns."""
    if provider == "openrouter" and not _openrouter_fetched:
        # Start a background fetch instead of blocking the UI thread.
        # Return the built-in model list immediately; the combobox can be
        # refreshed later once the fetch completes.
        start_openrouter_fetch()
    return [(m["label"], m["id"], m["free"]) for m in PROVIDERS.get(provider, {}).get("models", [])]


_OPT_CHAR_FIXES = {
    "©": "g", "®": "r", "ß": "s", "∂": "d", "ƒ": "f",
    "å": "a", "∫": "b", "ç": "c", "˙": "h", "∆": "j",
    "˚": "k", "¬": "l", "µ": "m", "ø": "o", "π": "p",
    "œ": "q", "†": "t", "√": "v", "∑": "w", "≈": "x",
    "¥": "y", "ω": "z", "Ω": "z",
}


def _normalize_hotkey(hotkey: str) -> str:
    """Replace any macOS Option-key characters in a hotkey string with the base key."""
    return "+".join(_OPT_CHAR_FIXES.get(p, p) for p in hotkey.split("+"))


def load_config() -> dict:
    if not CONFIG_FILE.exists():
        return DEFAULTS.copy()
    try:
        with open(CONFIG_FILE) as f:
            data = json.load(f)
        cfg = DEFAULTS.copy()
        cfg.update(data)
        # Auto-fix any stored Option-key characters in the hotkey
        if "hotkey" in cfg:
            cfg["hotkey"] = _normalize_hotkey(cfg["hotkey"])
        # One-time migration: move legacy plain-text api_key to Keychain
        if "api_key" in cfg:
            legacy_key = cfg.pop("api_key")
            if legacy_key:
                provider = cfg.get("provider", "openrouter")
                if not get_api_key(provider):
                    save_api_key(provider, legacy_key)
            # Write back without the api_key field
            try:
                _atomic_write_json(CONFIG_FILE, {k: v for k, v in cfg.items() if k != "api_key"})
            except Exception:
                pass
        return cfg
    except Exception:
        return DEFAULTS.copy()



def _atomic_write_json(file_path, data):
    dir_name = os.path.dirname(file_path)
    fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
    with os.fdopen(fd, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp_path, file_path)

def save_config(cfg: dict):
    try:
        _atomic_write_json(CONFIG_FILE, cfg)
    except Exception:
        pass  # better safe than crash if permissions issue



def get_system_prompt() -> str:
    cfg = load_config()
    if cfg.get("custom_system_prompt"):
        return cfg["custom_system_prompt"]
    if PROMPT_FILE.exists():
        return PROMPT_FILE.read_text(encoding="utf-8")
    if DEFAULT_SYSTEM_PROMPT_PATH.exists():
        return DEFAULT_SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    return ""


def save_custom_prompt(text: str):
    cfg = load_config()
    cfg["custom_system_prompt"] = text
    save_config(cfg)


def reset_prompt_to_default():
    cfg = load_config()
    cfg["custom_system_prompt"] = None
    save_config(cfg)
    if PROMPT_FILE.exists():
        PROMPT_FILE.unlink()


def get_custom_instructions() -> str:
    try:
        return INSTRUCTIONS_FILE.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return ""


def save_custom_instructions(text: str):
    INSTRUCTIONS_FILE.write_text(text.strip(), encoding="utf-8")



_log_lock = threading.Lock()

def log_entry(entry: dict):
    cfg = load_config()
    if not cfg.get("logging_enabled", True):
        return
    with _log_lock:
        max_entries = cfg.get("log_max_entries", 100)
        logs = []
        if LOG_FILE.exists():
            try:
                with open(LOG_FILE) as f:
                    logs = json.load(f)
            except Exception:
                logs = []
        entry["timestamp"] = datetime.now().isoformat()
        logs.append(entry)
        if len(logs) > max_entries:
            logs = logs[-max_entries:]
        try:
            _atomic_write_json(LOG_FILE, logs)
        except Exception:
            pass



def load_log() -> list:
    if not LOG_FILE.exists():
        return []
    try:
        with open(LOG_FILE) as f:
            return json.load(f)
    except Exception:
        return []


def clear_log():
    if LOG_FILE.exists():
        LOG_FILE.unlink()


def is_first_run() -> bool:
    return not CONFIG_FILE.exists()
