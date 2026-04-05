import requests
from config import load_config, get_system_prompt, log_entry, PROVIDERS


def call_openai_compatible(base_url: str, api_key: str, model: str,
                            messages: list, extra_headers: dict = None) -> str:
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    if extra_headers:
        headers.update(extra_headers)

    payload = {"model": model, "messages": messages, "max_tokens": 1500, "temperature": 0.3}

    try:
        resp = requests.post(f"{base_url}/chat/completions",
                             headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
    except requests.exceptions.ConnectionError:
        raise RuntimeError(f"Could not connect to {base_url}. Check your internet or that Ollama is running.")
    except requests.exceptions.HTTPError as e:
        body = ""
        try:
            body = resp.json().get("error", {}).get("message", resp.text[:200])
        except Exception:
            body = resp.text[:200]
        raise RuntimeError(f"API error ({resp.status_code}): {body}")

    data = resp.json()
    return data["choices"][0]["message"]["content"].strip()


def call_anthropic(api_key: str, model: str, system: str, messages: list) -> str:
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
    }
    user_messages = [m for m in messages if m["role"] != "system"]
    payload = {"model": model, "system": system, "messages": user_messages, "max_tokens": 1500}

    try:
        resp = requests.post("https://api.anthropic.com/v1/messages",
                             headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
    except requests.exceptions.HTTPError as e:
        body = ""
        try:
            body = resp.json().get("error", {}).get("message", resp.text[:200])
        except Exception:
            body = resp.text[:200]
        raise RuntimeError(f"Anthropic API error ({resp.status_code}): {body}")

    return resp.json()["content"][0]["text"].strip()


def optimize(raw_text: str, is_first_message: bool = True,
             conversation_history: list = None) -> str:
    cfg = load_config()
    provider = cfg.get("provider", "openrouter")
    api_key  = cfg.get("api_key", "")
    model    = cfg.get("model", "")
    pinfo    = PROVIDERS.get(provider, {})

    if not model:
        model = pinfo.get("best_free", "")

    system_prompt = get_system_prompt()
    mode_note = (
        "FIRST MESSAGE MODE: This is the start of a new project or conversation. "
        "Add full role, context, and setup structure."
        if is_first_message else
        "CONTINUATION MODE: This is an ongoing project. Do NOT repeat role/context/setup. "
        "Output only the next clean instruction or delta."
    )
    full_system = f"{system_prompt}\n\n---\nMODE: {mode_note}"

    messages = [{"role": "system", "content": full_system}]
    if conversation_history:
        messages.extend(conversation_history)
    messages.append({"role": "user", "content": raw_text})

    if provider == "anthropic":
        result = call_anthropic(api_key, model, full_system,
                                [m for m in messages if m["role"] != "system"])
    elif provider == "ollama":
        # Ollama OpenAI-compat accepts any non-empty string as key
        result = call_openai_compatible(pinfo["base_url"], "ollama", model, messages)
    elif provider == "openrouter":
        result = call_openai_compatible(
            pinfo["base_url"], api_key, model, messages,
            extra_headers={
                "HTTP-Referer": "https://github.com/ktorres0109/kprompter",
                "X-Title": "KPrompter",
            }
        )
    else:
        # OpenAI, Gemini (OpenAI-compat endpoint)
        result = call_openai_compatible(pinfo["base_url"], api_key, model, messages)

    log_entry({
        "provider": provider,
        "model": model,
        "mode": "first" if is_first_message else "continuation",
        "input_chars": len(raw_text),
        "output_chars": len(result),
    })

    return result
