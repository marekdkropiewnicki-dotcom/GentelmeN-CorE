import telebot
import ccxt
import os
import requests
import psycopg2
from groq import Groq

# --- KONFIGURACJA Z RAILWAY ---
TOKEN = os.environ.get("TELEGRAM_TOKEN")
GROQ_KEY = os.environ.get("GROQ_KEY")
BRAVE_KEY = os.environ.get("BRAVE_API_KEY")
DB_URL = os.environ.get("DATABASE_URL")

bot = telebot.TeleBot(TOKEN)
groq_client = Groq(api_key=GROQ_KEY)

# Konfiguracja Kucoin
kucoin = ccxt.kucoin({
    'apiKey': os.environ.get("KUCOIN_API_KEY"),
    'secret': os.environ.get("KUCOIN_SECRET"),
    'password': os.environ.get("KUCOIN_PASSWORD"),
})

# --- PAMIĘĆ BOTA (HISTORIA CZATU) ---
# Słownik przechowujący ostatnie wiadomości dla każdego użytkownika
user_history = {}
MAX_HISTORY = 6  # Pamięta 3 ostatnie Twoje pytania i 3 odpowiedzi bota

# --- BAZA DANYCH ---
def init_db():
    if not DB_URL: return
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                language TEXT DEFAULT 'PL',
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        cur.close()
        conn.close()
    except: pass

init_db()

def get_user_lang(user_id):
    if not DB_URL: return 'PL'
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        cur.execute("SELECT language FROM users WHERE user_id = %s", (user_id,))
        res = cur.fetchone()
        cur.close()
        conn.close()
        return res[0] if res else 'PL'
    except: return 'PL'

def set_user_lang(user_id, username, lang):
    if not DB_URL: return
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO users (user_id, username, language) 
            VALUES (%s, %s, %s) 
            ON CONFLICT (user_id) 
            DO UPDATE SET language = EXCLUDED.language, username = EXCLUDED.username
        """, (user_id, username, lang))
        conn.commit()
        cur.close()
        conn.close()
    except: pass

def search_brave(query):
    try:
        url = "https://api.search.brave.com/res/v1/web/search"
        headers = {"Accept": "application/json", "X-Subscription-Token": BRAVE_KEY}
        params = {"q": query, "count": 3}
        response = requests.get(url, headers=headers, params=params)
        data = response.json()
        results = [f"{r['title']}: {r['description']}" for r in data.get('web', {}).get('results', [])]
        return "\n".join(results) if results else ""
    except: return ""

# --- KOMENDY ---
@bot.message_handler(commands=['start'])
def welcome(m):
    set_user_lang(m.from_user.id, m.from_user.username, 'PL')
    # Czyścimy historię przy starcie
    user_history[m.from_user.id] = []
    bot.reply_to(m, "Witaj w systemie GentelmeN@CorE! Zaktualizowano moduł pamięci.\nAby zmienić język: /lang EN lub /lang PL")

@bot.message_handler(commands=['lang'])
def change_language(m):
    text = m.text.upper()
    if "EN" in text:
        set_user_lang(m.from_user.id, m.from_user.username, 'EN')
        # Gdy zmieniamy język, czyścimy historię, żeby bot nie pomieszał kontekstów
        user_history[m.from_user.id] = []
        bot.reply_to(m, "Language strictly set to English! 🇬🇧 I will now ignore Polish inputs.")
    else:
        set_user_lang(m.from_user.id, m.from_user.username, 'PL')
        user_history[m.from_user.id] = []
        bot.reply_to(m, "Język ustawiony na polski! 🇵🇱")

@bot.message_handler(commands=['balance'])
def check_balance(m):
    if m.from_user.username != "GentelmeN_CorE":
        bot.reply_to(m, "Brak dostępu / Access denied.")
        return
    try:
        balance = kucoin.fetch_balance()
        text = "💰 Saldo Kucoin:\n"
        for asset, amount in balance['total'].items():
            if amount > 0: text += f"- {asset}: {amount}\n"
        bot.reply_to(m, text if len(text) > 18 else "Brak środków.")
    except Exception as e:
        bot.reply_to(m, f"Error: {str(e)}")

# --- GŁÓWNY SILNIK AI Z PAMIĘCIĄ ---
@bot.message_handler(func=lambda m: True)
def ai_chat(m):
    user_id = m.from_user.id
    user_lang = get_user_lang(user_id)
    
    # 1. Rygorystyczny System Prompt w zależności od języka
    if user_lang == 'EN':
        sys_msg = "You are GentelmeN@CorE, an advanced AI. Current date is March 2026. YOU MUST RESPOND STRICTLY AND ONLY IN ENGLISH. If the user speaks Polish or any other language, translate your thoughts and reply in English ONLY."
    else:
        sys_msg = "Jesteś GentelmeN@CorE, zaawansowaną AI. Mamy Marzec 2026. MUSISZ ODPOWIADAĆ TYLKO I WYŁĄCZNIE PO POLSKU, niezależnie od tego w jakim języku pisze użytkownik."
    
    # 2. Sprawdzanie internetu
    web_info = ""
    if any(word in m.text.lower() for word in ["cena", "news", "bitcoin", "krypto", "kurs", "price", "today", "ile", "co"]):
        web_info = search_brave(m.text)
        if web_info:
            sys_msg += f"\nData from the web: {web_info}"

    # 3. Zarządzanie Pamięcią Konwersacji
    if user_id not in user_history:
        user_history[user_id] = []
        
    # Dodajemy nowe pytanie użytkownika do historii
    user_history[user_id].append({"role": "user", "content": m.text})
    
    # Budujemy pełny pakiet wiadomości: System + Historia
    messages = [{"role": "system", "content": sys_msg}] + user_history[user_id]

    try:
        completion = groq_client.chat.completions.create(
            messages=messages,
            model="llama-3.1-8b-instant",
        )
        reply = completion.choices[0].message.content
        
        # Zapisujemy odpowiedź AI do historii
        user_history[user_id].append({"role": "assistant", "content": reply})
        
        # Pilnujemy, żeby historia nie przekroczyła ustalonego limitu (MAX_HISTORY)
        if len(user_history[user_id]) > MAX_HISTORY:
            user_history[user_id] = user_history[user_id][-MAX_HISTORY:]
            
        bot.reply_to(m, reply)
    except Exception as e:
        bot.reply_to(m, f"Error: {str(e)}")

bot.infinity_polling()