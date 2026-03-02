import telebot
import ccxt
import os
import requests
from groq import Groq

# Pobieranie kluczy z bezpiecznego skarbca Railway
TOKEN = os.environ.get("TELEGRAM_TOKEN")
GROQ_KEY = os.environ.get("GROQ_KEY")
BRAVE_KEY = os.environ.get("BRAVE_API_KEY")

bot = telebot.TeleBot(TOKEN)
groq_client = Groq(api_key=GROQ_KEY)

# Konfiguracja giełdy Kucoin
kucoin = ccxt.kucoin({
    'apiKey': os.environ.get("KUCOIN_API_KEY"),
    'secret': os.environ.get("KUCOIN_SECRET"),
    'password': os.environ.get("KUCOIN_PASSWORD"),
})

def search_brave(query):
    """Funkcja przeszukująca internet przez Brave API"""
    try:
        url = "https://api.search.brave.com/res/v1/web/search"
        headers = {"Accept": "application/json", "X-Subscription-Token": BRAVE_KEY}
        params = {"q": query, "count": 3}
        response = requests.get(url, headers=headers, params=params)
        results = response.json()
        
        snippets = []
        for res in results.get('web', {}).get('results', []):
            snippets.append(f"- {res['title']}: {res['description']}")
        
        return "\n".join(snippets) if snippets else "Brak wyników w sieci."
    except Exception:
        return "Nie udało się przeszukać internetu."

@bot.message_handler(commands=['start'])
def welcome(m):
    bot.reply_to(m, "GentelmeN@CorE zintegrowany z Brave Search! Jak mogę Ci pomóc?")

@bot.message_handler(commands=['balance'])
def check_balance(m):
    try:
        balance = kucoin.fetch_balance()
        text = "💰 Saldo Kucoin:\n"
        for asset, amount in balance['total'].items():
            if amount > 0:
                text += f"- {asset}: {amount}\n"
        bot.reply_to(m, text if len(text) > 18 else "Brak środków.")
    except Exception as e:
        bot.reply_to(m, f"Błąd portfela: {str(e)}")

@bot.message_handler(func=lambda m: True)
def ai_chat(m):
    try:
        # Jeśli zapytasz o coś aktualnego, bot użyje Brave
        context = ""
        if any(word in m.text.lower() for word in ["news", "cena", "dzisiaj", "sprawdź", "kto"]):
            web_results = search_brave(m.text)
            context = f"\n\nWyniki z internetu (Brave Search):\n{web_results}"

        completion = groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": f"Jesteś GentelmeN@CorE. Pomagaj użytkownikowi. {context}"},
                {"role": "user", "content": m.text}
            ],
            model="llama-3.1-8b-instant",
        )
        bot.reply_to(m, completion.choices[0].message.content)
    except Exception as e:
        bot.reply_to(m, f"Błąd: {str(e)}")

bot.infinity_polling()