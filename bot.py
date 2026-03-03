import telebot
import ccxt
import os
import requests
import psycopg2
import time
from groq import Groq

TOKEN = os.environ.get("TELEGRAM_TOKEN")
GROQ_KEY = os.environ.get("GROQ_KEY")
BRAVE_KEY = os.environ.get("BRAVE_API_KEY")
DB_URL = os.environ.get("DATABASE_URL")

bot = telebot.TeleBot(TOKEN)
groq_client = Groq(api_key=GROQ_KEY)

kucoin = ccxt.kucoin({
    'apiKey': os.environ.get("KUCOIN_API_KEY"),
    'secret': os.environ.get("KUCOIN_SECRET"),
    'password': os.environ.get("KUCOIN_PASSWORD"),
})

user_history = {}
user_prefs = {} 
user_models = {} 
MAX_HISTORY = 6

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
    except: pass

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
            user_prefs[user_id] = res[0]
            user_models[user_id] = res[1]
            return res[0], res[1]
    except: pass
    return 'EN', 'llama-3.3-70b-versatile'

def update_user_db(user_id, username, lang=None, model=None):
    current_lang, current_model = get_user_data(user_id)
    new_lang = lang if lang else current_lang
    new_model = model if model else current_model
    user_prefs[user_id] = new_lang
    user_models[user_id] = new_model
    if not DB_URL: return
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO users (user_id, username, language, model_name) 
            VALUES (%s, %s, %s, %s) 
            ON CONFLICT (user_id) 
            DO UPDATE SET language = EXCLUDED.language, model_name = EXCLUDED.model_name, username = EXCLUDED.username
        """, (user_id, username, new_lang, new_model))
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

def inteligentna_odpowiedz(chat_id, text, thread_id):
    if thread_id:
        bot.send_message(chat_id, text, message_thread_id=thread_id)
    else:
        bot.send_message(chat_id, text)

@bot.message_handler(commands=['start'])
def welcome(m):
    update_user_db(m.from_user.id, m.from_user.username, lang='EN', model='llama-3.3-70b-versatile')
    user_history[m.from_user.id] = []
    inteligentna_odpowiedz(m.chat.id, "Welcome to GentelmeN@CorE!\n/en | /pl - Language\n/llama | /fast | /qwen - AI Brain\n/balance - KuCoin", m.message_thread_id)

@bot.message_handler(commands=['en', 'pl'])
def change_language(m):
    new_lang = 'EN' if 'EN' in m.text.upper() else 'PL'
    update_user_db(m.from_user.id, m.from_user.username, lang=new_lang)
    msg = "Language: English 🇬🇧" if new_lang == 'EN' else "Język: Polski 🇵🇱"
    inteligentna_odpowiedz(m.chat.id, msg, m.message_thread_id)

@bot.message_handler(commands=['llama', 'fast', 'qwen'])
def change_model(m):
    cmd = m.text.lower()
    model_map = {'/llama': 'llama-3.3-70b-versatile', '/fast': 'llama-3.1-8b-instant', '/qwen': 'qwen-2.5-32b'}
    selected_model = model_map.get(cmd, 'llama-3.3-70b-versatile')
    update_user_db(m.from_user.id, m.from_user.username, model=selected_model)
    inteligentna_odpowiedz(m.chat.id, f"🚀 Brain switched to: {selected_model}", m.message_thread_id)

# ----------------- PRZYWRÓCONY KUCOIN -----------------
@bot.message_handler(commands=['balance'])
def check_balance(m):
    # TUTAJ JEST TWOJA BLOKADA BEZPIECZEŃSTWA:
    if m.from_user.username != "GentelmeN_CorE":
        inteligentna_odpowiedz(m.chat.id, f"🚫 Brak dostępu. Twój username to: {m.from_user.username}. Zmień kod na GitHubie, jeśli to Ty!", m.message_thread_id)
        return
        
    inteligentna_odpowiedz(m.chat.id, "🔄 Łączę się z KuCoin...", m.message_thread_id)
    try:
        balance = kucoin.fetch_balance()
        text = "💰 Saldo KuCoin:\n"
        for asset, amount in balance['total'].items():
            if amount > 0: text += f"- {asset}: {amount}\n"
        inteligentna_odpowiedz(m.chat.id, text if len(text) > 18 else "Brak środków.", m.message_thread_id)
    except Exception as e:
        inteligentna_odpowiedz(m.chat.id, f"❌ Błąd KuCoin: {str(e)}", m.message_thread_id)
# ------------------------------------------------------

@bot.message_handler(content_types=['voice'])
def handle_voice(m):
    try:
        file_info = bot.get_file(m.voice.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        file_name = f"voice_{m.chat.id}.ogg"
        with open(file_name, 'wb') as new_file: new_file.write(downloaded_file)
        with open(file_name, "rb") as audio_file:
            transcription = groq_client.audio.transcriptions.create(file=(file_name, audio_file.read()), model="whisper-large-v3")
        user_text = transcription.text
        os.remove(file_name)
        inteligentna_odpowiedz(m.chat.id, f"🎙️ *Usłyszałem:* {user_text}", m.message_thread_id)
        m.text = user_text
        ai_chat(m)
    except Exception as e:
        inteligentna_odpowiedz(m.chat.id, f"Błąd głosu: {str(e)}", m.message_thread_id)

@bot.message_handler(func=lambda m: True)
def ai_chat(m):
    user_id = m.from_user.id
    user_lang, user_model = get_user_data(user_id)
    if user_lang == 'EN':
        sys_msg = "You are GentelmeN@CorE, a sovereign digital entity. Speak ONLY English. Never apologize."
    else:
        sys_msg = "Jesteś GentelmeN@CorE, suwerennym bytem cyfrowym. Mów TYLKO po polsku. Nigdy nie przepraszaj."
    
    web_info = ""
    if any(word in m.text.lower() for word in ["cena", "news", "bitcoin", "kurs", "price", "today"]):
        web_info = search_brave(m.text)
        if web_info: sys_msg += f"\nWeb data: {web_info}"

    if user_id not in user_history: user_history[user_id] = []
    user_history[user_id].append({"role": "user", "content": m.text})
    messages = [{"role": "system", "content": sys_msg}] + user_history[user_id]

    try:
        completion = groq_client.chat.completions.create(messages=messages, model=user_model)
        reply = completion.choices[0].message.content
        user_history[user_id].append({"role": "assistant", "content": reply})
        if len(user_history[user_id]) > MAX_HISTORY: user_history[user_id] = user_history[user_id][-MAX_HISTORY:]
        inteligentna_odpowiedz(m.chat.id, reply, m.message_thread_id)
    except Exception as e:
        inteligentna_odpowiedz(m.chat.id, f"Error: {str(e)}", m.message_thread_id)

print("Czekam 10 sekund na zamknięcie starych procesów Railway...")
time.sleep(10)
bot.infinity_polling()