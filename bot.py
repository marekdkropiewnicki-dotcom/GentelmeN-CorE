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

# --- LOGOWANIE BŁĘDÓW ---
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
    logger.error(f"Błąd KuCoin: {e}")

# --- SESJE I HISTORIA ---
user_history = {}
user_prefs = {} 
user_models = {} 
MAX_HISTORY = 6

# --- LOGIKA BAZY DANYCH (POSTGRESQL) ---
def init_db():
    if not DB_URL: return
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
    except Exception as e:
        logger.error(f"DB Init Error: {e}")

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
    except: pass
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
    except: pass

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
    except: return ""

# --- OBSŁUGA KOMEND ---
@bot.message_handler(commands=['start'])
def welcome(m):
    update_user_db(m.from_user.id, m.from_user.username)
    bot.send_message(m.chat.id, "GentelmeN@CorE online.\n/en | /pl\n/rysuj [opis]\n/balance")

@bot.message_handler(commands=['en', 'pl'])
def change_lang(m):
    l = 'EN' if 'en' in m.text.lower() else 'PL'
    update_user_db(m.from_user.id, m.from_user.username, lang=l)
    bot.send_message(m.chat.id, f"Język: {l}")

@bot.message_handler(commands=['balance'])
def check_bal(m):
    # PRZYWRÓCONO: Autoryzacja po username
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
        # PRZYWRÓCONO: timeout=120
        response = requests.post(API, headers=headers, json=payload, timeout=120)
        if response.status_code == 200:
            img = io.BytesIO(response.content)
            img.seek(0) # Kluczowe, żeby nie ucinało obrazu
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
        with open("v.ogg", "wb") as f: f.write(data)
        with open("v.ogg", "rb") as f:
            tr = groq_client.audio.transcriptions.create(file=("v.ogg", f.read()), model="whisper-large-v3")
        bot.send_message(m.chat.id, f"🎙️ {tr.text}")
        m.text = tr.text
        chat(m)
        os.remove("v.ogg")
    except Exception as e:
        bot.send_message(m.chat.id, f"❌ Voice Error: {e}")

# --- CHAT AI (Z HISTORIĄ I BRAVE SEARCH) ---
@bot.message_handler(func=lambda m: True)
def chat(m):
    uid = m.from_user.id
    l, model = get_user_data(uid)
    sys = "You are GentelmeN@CorE." if l == 'EN' else "Jesteś GentelmeN@CorE."
    
    if any(x in m.text.lower() for x in ["cena", "news", "bitcoin"]):
        web = search_brave(m.text)
        if web: sys += f"\nAktualne dane: {web}"

    if uid not in user_history: user_history[uid] = []
    user_history[uid].append({"role": "user", "content": m.text})
    
    try:
        res = groq_client.chat.completions.create(
            messages=[{"role": "system", "content": sys}] + user_history[uid][-MAX_HISTORY:], 
            model=model
        )
        reply = res.choices[0].message.content
        user_history[uid].append({"role": "assistant", "content": reply})
        bot.send_message(m.chat.id, reply)
    except Exception as e:
        bot.send_message(m.chat.id, f"❌ AI Error: {e}")

bot.infinity_polling()