import requests

try:
    response = requests.get("https://openrouter.ai/api/v1/models", timeout=10)
    data = response.json()
    models = data.get('data', [])
    free_models = [
        m['id'] for m in models
        if str(m.get('pricing', {}).get('prompt', -1)) == "0"
    ]
    for m in free_models:
        print(m)
    print(f"\nTotal free models: {len(free_models)}")
except Exception as e:
    print(f"Failed: {e}")
