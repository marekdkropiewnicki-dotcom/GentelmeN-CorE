import telebot
import ccxt
import os
import requests
from groq import Groq

# --- KONFIGURACJA (Dane z Twojego Railway) ---
TOKEN = os.environ.get("TELEGRAM_TOKEN")
GROQ_KEY = os.environ.get("GROQ_KEY")
BRAVE_KEY = os.environ.get("BRAVE_API_KEY")

# --- TWOJA NAZWA UŻYTKOWNIKA ---
MY_USERNAME = "GentelmeN_CorE" 

bot = telebot.TeleBot(TOKEN)
groq_client = Groq(api_key=GROQ_KEY)

# Konfiguracja giełdy Kucoin
kucoin = ccxt.kucoin({
    'apiKey': os.environ.get("KUCOIN_API_KEY"),
    'secret': os.environ.get("KUCOIN_SECRET"),
    'password': os.environ.get("KUCOIN_PASSWORD"),
})

def search_brave(query):
    """Przeszukiwanie internetu w czasie rzeczywistym (Marzec 2026)"""
    try:
        url = "https://api.search.brave.com/res/v1/web/search"
        headers = {"Accept": "application/json", "X-Subscription-Token": BRAVE_KEY}
        params = {"q": query, "count": 3}
        response = requests.get(url, headers=headers, params=params)
        data = response.json()
        results = [f"{r['title']}: {r['description']}" for r in data.get('web', {}).get('results', [])]
        return "\n".join(results) if results else "Brak nowych danych."
    except:
        return "Błąd połączenia z internetem."

@bot.message_handler(func=lambda m: m.from_user.username != MY_USERNAME)
def access_denied(m):
    bot.reply_to(m, "❌ System GentelmeN@CorE jest prywatny. Brak dostępu.")

@bot.message_handler(commands=['start'])
def welcome(m):
    bot.reply_to(m, "GentelmeN@CorE online! System gotowy do pracy w roku 2026.")

@bot.message_handler(commands=['balance'])
def check_balance(m):
    try:
        balance = kucoin.fetch_balance()
        text = "💰 Saldo Kucoin:\n"
        for asset, amount in balance['total'].items():
            if amount > 0:
                text += f"- {asset}: {amount}\n"
        bot.reply_to(m, text if len(text) > 18 else "Brak środków na koncie.")
    except Exception as e:
        bot.reply_to(m, f"Błąd portfela: {str(e)}")

@bot.message_handler(func=lambda m: True)
def ai_chat(m):
    try:
        # Sprawdzanie, czy zapytanie wymaga świeżych danych (cena, news itp.)
        web_info = ""
        keywords = ["cena", "news", "bitcoin", "krypto", "kurs", "dzisiaj"]
        if any(word in m.text.lower() for word in keywords):
            web_info = search_brave(m.text)
        
        # Tworzenie instrukcji dla AI (Llama 3.1)
        prompt = f"Jesteś GentelmeN@CorE. Mamy Marzec 2026. Użyj tych danych z sieci: {web_info}"
        
        completion = groq_client.chat.completions.create(
            messages=[{"role": "system", "content": prompt}, {"role": "user", "content": m.text}],
            model="llama-3.1-8b-instant",
        )
        bot.reply_to(m, completion.choices[0].message.content)
    except Exception as e:
        bot.reply_to(m, f"Błąd AI: {str(e)}")

bot.infinity_polling()