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
DB_URL = os.environ.get("DATABASE_URL")  # Nowość: Link do Twojej bazy danych

bot = telebot.TeleBot(TOKEN)
groq_client = Groq(api_key=GROQ_KEY)

# Konfiguracja Kucoin
kucoin = ccxt.kucoin({
    'apiKey': os.environ.get("KUCOIN_API_KEY"),
    'secret': os.environ.get("KUCOIN_SECRET"),
    'password': os.environ.get("KUCOIN_PASSWORD"),
})

# --- INICJALIZACJA BAZY DANYCH ---
def init_db():
    if not DB_URL:
        print("Brak DATABASE_URL. Baza nie działa.")
        return
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        # Tworzymy tabelę użytkowników (jeśli jeszcze nie istnieje)
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
    except Exception as e:
        print(f"Błąd bazy danych: {e}")

init_db()  # Uruchamiamy przy starcie bota

# --- FUNKCJE BAZY DANYCH ---
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
    except:
        return 'PL'

def set_user_lang(user_id, username, lang):
    if not DB_URL: return
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        # Zapisz lub zaktualizuj użytkownika
        cur.execute("""
            INSERT INTO users (user_id, username, language) 
            VALUES (%s, %s, %s) 
            ON CONFLICT (user_id) 
            DO UPDATE SET language = EXCLUDED.language, username = EXCLUDED.username
        """, (user_id, username, lang))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Błąd zapisu: {e}")

def search_brave(query):
    try:
        url = "https://api.search.brave.com/res/v1/web/search"
        headers = {"Accept": "application/json", "X-Subscription-Token": BRAVE_KEY}
        params = {"q": query, "count": 3}
        response = requests.get(url, headers=headers, params=params)
        data = response.json()
        results = [f"{r['title']}: {r['description']}" for r in data.get('web', {}).get('results', [])]
        return "\n".join(results) if results else "Brak nowych danych."
    except:
        return ""

# --- OBSŁUGA KOMEND ---

@bot.message_handler(commands=['start'])
def welcome(m):
    # Domyślnie dodajemy nowego użytkownika do bazy z językiem PL
    set_user_lang(m.from_user.id, m.from_user.username, 'PL')
    bot.reply_to(m, "Witaj w systemie GentelmeN@CorE! / Welcome to GentelmeN@CorE system!\n\nAby zmienić język na angielski wpisz: /lang EN\nTo change language to Polish type: /lang PL")

@bot.message_handler(commands=['lang'])
def change_language(m):
    text = m.text.upper()
    if "EN" in text:
        set_user_lang(m.from_user.id, m.from_user.username, 'EN')
        bot.reply_to(m, "Language changed to English! 🇬🇧")
    else:
        set_user_lang(m.from_user.id, m.from_user.username, 'PL')
        bot.reply_to(m, "Język zmieniony na polski! 🇵🇱")

@bot.message_handler(commands=['balance'])
def check_balance(m):
    # Prosta blokada - na razie tylko dla Ciebie (jako administratora)
    if m.from_user.username != "GentelmeN_CorE":
        bot.reply_to(m, "Brak dostępu do portfela / Wallet access denied.")
        return
    try:
        balance = kucoin.fetch_balance()
        text = "💰 Saldo Kucoin:\n"
        for asset, amount in balance['total'].items():
            if amount > 0: text += f"- {asset}: {amount}\n"
        bot.reply_to(m, text if len(text) > 18 else "Brak środków na koncie.")
    except Exception as e:
        bot.reply_to(m, f"Błąd portfela / Wallet error: {str(e)}")

@bot.message_handler(func=lambda m: True)
def ai_chat(m):
    try:
        # Pobieramy język użytkownika z bazy danych!
        user_lang = get_user_lang(m.from_user.id)
        
        web_info = ""
        if any(word in m.text.lower() for word in ["cena", "news", "bitcoin", "krypto", "kurs", "price", "today"]):
            web_info = search_brave(m.text)
        
        # Instrukcja z uwzględnieniem wybranego języka
        lang_instruction = "Respond in Polish." if user_lang == 'PL' else "Respond in English."
        prompt = f"Jesteś GentelmeN@CorE. Mamy Marzec 2026. {lang_instruction} Użyj tych danych z sieci: {web_info}"
        
        completion = groq_client.chat.completions.create(
            messages=[{"role": "system", "content": prompt}, {"role": "user", "content": m.text}],
            model="llama-3.1-8b-instant",
        )
        bot.reply_to(m, completion.choices[0].message.content)
    except Exception as e:
        bot.reply_to(m, f"Error: {str(e)}")

bot.infinity_polling()