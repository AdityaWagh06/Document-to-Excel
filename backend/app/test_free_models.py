import sys, os
from pathlib import Path

# Ensure backend root is in sys.path
ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import requests
from backend.app.config.settings import settings

key = settings.openrouter_api_key
if not key:
    print("OPENROUTER_API_KEY is not set. Please configure it in your environment or backend/.env.")
    sys.exit(0)

url = 'https://openrouter.ai/api/v1/models'

res = requests.get(url)
data = res.json().get('data', [])
free_models = [m['id'] for m in data if m.get('id', '').endswith(':free')]

print(f"Testing {len(free_models)} free models on OpenRouter...")

chat_url = 'https://openrouter.ai/api/v1/chat/completions'

working = []

for model in free_models:
    try:
        r = requests.post(
            chat_url,
            headers={'Authorization': f'Bearer {key}'},
            json={
                'model': model,
                'messages': [{'role': 'user', 'content': 'Hello, reply with JSON: {"status": "ok"}'}]
            },
            timeout=8
        )
        if r.status_code == 200:
            print(f"  [WORKS 200] {model}")
            working.append(model)
        else:
            print(f"  [FAIL {r.status_code}] {model}")
    except Exception as exc:
        print(f"  [ERROR] {model}: {exc}")

print("\n--- WORKING FREE MODELS LIST ---")
for w in working:
    print(w)
