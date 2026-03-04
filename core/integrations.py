import io
import os

import ccxt
import requests

BRAVE_KEY = os.environ.get("BRAVE_API_KEY")
HF_TOKEN = os.environ.get("HF_TOKEN")


def init_kucoin():
    try:
        return ccxt.kucoin({
            'apiKey': os.environ.get("KUCOIN_API_KEY"),
            'secret': os.environ.get("KUCOIN_SECRET"),
            'password': os.environ.get("KUCOIN_PASSWORD"),
        })
    except Exception:
        return None


def search_brave(query):
    if not BRAVE_KEY:
        return ""
    try:
        url = "https://api.search.brave.com/res/v1/web/search"
        headers = {"Accept": "application/json", "X-Subscription-Token": BRAVE_KEY}
        params = {"q": query, "count": 3}
        response = requests.get(url, headers=headers, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
        results = [f"{r['title']}: {r['description']}" for r in data.get('web', {}).get('results', [])]
        return "\n".join(results) if results else ""
    except requests.RequestException:
        return ""


def generate_image_hf(prompt):
    """Generate an image using Hugging Face Stable Diffusion API.

    Returns (image_bytes, None) on success, or (None, error_message) on failure.
    """
    if not HF_TOKEN:
        return None, "❌ Brak zmiennej HF_TOKEN w Railway."
    api_url = "https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-xl-base-1.0"
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    try:
        response = requests.post(api_url, headers=headers, json={"inputs": prompt})
        if response.status_code == 200:
            return io.BytesIO(response.content), None
        else:
            return None, f"❌ Błąd serwera HF: {response.status_code}"
    except Exception as e:
        return None, f"❌ Błąd: {str(e)}"
