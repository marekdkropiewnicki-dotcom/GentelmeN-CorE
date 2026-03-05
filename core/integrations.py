import io
import os

import requests

BRAVE_KEY = os.environ.get("BRAVE_API_KEY")
HF_TOKEN = os.environ.get("HF_TOKEN")


def search_brave(query, count=3):
    if not BRAVE_KEY:
        return ""
    try:
        url = "https://api.search.brave.com/res/v1/web/search"
        headers = {"Accept": "application/json", "X-Subscription-Token": BRAVE_KEY}
        params = {"q": query, "count": count, "text_decorations": False}
        response = requests.get(url, headers=headers, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
        results = [
            f"{r['title']}: {r['description']}"
            for r in data.get('web', {}).get('results', [])
        ]
        return "\n".join(results) if results else ""
    except requests.RequestException:
        return ""


def generate_image_hf(prompt):
    if not HF_TOKEN:
        return None, "❌ Brak HF_TOKEN."
    api_url = "https://api-inference.huggingface.co/models/black-forest-labs/FLUX.1-schnell"
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    try:
        response = requests.post(
            api_url,
            headers=headers,
            json={"inputs": prompt},
            timeout=15,
        )
        if response.status_code == 200:
            return io.BytesIO(response.content), None
        else:
            return None, f"❌ Błąd serwera HF: {response.status_code}"
    except requests.Timeout:
        return None, "❌ Przekroczono limit czasu podczas łączenia z HF (timeout)."
    except requests.RequestException as e:
        return None, f"❌ Błąd połączenia: {str(e)}"
