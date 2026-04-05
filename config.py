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
    "model": "meta-llama/llama-3.3-70b-instruct:free",
    "hotkey": "ctrl+alt+g",
    "logging_enabled": True,
    "log_max_entries": 100,
    "custom_system_prompt": None,
    "first_message_default": True,
}


# Each provider has: name, base_url, models list (label, id, free?), best_free, key_url, setup_tip
PROVIDERS = {
    "openrouter": {
        "name": "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1",
        "best_free": "meta-llama/llama-3.3-70b-instruct:free",
        "models": [
            {"label": "Llama 3.3 70B (free)",          "id": "meta-llama/llama-3.3-70b-instruct:free",            "free": True},
            {"label": "Llama 4 Maverick (free)",        "id": "meta-llama/llama-4-maverick:free",                  "free": True},
            {"label": "Llama 4 Scout (free)",           "id": "meta-llama/llama-4-scout:free",                     "free": True},
            {"label": "DeepSeek V3 (free)",             "id": "deepseek/deepseek-chat-v3-0324:free",               "free": True},
            {"label": "DeepSeek R1 Zero (free)",        "id": "deepseek/deepseek-r1-zero:free",                    "free": True},
            {"label": "Mistral Small 3.1 24B (free)",   "id": "mistralai/mistral-small-3.1-24b-instruct:free",     "free": True},
            {"label": "Qwen3 Coder 480B (free)",        "id": "qwen/qwen3-coder:free",                             "free": True},
            {"label": "Gemini 2.5 Pro Exp (free)",      "id": "google/gemini-2.5-pro-exp-03-25:free",              "free": True},
            {"label": "GPT-4o mini",                    "id": "openai/gpt-4o-mini",                                "free": False},
            {"label": "GPT-4o",                         "id": "openai/gpt-4o",                                     "free": False},
            {"label": "Claude Haiku 4.5",               "id": "anthropic/claude-haiku-4-5",                        "free": False},
            {"label": "Claude Sonnet 4.6",              "id": "anthropic/claude-sonnet-4-6",                       "free": False},
            {"label": "Gemini 2.5 Flash",               "id": "google/gemini-2.5-flash",                           "free": False},
        ],
        "key_url": "https://openrouter.ai/keys",
        "setup_tip": "Recommended. Set a $0 credit limit to block paid models entirely.",
    },
    "anthropic": {
        "name": "Anthropic",
        "base_url": "https://api.anthropic.com/v1",
        "best_free": "claude-haiku-4-5-20251001",
        "models": [
            {"label": "Claude Haiku 4.5 (cheapest)",   "id": "claude-haiku-4-5-20251001",   "free": False},
            {"label": "Claude Sonnet 4.6",             "id": "claude-sonnet-4-6",            "free": False},
            {"label": "Claude Opus 4.6",               "id": "claude-opus-4-6",              "free": False},
        ],
        "key_url": "https://console.anthropic.com/settings/keys",
        "setup_tip": "Paid service. Set a spending limit under Account → Billing.",
    },
    "openai": {
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "best_free": "gpt-4o-mini",
        "models": [
            {"label": "GPT-4o mini (cheapest)",   "id": "gpt-4o-mini",    "free": False},
            {"label": "GPT-4.1 mini",             "id": "gpt-4.1-mini",   "free": False},
            {"label": "GPT-4o",                   "id": "gpt-4o",         "free": False},
            {"label": "GPT-4.1",                  "id": "gpt-4.1",        "free": False},
            {"label": "o3 mini",                  "id": "o3-mini",        "free": False},
            {"label": "o4 mini",                  "id": "o4-mini",        "free": False},
        ],
        "key_url": "https://platform.openai.com/api-keys",
        "setup_tip": "Paid service. Set a usage limit under Billing → Limits.",
    },
    "gemini": {
        "name": "Google Gemini",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "best_free": "gemini-2.5-flash",
        "models": [
            {"label": "Gemini 2.5 Flash (free tier)",     "id": "gemini-2.5-flash",       "free": True},
            {"label": "Gemini 2.5 Flash Lite (free tier)","id": "gemini-2.5-flash-lite",  "free": True},
            {"label": "Gemini 2.5 Pro (free tier)",       "id": "gemini-2.5-pro",         "free": True},
            {"label": "Gemini 3 Flash Preview",           "id": "gemini-3-flash-preview",  "free": False},
            {"label": "Gemini 3.1 Flash Lite Preview",    "id": "gemini-3.1-flash-lite-preview", "free": False},
            {"label": "Gemini 3.1 Pro Preview",           "id": "gemini-3.1-pro-preview",  "free": False},
        ],
        "key_url": "https://aistudio.google.com/apikey",
        "setup_tip": "Get a free key at aistudio.google.com. Set billing limits just in case.",
    },
    "ollama": {
        "name": "Ollama (Local)",
        "base_url": "http://localhost:11434/v1",
        "best_free": "llama3.2",
        "models": [
            {"label": "Llama 3.2 3B",    "id": "llama3.2",       "free": True},
            {"label": "Llama 3.1 8B",    "id": "llama3.1",       "free": True},
            {"label": "Llama 3 8B",      "id": "llama3",         "free": True},
            {"label": "Mistral 7B",      "id": "mistral",        "free": True},
            {"label": "Gemma 3 4B",      "id": "gemma3:4b",      "free": True},
            {"label": "Phi-4 Mini",      "id": "phi4-mini",      "free": True},
            {"label": "Qwen 2.5 7B",     "id": "qwen2.5",        "free": True},
            {"label": "DeepSeek R1 7B",  "id": "deepseek-r1:7b", "free": True},
        ],
        "key_url": "https://ollama.com/download",
        "setup_tip": "No API key needed. Run: ollama pull llama3.2",
    },
}


def get_best_model(provider: str) -> str:
    return PROVIDERS.get(provider, {}).get("best_free", "")


def get_model_labels(provider: str) -> list:
    """Returns list of (label, model_id, is_free) tuples for UI dropdowns."""
    return [(m["label"], m["id"], m["free"]) for m in PROVIDERS.get(provider, {}).get("models", [])]


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
