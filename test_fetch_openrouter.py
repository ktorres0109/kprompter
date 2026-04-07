import requests

try:
    response = requests.get("https://openrouter.ai/api/v1/models")
    models = response.json()['data']
    free_models = [m['id'] for m in models if m['pricing']['prompt'] == "0"]
    for m in free_models[:10]:
        print(m)
except Exception as e:
    print(f"Failed: {e}")
