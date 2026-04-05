import json
import os
import platform
from pathlib import Path
from datetime import datetime

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

DEFAULT_SYSTEM_PROMPT_PATH = Path(__file__).parent / "prompts" / "default.txt"

DEFAULTS = {
    "provider": "openrouter",
    "api_key": "",
    "model": "mistralai/mistral-7b-instruct:free",
    "hotkey": "ctrl+alt+g",
    "logging_enabled": True,
    "log_max_entries": 100,
    "custom_system_prompt": None,
    "first_message_default": True,
}

PROVIDERS = {
    "openrouter": {
        "name": "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1",
        "default_model": "mistralai/mistral-7b-instruct:free",
        "free_models": [
            "mistralai/mistral-7b-instruct:free",
            "google/gemma-2-9b-it:free",
            "meta-llama/llama-3-8b-instruct:free",
        ],
        "key_url": "https://openrouter.ai/keys",
        "setup_tip": "Go to openrouter.ai → Keys → Create Key. Set a $0 credit limit to avoid any charges.",
    },
    "anthropic": {
        "name": "Anthropic",
        "base_url": "https://api.anthropic.com/v1",
        "default_model": "claude-3-haiku-20240307",
        "free_models": [],
        "key_url": "https://console.anthropic.com/settings/keys",
        "setup_tip": "Anthropic is a paid service. Set a spending limit in your account settings.",
    },
    "openai": {
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-3.5-turbo",
        "free_models": [],
        "key_url": "https://platform.openai.com/api-keys",
        "setup_tip": "OpenAI is a paid service. Set a usage limit under Billing → Limits.",
    },
    "gemini": {
        "name": "Google Gemini",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "default_model": "gemini-1.5-flash",
        "free_models": ["gemini-1.5-flash", "gemini-1.5-flash-8b"],
        "key_url": "https://aistudio.google.com/apikey",
        "setup_tip": "Get a free key at aistudio.google.com. Has free tier but set billing limits just in case.",
    },
    "ollama": {
        "name": "Ollama (Local)",
        "base_url": "http://localhost:11434/v1",
        "default_model": "llama3",
        "free_models": ["llama3", "mistral", "gemma2"],
        "key_url": "https://ollama.com/download",
        "setup_tip": "No API key needed. Install Ollama and run: ollama pull llama3",
    },
}


def load_config() -> dict:
    if not CONFIG_FILE.exists():
        return DEFAULTS.copy()
    try:
        with open(CONFIG_FILE) as f:
            data = json.load(f)
        cfg = DEFAULTS.copy()
        cfg.update(data)
        return cfg
    except Exception:
        return DEFAULTS.copy()


def save_config(cfg: dict):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)


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


def log_entry(entry: dict):
    cfg = load_config()
    if not cfg.get("logging_enabled", True):
        return
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
    with open(LOG_FILE, "w") as f:
        json.dump(logs, f, indent=2)


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
