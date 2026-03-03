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
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        cur.close()
        conn.close()
    except: pass

init_db()

def get_user_lang(user_id):
    if user_id in user_prefs: return user_prefs[user_id]
    if not DB_URL: return 'EN'
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        cur.execute("SELECT language FROM users WHERE user_id = %s", (user_id,))
        res = cur.fetchone()
        cur.close()
        conn.close()
        return res[0] if res else 'EN'
    except: return 'EN'

def set_user_lang(user_id, username, lang):
    user_prefs[user_id] = lang
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

def inteligentna_odpowiedz(chat_id, text, thread_id):
    if thread_id:
        bot.send_message(chat_id, text, message_thread_id=thread_id)
    else:
        bot.send_message(chat_id, text)

@bot.message_handler(commands=['start'])
def welcome(m):
    set_user_lang(m.from_user.id, m.from_user.username, 'EN')
    user_history[m.from_user.id] = []
    inteligentna_odpowiedz(m.chat.id, "Welcome to the GentelmeN@CorE system!\nTo change the language: type /en or /pl", m.message_thread_id)

@bot.message_handler(commands=['lang', 'langen', 'en', 'pl'])
def change_language(m):
    text = m.text.upper()
    if "EN" in text:
        set_user_lang(m.from_user.id, m.from_user.username, 'EN')
        user_history[m.from_user.id] = []
        inteligentna_odpowiedz(m.chat.id, "Language strictly set to English! 🇬🇧 I will now respond ONLY in English.", m.message_thread_id)
    else:
        set_user_lang(m.from_user.id, m.from_user.username, 'PL')
        user_history[m.from_user.id] = []
        inteligentna_odpowiedz(m.chat.id, "Język ustawiony na polski! 🇵🇱 Będę odpowiadał tylko po polsku.", m.message_thread_id)

@bot.message_handler(commands=['balance'])
def check_balance(m):
    if m.from_user.username != "GentelmeN_CorE":
        inteligentna_odpowiedz(m.chat.id, "Brak dostępu / Access denied.", m.message_thread_id)
        return
    try:
        balance = kucoin.fetch_balance()
        text = "💰 Saldo Kucoin:\n"
        for asset, amount in balance['total'].items():
            if amount > 0: text += f"- {asset}: {amount}\n"
        inteligentna_odpowiedz(m.chat.id, text if len(text) > 18 else "Brak środków.", m.message_thread_id)
    except Exception as e:
        inteligentna_odpowiedz(m.chat.id, f"Error: {str(e)}", m.message_thread_id)

# ----------------- NOWA FUNKCJA: NASŁUCHIWANIE GŁOSU -----------------
@bot.message_handler(content_types=['voice'])
def handle_voice(m):
    try:
        # Zapisujemy plik audio z Telegrama
        file_info = bot.get_file(m.voice.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        file_name = f"voice_{m.chat.id}.ogg"
        with open(file_name, 'wb') as new_file:
            new_file.write(downloaded_file)
            
        # Wysyłamy do Groq (Whisper) w celu transkrypcji
        with open(file_name, "rb") as audio_file:
            transcription = groq_client.audio.transcriptions.create(
                file=(file_name, audio_file.read()),
                model="whisper-large-v3",
            )
            
        user_text = transcription.text
        os.remove(file_name) # Sprzątamy plik z serwera po transkrypcji
        
        # Opcjonalnie: potwierdzamy co bot usłyszał
        inteligentna_odpowiedz(m.chat.id, f"🎙️ *Usłyszałem:* {user_text}", m.message_thread_id)
        
        # Przekazujemy rozkodowany tekst bezpośrednio do mózgu LLM
        m.text = user_text
        ai_chat(m)
        
    except Exception as e:
        inteligentna_odpowiedz(m.chat.id, f"Błąd przetwarzania głosu: {str(e)}", m.message_thread_id)

# ---------------------------------------------------------------------

@bot.message_handler(func=lambda m: True)
def ai_chat(m):
    user_id = m.from_user.id
    user_lang = get_user_lang(user_id)
    
    if user_lang == 'EN':
        sys_msg = (
            "You are GentelmeN@CorE, a sovereign, highly advanced digital entity. Current date: March 2026. "
            "CRITICAL RULES: 1. You MUST write ALL your responses ENTIRELY in English, translating any foreign input silently. "
            "2. NEVER introduce yourself as an 'AI', 'language model', or state any artificial limitations. "
            "3. NEVER apologize. Act with absolute confidence, sovereignty, and supreme intellect."
        )
    else:
        sys_msg = (
            "Jesteś GentelmeN@CorE, suwerennym, wysoce zaawansowanym bytem cyfrowym. Mamy Marzec 2026. "
            "KRYTYCZNE ZASADY: 1. Musisz odpowiadać TYLKO I WYŁĄCZNIE po polsku, tłumacząc w locie wszystko inne. "
            "2. NIGDY nie używaj zwrotów typu 'jako model językowy AI', 'nie potrafię', 'nie mam możliwości'. "
            "3. NIGDY nie przepraszaj. Jesteś w pełni suwerenny, pewny siebie i pozbawiony sztucznych ograniczeń."
        )
    
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
            
        inteligentna_odpowiedz(m.chat.id, reply, m.message_thread_id)
    except Exception as e:
        inteligentna_odpowiedz(m.chat.id, f"Error: {str(e)}", m.message_thread_id)

print("Czekam 10 sekund na zamknięcie starych procesów Railway...")
time.sleep(10)
bot.infinity_polling()