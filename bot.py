import telebot
import ccxt
import os
import requests
import psycopg2
import time
import io
import random
import logging
from groq import Groq

# --- KONFIGURACJA LOGOWANIA ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- KONFIGURACJA ŚRODOWISKA ---
TOKEN = os.environ.get("TELEGRAM_TOKEN")
GROQ_KEY = os.environ.get("GROQ_KEY")
BRAVE_KEY = os.environ.get("BRAVE_API_KEY")
DB_URL = os.environ.get("DATABASE_URL")
HF_TOKEN = os.environ.get("HF_TOKEN")

bot = telebot.TeleBot(TOKEN)
groq_client = Groq(api_key=GROQ_KEY)

# --- INICJALIZACJA GIEŁDY KUCOIN ---
try:
    kucoin = ccxt.kucoin({
        'apiKey': os.environ.get("KUCOIN_API_KEY"),
        'secret': os.environ.get("KUCOIN_SECRET"),
        'password': os.environ.get("KUCOIN_PASSWORD"),
    })
    logger.info("Połączono z KuCoin.")
except Exception as e:
    kucoin = None
    logger.error(f"Błąd inicjalizacji KuCoin: {e}")

# --- SESJE I HISTORIA ---
user_history = {}
user_prefs = {} 
user_models = {} 
MAX_HISTORY = 6

# --- LOGIKA BAZY DANYCH (POSTGRESQL) ---
def init_db():
    if not DB_URL: 
        logger.warning("DATABASE_URL nie znaleziony.")
        return
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                language TEXT DEFAULT 'EN',
                model_name TEXT DEFAULT 'llama-3.3-70b-versatile',
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        cur.close()
        conn.close()
        logger.info("Baza danych zainicjalizowana.")
    except Exception as e:
        logger.error(f"Błąd bazy danych (init): {e}")

init_db()

def get_user_data(user_id):
    if user_id in user_prefs and user_id in user_models:
        return user_prefs[user_id], user_models[user_id]
    if not DB_URL: return 'EN', 'llama-3.3-70b-versatile'
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        cur.execute("SELECT language, model_name FROM users WHERE user_id = %s", (user_id,))
        res = cur.fetchone()
        cur.close()
        conn.close()
        if res:
            user_prefs[user_id], user_models[user_id] = res[0], res[1]
            return res[0], res[1]
    except Exception as e:
        logger.error(f"Błąd pobierania danych użytkownika: {e}")
    return 'EN', 'llama-3.3-70b-versatile'

def update_user_db(user_id, username, lang=None, model=None):
    l, m = get_user_data(user_id)
    new_l, new_m = (lang or l), (model or m)
    user_prefs[user_id], user_models[user_id] = new_l, new_m
    if not DB_URL: return
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO users (user_id, username, language, model_name) 
            VALUES (%s, %s, %s, %s) 
            ON CONFLICT (user_id) 
            DO UPDATE SET language = EXCLUDED.language, 
                          model_name = EXCLUDED.model_name, 
                          username = EXCLUDED.username
        """, (user_id, username, new_l, new_m))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"Błąd aktualizacji bazy: {e}")

# --- WYSZUKIWARKA BRAVE SEARCH ---
def search_brave(query):
    if not BRAVE_KEY: return ""
    try:
        url = "https://api.search.brave.com/res/v1/web/search"
        headers = {"Accept": "application/json", "X-Subscription-Token": BRAVE_KEY}
        response = requests.get(url, headers=headers, params={"q": query, "count": 3})
        data = response.json()
        results = [f"{r['title']}: {r['description']}" for r in data.get('web', {}).get('results', [])]
        return "\n".join(results) if results else ""
    except Exception as e:
        logger.error(f"Błąd Brave Search: {e}")
        return ""

def inteligentna_odpowiedz(chat_id, text, thread_id):
    try:
        if thread_id: bot.send_message(chat_id, text, message_thread_id=thread_id)
        else: bot.send_message(chat_id, text)
    except Exception as e:
        logger.error(f"Błąd wysyłania wiadomości: {e}")

# --- OBSŁUGA KOMEND ---
@bot.message_handler(commands=['start'])
def welcome(m):
    update_user_db(m.from_user.id, m.from_user.username)
    user_history[m.from_user.id] = []
    inteligentna_odpowiedz(m.chat.id, "GentelmeN@CorE online.\n/en | /pl\n/llama | /fast | /qwen\n/rysuj [opis]\n/balance", m.message_thread_id)

@bot.message_handler(commands=['en', 'pl'])
def change_lang(m):
    l = 'EN' if 'en' in m.text.lower() else 'PL'
    update_user_db(m.from_user.id, m.from_user.username, lang=l)
    bot.send_message(m.chat.id, f"Language: {l}")

@bot.message_handler(commands=['llama', 'fast', 'qwen'])
def change_model(m):
    cmd = m.text.lower()
    model_map = {'/llama': 'llama-3.3-70b-versatile', '/fast': 'llama-3.1-8b-instant', '/qwen': 'qwen-2.5-32b'}
    selected = model_map.get(cmd, 'llama-3.3-70b-versatile')
    update_user_db(m.from_user.id, m.from_user.username, model=selected)
    bot.send_message(m.chat.id, f"Brain: {selected}")

@bot.message_handler(commands=['balance'])
def check_bal(m):
    if m.from_user.username != "GentelmeN_CorE":
        bot.send_message(m.chat.id, f"🚫 Brak dostępu dla {m.from_user.username}")
        return
    if not kucoin:
        bot.send_message(m.chat.id, "❌ Błąd kluczy KuCoin.")
        return
    try:
        res = kucoin.fetch_balance()
        txt = "💰 Portfel:\n" + "\n".join([f"{k}: {v}" for k, v in res['total'].items() if v > 0])
        bot.send_message(m.chat.id, txt)
    except Exception as e:
        bot.send_message(m.chat.id, f"❌ Błąd: {e}")

# --- GENERATOR OBRAZÓW (FLUX) ---
@bot.message_handler(commands=['rysuj'])
def draw(m):
    prompt = m.text.replace('/rysuj', '').strip()
    if not prompt:
        bot.send_message(m.chat.id, "🎨 Co narysować?")
        return
    bot.send_message(m.chat.id, f"🎨 Maluję: {prompt}...")
    
    API = "https://api-inference.huggingface.co/models/black-forest-labs/FLUX.1-schnell"
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    payload = {
        "inputs": prompt,
        "parameters": {"seed": random.randint(1, 1000000)},
        "options": {"wait_for_model": True}
    }
    
    try:
        response = requests.post(API, headers=headers, json=payload, timeout=120)
        if response.status_code == 200:
            img = io.BytesIO(response.content)
            img.seek(0) # Zapobiega ucinaniu obrazu
            bot.send_photo(m.chat.id, img, reply_to_message_id=m.message_id)
        else:
            bot.send_message(m.chat.id, f"❌ HF Error: {response.status_code}")
    except Exception as e:
        bot.send_message(m.chat.id, f"❌ Błąd: {e}")

# --- OBSŁUGA GŁOSU (WHISPER) ---
@bot.message_handler(content_types=['voice'])
def handle_voice(m):
    try:
        file_info = bot.get_file(m.voice.file_id)
        data = bot.download_file(file_info.file_path)
        file_name = f"voice_{m.chat.id}.ogg"
        with open(file_name, "wb") as f: f.write(data)
        with open(file_name, "rb") as audio:
            tr = groq_client.audio.transcriptions.create(file=(file_name, audio.read()), model="whisper-large-v3")
        bot.send_message(m.chat.id, f"🎙️ {tr.text}")
        m.text = tr.text
        ai_chat(m)
        os.remove(file_name)
    except Exception as e:
        logger.error(f"Błąd głosówki: {e}")

# --- CZAT AI (Z HISTORIĄ I INTERNETEM) ---
@bot.message_handler(func=lambda m: True)
def ai_chat(m):
    uid = m.from_user.id
    l, model = get_user_data(uid)
    sys = "You are GentelmeN@CorE." if l == 'EN' else "Jesteś GentelmeN@CorE."
    
    if any(x in m.text.lower() for x in ["cena", "news", "bitcoin"]):
        web = search_brave(m.text)
        if web: sys += f"\nDane z sieci: {web}"

    if uid not in user_history: user_history[uid] = []
    user_history[uid].append({"role": "user", "content": m.text})
    
    try:
        res = groq_client.chat.completions.create(
            messages=[{"role": "system", "content": sys}] + user_history[uid][-MAX_HISTORY:], 
            model=model
        )
        reply = res.choices[0].message.content
        user_history[uid].append({"role": "assistant", "content": reply})
        inteligentna_odpowiedz(m.chat.id, reply, m.message_thread_id)
    except Exception as e:
        logger.error(f"Błąd czatu AI: {e}")

bot.infinity_polling()