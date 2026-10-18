import sys, os
sys.path.insert(0, os.path.abspath('.'))

import requests, json
from backend.app.config.settings import settings
from backend.app.config.ai_constants import build_prompt

key = settings.openrouter_api_key
url = 'https://openrouter.ai/api/v1/chat/completions'

sample_text = '''The Shop
Store #100
Chicago, IL

Large Eggs           0.99
Milk                 1.15
Cottage Cheese       0.59
Natural Yogurt       0.70

TOTAL               $3.43'''

for model in ['openrouter/auto', 'inclusionai/ling-3.0-flash:free', 'google/gemma-4-26b-a4b-it:free']:
    print(f"Testing model: {model}...")
    try:
        r = requests.post(
            url,
            headers={'Authorization': f'Bearer {key}'},
            json={
                'model': model,
                'messages': [
                    {'role': 'system', 'content': 'You extract structured JSON from OCR text.'},
                    {'role': 'user', 'content': build_prompt(sample_text)}
                ]
            },
            timeout=10
        )
        print("Status code:", r.status_code)
        if r.status_code == 200:
            content = r.json()['choices'][0]['message']['content']
            print("Response:", content[:200])
    except Exception as e:
        print("Error:", e)
