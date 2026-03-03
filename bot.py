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

# --- PAMIĘĆ BOTA (RAM) ---
user_history = {}
user_prefs = {}  # NOWOŚĆ: Zapasowa pamięć języka w RAM!
MAX_HISTORY = 6

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
    # Najpierw sprawdzamy niezawodny RAM
    if user_id in user_prefs:
        return user_prefs[user_id]
    
    # Jeśli nie ma w RAM, próbujemy z bazy
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
    # ZAPIS DO NIEZAWODNEGO RAM-u
    user_prefs[user_id] = lang
    
    # Próba zapisu do bazy w tle
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
    user_history[m.from_user.id] = []
    bot.reply_to(m, "Witaj w systemie GentelmeN@CorE!\nAby zmienić język: wpisz /en lub /pl")

@bot.message_handler(commands=['lang', 'langen', 'en', 'pl'])
def change_language(m):
    text = m.text.upper()
    if "EN" in text:
        set_user_lang(m.from_user.id, m.from_user.username, 'EN')
        user_history[m.from_user.id] = []
        bot.reply_to(m, "Language strictly set to English! 🇬🇧 I will now respond ONLY in English.")
    else:
        set_user_lang(m.from_user.id, m.from_user.username, 'PL')
        user_history[m.from_user.id] = []
        bot.reply_to(m, "Język ustawiony na polski! 🇵🇱 Będę odpowiadał tylko po polsku.")

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

# --- GŁÓWNY SILNIK AI (LLAMA 3.3 70B) ---
@bot.message_handler(func=lambda m: True)
def ai_chat(m):
    user_id = m.from_user.id
    user_lang = get_user_lang(user_id)
    
    if user_lang == 'EN':
        sys_msg = "You are GentelmeN@CorE, an advanced AI. Current date: March 2026. CRITICAL RULE: You MUST write ALL your responses ENTIRELY in English. Even if the user asks a question in Polish, German or any other language, you MUST translate your answer and reply ONLY in English. Do not use any Polish words."
    else:
        sys_msg = "Jesteś GentelmeN@CorE, zaawansowaną AI. Mamy Marzec 2026. KRYTYCZNA ZASADA: Musisz odpowiadać TYLKO I WYŁĄCZNIE po polsku. Nawet jeśli użytkownik zada pytanie po angielsku, musisz odpowiedzieć po polsku."
    
    web_info = ""
    if any(word in m.text.lower() for word in ["cena", "news", "bitcoin", "krypto", "kurs", "price", "today", "ile", "co"]):
        web_info = search_brave(m.text)
        if web_info:
            sys_msg += f"\nData from the web: {web_info}"

    if user_id not in user_history:
        user_history[user_id] = []
        
    user_history[user_id].append({"role": "user", "content": m.text})
    messages = [{"role": "system", "content": sys_msg}] + user_history[user_id]

    try:
        completion = groq_client.chat.completions.create(
            messages=messages,
            model="llama-3.3-70b-versatile", 
        )
        reply = completion.choices[0].message.content
        
        user_history[user_id].append({"role": "assistant", "content": reply})
        if len(user_history[user_id]) > MAX_HISTORY:
            user_history[user_id] = user_history[user_id][-MAX_HISTORY:]
            
        bot.reply_to(m, reply)
    except Exception as e:
        bot.reply_to(m, f"Error: {str(e)}")

bot.infinity_polling()