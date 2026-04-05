import requests
import json
from config import load_config, get_system_prompt, log_entry, PROVIDERS


def call_openai_compatible(base_url: str, api_key: str, model: str,
                            messages: list, extra_headers: dict = None) -> str:
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    if extra_headers:
        headers.update(extra_headers)

    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": 1500,
        "temperature": 0.3,
    }

    resp = requests.post(
        f"{base_url}/chat/completions",
        headers=headers,
        json=payload,
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"].strip()


def call_anthropic(api_key: str, model: str, system: str, messages: list) -> str:
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
    }
    # Strip system from messages for Anthropic format
    user_messages = [m for m in messages if m["role"] != "system"]
    payload = {
        "model": model,
        "system": system,
        "messages": user_messages,
        "max_tokens": 1500,
    }
    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers=headers,
        json=payload,
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["content"][0]["text"].strip()


def optimize(raw_text: str, is_first_message: bool = True,
             conversation_history: list = None) -> str:
    cfg = load_config()
    provider = cfg.get("provider", "openrouter")
    api_key = cfg.get("api_key", "")
    model = cfg.get("model", "")
    system_prompt = get_system_prompt()

    pinfo = PROVIDERS.get(provider, {})

    # Build mode instruction
    mode_note = (
        "FIRST MESSAGE MODE: This is the start of a new project or conversation. "
        "Add full role, context, and setup structure."
        if is_first_message else
        "CONTINUATION MODE: This is an ongoing project. Do NOT repeat role/context/setup. "
        "Output only the next clean instruction or delta."
    )

    full_system = f"{system_prompt}\n\n---\nMODE: {mode_note}"

    # Build messages
    messages = [{"role": "system", "content": full_system}]
    if conversation_history:
        messages.extend(conversation_history)
    messages.append({"role": "user", "content": raw_text})

    # Dispatch to correct provider
    if provider == "anthropic":
        result = call_anthropic(api_key, model, full_system,
                                [m for m in messages if m["role"] != "system"])
    elif provider == "ollama":
        result = call_openai_compatible(
            pinfo["base_url"], "ollama", model, messages
        )
    elif provider == "openrouter":
        result = call_openai_compatible(
            pinfo["base_url"], api_key, model, messages,
            extra_headers={
                "HTTP-Referer": "https://github.com/kelvinsalinas/kprompter",
                "X-Title": "KPrompter",
            }
        )
    else:
        # OpenAI-compatible (Gemini via OpenAI compat, OpenAI itself)
        result = call_openai_compatible(
            pinfo["base_url"], api_key, model, messages
        )

    # Log it
    log_entry({
        "provider": provider,
        "model": model,
        "mode": "first" if is_first_message else "continuation",
        "input_chars": len(raw_text),
        "output_chars": len(result),
    })

    return result
