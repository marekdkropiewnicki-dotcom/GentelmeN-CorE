import telebot
import ccxt
import os
import requests
import psycopg2
import time
import io
import tempfile
from groq import Groq

# --- ZMIENNE ŚRODOWISKOWE ---
TOKEN = os.environ.get("TELEGRAM_TOKEN")
GROQ_KEY = os.environ.get("GROQ_KEY")
BRAVE_KEY = os.environ.get("BRAVE_API_KEY")
DB_URL = os.environ.get("DATABASE_URL")
HF_TOKEN = os.environ.get("HF_TOKEN")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN") # Opcjonalnie

# Ważne: Zmień na swoje numeryczne ID z Telegrama
ADMIN_ID = int(os.environ.get("ADMIN_ID", 0))

bot = telebot.TeleBot(TOKEN)
groq_client = Groq(api_key=GROQ_KEY)

# --- INICJALIZACJA KUCOIN ---
try:
    kucoin = ccxt.kucoin({
        'apiKey': os.environ.get("KUCOIN_API_KEY"),
        'secret': os.environ.get("KUCOIN_SECRET"),
        'password': os.environ.get("KUCOIN_PASSWORD"),
    })
except Exception as e:
    print(f"Błąd inicjalizacji KuCoin: {e}")
    kucoin = None

user_history = {}
user_prefs = {} 
user_models = {} 

# ZWIĘKSZONA PAMIĘĆ BOTA DLA GROQ PREMIUM
MAX_HISTORY = 40 

# --- BAZA DANYCH (Zoptymalizowana) ---
def init_db():
    if not DB_URL: return
    try:
        with psycopg2.connect(DB_URL) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        user_id BIGINT PRIMARY KEY,
                        username TEXT,
                        language TEXT DEFAULT 'EN',
                        model_name TEXT DEFAULT 'llama-3.3-70b-versatile',
                        joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
    except Exception as e:
        print(f"Błąd inicjalizacji DB: {e}")

init_db()

def get_user_data(user_id):
    if user_id in user_prefs and user_id in user_models:
        return user_prefs[user_id], user_models[user_id]
    if not DB_URL: return 'EN', 'llama-3.3-70b-versatile'
    
    try:
        with psycopg2.connect(DB_URL) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT language, model_name FROM users WHERE user_id = %s", (user_id,))
                res = cur.fetchone()
                if res:
                    user_prefs[user_id] = res[0]
                    user_models[user_id] = res[1]
                    return res[0], res[1]
    except Exception as e:
        print(f"Błąd odczytu DB: {e}")
    return 'EN', 'llama-3.3-70b-versatile'

def update_user_db(user_id, username, lang=None, model=None):
    current_lang, current_model = get_user_data(user_id)
    new_lang = lang if lang else current_lang
    new_model = model if model else current_model
    user_prefs[user_id] = new_lang
    user_models[user_id] = new_model
    
    if not DB_URL: return
    try:
        with psycopg2.connect(DB_URL) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO users (user_id, username, language, model_name) 
                    VALUES (%s, %s, %s, %s) 
                    ON CONFLICT (user_id) 
                    DO UPDATE SET language = EXCLUDED.language, model_name = EXCLUDED.model_name, username = EXCLUDED.username
                """, (user_id, username, new_lang, new_model))
    except Exception as e:
        print(f"Błąd zapisu DB: {e}")

# --- API ZEWNĘTRZNE ---
def search_brave_pro(query, count=3):
    if not BRAVE_KEY: return ""
    try:
        url = "https://api.search.brave.com/res/v1/web/search"
        headers = {"Accept": "application/json", "X-Subscription-Token": BRAVE_KEY}
        params = {"q": query, "count": count, "text_decorations": False}
        response = requests.get(url, headers=headers, params=params)
        data = response.json()
        
        results = []
        for r in data.get('web', {}).get('results', []):
            results.append(f"🔹 [{r['title']}]({r['url']})\n   {r['description']}")
        return "\n\n".join(results) if results else ""
    except Exception as e:
        print(f"Błąd Brave API: {e}")
        return ""

def inteligentna_odpowiedz(chat_id, text, thread_id, parse_mode=None, disable_preview=False):
    if thread_id: 
        bot.send_message(chat_id, text, message_thread_id=thread_id, parse_mode=parse_mode, disable_web_page_preview=disable_preview)
    else: 
        bot.send_message(chat_id, text, parse_mode=parse_mode, disable_web_page_preview=disable_preview)

# --- KOMENDY ---
@bot.message_handler(commands=['start'])
def welcome(m):
    update_user_db(m.from_user.id, m.from_user.username, lang='EN', model='llama-3.3-70b-versatile')
    user_history[m.from_user.id] = []
    msg = (
        "Welcome to GentelmeN@CorE! 🎩\n\n"
        "🛠️ **Ustawienia:**\n"
        "/en | /pl - Language\n"
        "/llama | /fast | /qwen - AI Brain\n"
        "/reset - Wyczyść pamięć rozmowy\n\n"
        "🚀 **Narzędzia:**\n"
        "/szukaj [hasło] - Brave Search Pro\n"
        "/github [hasło] - Szukaj repozytoriów\n"
        "/rysuj [opis] - Image Gen (HF Pro)\n"
        "/balance - KuCoin (Admin only)"
    )
    inteligentna_odpowiedz(m.chat.id, msg, m.message_thread_id, parse_mode="Markdown")

@bot.message_handler(commands=['reset', 'clear'])
def reset_memory(m):
    user_id = m.from_user.id
    user_history[user_id] = []
    bot.send_chat_action(m.chat.id, 'typing')
    msg = "🧠 Moja pamięć podręczna została wyczyszczona. Zaczynamy z czystą kartą!"
    inteligentna_odpowiedz(m.chat.id, msg, m.message_thread_id)

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

@bot.message_handler(commands=['szukaj'])
def explicit_search(m):
    query = m.text.replace('/szukaj', '').strip()
    if not query:
        inteligentna_odpowiedz(m.chat.id, "🌐 Co mam wyszukać? Użyj: `/szukaj najnowsze modele LLM`", m.message_thread_id, parse_mode="Markdown")
        return
        
    bot.send_chat_action(m.chat.id, 'typing')
    results = search_brave_pro(query, count=5)
    
    if results:
        inteligentna_odpowiedz(m.chat.id, f"🌐 **Wyniki z Brave:**\n\n{results}", m.message_thread_id, parse_mode="Markdown", disable_preview=True)
    else:
        inteligentna_odpowiedz(m.chat.id, "❌ Brak wyników lub błąd API Brave.", m.message_thread_id)

@bot.message_handler(commands=['github'])
def github_search(m):
    query = m.text.replace('/github', '').strip()
    if not query:
        inteligentna_odpowiedz(m.chat.id, "🐙 Co wyszukać? Użyj: `/github telebot python`", m.message_thread_id, parse_mode="Markdown")
        return

    bot.send_chat_action(m.chat.id, 'typing')
    headers = {"Accept": "application/vnd.github.v3+json"}
    if GITHUB_TOKEN: headers["Authorization"] = f"token {GITHUB_TOKEN}"

    try:
        url = f"https://api.github.com/search/repositories?q={query}&sort=stars&order=desc&per_page=3"
        response = requests.get(url, headers=headers)
        data = response.json()

        if response.status_code == 200 and data.get('items'):
            text = f"🐙 **Top wyniki GitHub dla '{query}':**\n\n"
            for repo in data['items']:
                text += f"🔹 [{repo['full_name']}]({repo['html_url']}) (⭐ {repo['stargazers_count']})\n   {repo.get('description', 'Brak opisu')}\n\n"
            inteligentna_odpowiedz(m.chat.id, text, m.message_thread_id, parse_mode="Markdown", disable_preview=True)
        else:
            inteligentna_odpowiedz(m.chat.id, "❌ Nie znaleziono repozytoriów.", m.message_thread_id)
    except Exception as e:
        inteligentna_odpowiedz(m.chat.id, f"❌ Błąd GitHub: {str(e)}", m.message_thread_id)

@bot.message_handler(commands=['balance'])
def check_balance(m):
    if m.from_user.id != ADMIN_ID:
        inteligentna_odpowiedz(m.chat.id, "🚫 Brak dostępu. Zła autoryzacja ID.", m.message_thread_id)
        return
        
    if not kucoin:
        inteligentna_odpowiedz(m.chat.id, "❌ Błąd: Brak kluczy KuCoin lub błąd połączenia.", m.message_thread_id)
        return

    bot.send_chat_action(m.chat.id, 'typing')
    try:
        balance = kucoin.fetch_balance()
        text = "💰 **Saldo KuCoin:**\n"
        for asset, amount in balance['total'].items():
            if amount > 0: text += f"- {asset}: `{amount}`\n"
        inteligentna_odpowiedz(m.chat.id, text if len(text) > 20 else "Brak środków.", m.message_thread_id, parse_mode="Markdown")
    except Exception as e:
        inteligentna_odpowiedz(m.chat.id, f"❌ Błąd KuCoin: {str(e)}", m.message_thread_id)

@bot.message_handler(commands=['rysuj'])
def generate_image(m):
    prompt = m.text.replace('/rysuj', '').strip()
    if not prompt:
        inteligentna_odpowiedz(m.chat.id, "🎨 Co narysować? Użyj: `/rysuj cyberpunk cat`", m.message_thread_id, parse_mode="Markdown")
        return
        
    if not HF_TOKEN:
        inteligentna_odpowiedz(m.chat.id, "❌ Brak zmiennej HF_TOKEN.", m.message_thread_id)
        return

    inteligentna_odpowiedz(m.chat.id, f"🎨 Maluję (PRO): '{prompt}'...", m.message_thread_id)
    bot.send_chat_action(m.chat.id, 'upload_photo')
    
    API_URL = "https://api-inference.huggingface.co/models/black-forest-labs/FLUX.1-schnell"
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    
    try:
        response = requests.post(API_URL, headers=headers, json={"inputs": prompt})
        if response.status_code == 200:
            image_bytes = io.BytesIO(response.content)
            bot.send_photo(m.chat.id, image_bytes, reply_to_message_id=m.message_id)
        else:
            error_msg = response.json().get('error', 'Nieznany błąd')
            inteligentna_odpowiedz(m.chat.id, f"❌ Błąd serwera HF: {error_msg}", m.message_thread_id)
    except Exception as e:
        inteligentna_odpowiedz(m.chat.id, f"❌ Błąd: {str(e)}", m.message_thread_id)

@bot.message_handler(content_types=['voice'])
def handle_voice(m):
    bot.send_chat_action(m.chat.id, 'typing')
    try:
        file_info = bot.get_file(m.voice.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as temp_audio:
            temp_audio.write(downloaded_file)
            temp_file_name = temp_audio.name

        with open(temp_file_name, "rb") as audio_file:
            transcription = groq_client.audio.transcriptions.create(file=(temp_file_name, audio_file.read()), model="whisper-large-v3")
        
        user_text = transcription.text
        os.remove(temp_file_name)
        
        inteligentna_odpowiedz(m.chat.id, f"🎙️ *Usłyszałem:* {user_text}", m.message_thread_id, parse_mode="Markdown")
        m.text = user_text
        ai_chat(m)
    except Exception as e:
        inteligentna_odpowiedz(m.chat.id, f"❌ Błąd głosu: {str(e)}", m.message_thread_id)

@bot.message_handler(func=lambda m: True)
def ai_chat(m):
    bot.send_chat_action(m.chat.id, 'typing')
    user_id = m.from_user.id
    user_lang, user_model = get_user_data(user_id)
    
    if user_lang == 'EN':
        sys_msg = "You are GentelmeN@CorE, a sovereign digital entity. Speak ONLY English. Never apologize. Format your output nicely."
    else:
        sys_msg = "Jesteś GentelmeN@CorE, suwerennym bytem cyfrowym. Mów TYLKO po polsku. Nigdy nie przepraszaj. Formatuj ładnie tekst (Markdown)."
    
    if any(word in m.text.lower() for word in ["cena", "news", "bitcoin", "kurs", "price", "today"]):
        web_info = search_brave_pro(m.text, count=2)
        if web_info: sys_msg += f"\nOto aktualne dane z sieci (użyj ich do odpowiedzi):\n{web_info}"

    if user_id not in user_history: user_history[user_id] = []
    user_history[user_id].append({"role": "user", "content": m.text})
    messages = [{"role": "system", "content": sys_msg}] + user_history[user_id]

    try:
        completion = groq_client.chat.completions.create(messages=messages, model=user_model)
        reply = completion.choices[0].message.content
        user_history[user_id].append({"role": "assistant", "content": reply})
        if len(user_history[user_id]) > MAX_HISTORY: user_history[user_id] = user_history[user_id][-MAX_HISTORY:]
        inteligentna_odpowiedz(m.chat.id, reply, m.message_thread_id, parse_mode="Markdown")
    except Exception as e:
        inteligentna_odpowiedz(m.chat.id, f"❌ Error Groq: {str(e)}", m.message_thread_id)

print("🚀 Bot się uruchamia... Czekam na zamknięcie starych procesów Railway...")
time.sleep(5)
print("✅ GentelmeN@CorE Online!")
bot.infinity_polling(timeout=60, long_polling_timeout=60)