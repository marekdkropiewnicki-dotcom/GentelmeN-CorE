import telebot
import ccxt
import os
import requests
import psycopg2
import time
import io
import tempfile
import threading
from groq import Groq

# ==========================================
# 1. ZMIENNE ŚRODOWISKOWE I KONFIGURACJA
# ==========================================
TOKEN = os.environ.get("TELEGRAM_TOKEN")
GROQ_KEY = os.environ.get("GROQ_KEY")
BRAVE_KEY = os.environ.get("BRAVE_API_KEY")
DB_URL = os.environ.get("DATABASE_URL")
HF_TOKEN = os.environ.get("HF_TOKEN")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")

ADMIN_ID = int(os.environ.get("ADMIN_ID", 0))
MAX_HISTORY = 40

bot = telebot.TeleBot(TOKEN)
groq_client = Groq(api_key=GROQ_KEY)

# ==========================================
# 2. INICJALIZACJA ZEWNĘTRZNYCH API
# ==========================================
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

# Mapa języków: komenda -> (kod języka, komunikat)
LANG_MAP = {
    '/en': ('EN', 'Language: English 🇬🇧'),
    '/pl': ('PL', 'Język: Polski 🇵🇱'),
    '/es': ('ES', 'Idioma: Español 🇪🇸'),
    '/de': ('DE', 'Sprache: Deutsch 🇩🇪'),
    '/fr': ('FR', 'Langue: Français 🇫🇷'),
    '/ru': ('RU', 'Язык: Русский 🇷🇺'),
    '/uk': ('UK', 'Мова: Українська 🇺🇦'),
    '/zh': ('ZH', '语言：中文 🇨🇳'),
}

# Systemowe prompty dla każdego języka
LANG_PROMPTS = {
    'PL': "Jesteś GeNCorE. Mów po polsku.",
    'EN': "You are GeNCorE. Speak English.",
    'ES': "Eres GeNCorE. Habla en español.",
    'DE': "Du bist GeNCorE. Sprich auf Deutsch.",
    'FR': "Tu es GeNCorE. Parle en français.",
    'RU': "Ты GeNCorE. Говори по-русски.",
    'UK': "Ти GeNCorE. Говори українською.",
    'ZH': "你是GeNCorE。请用中文回答。",
}

# ==========================================
# 3. BAZA DANYCH (POSTGRESQL) - TERAZ Z ALERTAMI
# ==========================================
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
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS alerts (
                        id SERIAL PRIMARY KEY,
                        user_id BIGINT,
                        symbol TEXT,
                        target_price NUMERIC,
                        direction TEXT
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

# ==========================================
# 4. FUNKCJE POMOCNICZE I WYSZUKIWARKA
# ==========================================
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

# ==========================================
# 5. HANDLERY TELEGRAMA (KRYPTO & ALERTY)
# ==========================================
@bot.message_handler(commands=['cena'])
def check_price(m):
    if not kucoin: return inteligentna_odpowiedz(m.chat.id, "❌ KuCoin offline.", m.message_thread_id)
    parts = m.text.upper().split()
    if len(parts) < 2: return inteligentna_odpowiedz(m.chat.id, "📊 Użyj: `/cena BTC/USDT`", m.message_thread_id, parse_mode="Markdown")
    
    symbol = parts[1]
    try:
        ticker = kucoin.fetch_ticker(symbol)
        inteligentna_odpowiedz(m.chat.id, f"📈 **{symbol}**: `{ticker['last']}`", m.message_thread_id, parse_mode="Markdown")
    except Exception as e:
        inteligentna_odpowiedz(m.chat.id, f"❌ Błąd (zły symbol?): {str(e)}", m.message_thread_id)

@bot.message_handler(commands=['alert'])
def set_alert(m):
    if m.from_user.id != ADMIN_ID: return inteligentna_odpowiedz(m.chat.id, "🚫 Tylko Admin.", m.message_thread_id)
    if not kucoin or not DB_URL: return inteligentna_odpowiedz(m.chat.id, "❌ Błąd bazy lub KuCoin.", m.message_thread_id)
    
    parts = m.text.upper().split()
    if len(parts) < 3: return inteligentna_odpowiedz(m.chat.id, "🔔 Użyj: `/alert BTC/USDT 100000`", m.message_thread_id, parse_mode="Markdown")
    
    symbol = parts[1]
    try:
        target = float(parts[2])
        current = kucoin.fetch_ticker(symbol)['last']
        direction = 'UP' if target > current else 'DOWN'
        
        with psycopg2.connect(DB_URL) as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO alerts (user_id, symbol, target_price, direction) VALUES (%s, %s, %s, %s)", 
                            (m.from_user.id, symbol, target, direction))
        
        msg = f"✅ **Zapisano alert!**\nObecna cena {symbol}: `{current}`\nPowiadomię Cię, gdy {'wzrośnie do' if direction=='UP' else 'spadnie do'} `{target}`."
        inteligentna_odpowiedz(m.chat.id, msg, m.message_thread_id, parse_mode="Markdown")
    except Exception as e:
        inteligentna_odpowiedz(m.chat.id, f"❌ Błąd: {str(e)}", m.message_thread_id)

@bot.message_handler(commands=['alerty'])
def list_alerts(m):
    if m.from_user.id != ADMIN_ID: return inteligentna_odpowiedz(m.chat.id, "🚫 Tylko Admin.", m.message_thread_id)
    try:
        with psycopg2.connect(DB_URL) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, symbol, target_price, direction FROM alerts WHERE user_id = %s", (m.from_user.id,))
                alerts = cur.fetchall()
        
        if not alerts: return inteligentna_odpowiedz(m.chat.id, "🔕 Brak aktywnych alertów.", m.message_thread_id)
        
        text = "🔔 **Twoje Alerty:**\n"
        for a in alerts:
            text += f"ID: {a[0]} | {a[1]} -> {'📈' if a[3]=='UP' else '📉'} `{a[2]}`\n"
        inteligentna_odpowiedz(m.chat.id, text, m.message_thread_id, parse_mode="Markdown")
    except Exception as e:
        inteligentna_odpowiedz(m.chat.id, f"❌ Błąd DB: {str(e)}", m.message_thread_id)

@bot.message_handler(commands=['balance'])
def check_balance(m):
    if m.from_user.id != ADMIN_ID: return inteligentna_odpowiedz(m.chat.id, "🚫 Brak dostępu.", m.message_thread_id)
    if not kucoin: return inteligentna_odpowiedz(m.chat.id, "❌ Błąd KuCoin.", m.message_thread_id)

    bot.send_chat_action(m.chat.id, 'typing')
    try:
        balance = kucoin.fetch_balance()
        text = "💰 **Saldo KuCoin:**\n"
        for asset, amount in balance['total'].items():
            if amount > 0: text += f"- {asset}: `{amount}`\n"
        inteligentna_odpowiedz(m.chat.id, text if len(text) > 20 else "Brak środków.", m.message_thread_id, parse_mode="Markdown")
    except Exception as e:
        inteligentna_odpowiedz(m.chat.id, f"❌ Błąd KuCoin: {str(e)}", m.message_thread_id)

# ==========================================
# 6. HANDLERY TELEGRAMA (AI & NARZĘDZIA)
# ==========================================
@bot.message_handler(commands=['start'])
def welcome(m):
    update_user_db(m.from_user.id, m.from_user.username, lang='EN', model='llama-3.3-70b-versatile')
    user_history[m.from_user.id] = []
    msg = (
        "Welcome to GeNCorE! 🎩\n\n"
        "🛠️ **System:**\n"
        "/en | /pl | /es | /de | /fr | /ru | /uk | /zh - Język AI\n"
        "/llama | /fast | /qwen - Mózg AI\n"
        "/reset - Czysta karta\n\n"
        "🚀 **Narzędzia:**\n"
        "/szukaj [hasło] - Wyszukiwarka PRO\n"
        "/github [hasło] - Repozytoria\n"
        "/rysuj [opis] - Sztuka (HF PRO)\n\n"
        "📈 **Krypto:**\n"
        "/cena [symbol] - Np. BTC/USDT\n"
        "/alert [sym] [cena] - Dodaj powiadomienie\n"
        "/alerty - Lista alarmów\n"
        "/balance - Portfel KuCoin"
    )
    inteligentna_odpowiedz(m.chat.id, msg, m.message_thread_id, parse_mode="Markdown")

@bot.message_handler(commands=['reset', 'clear'])
def reset_memory(m):
    user_history[m.from_user.id] = []
    inteligentna_odpowiedz(m.chat.id, "🧠 Moja pamięć została wyczyszczona. Zaczynamy od nowa!", m.message_thread_id)

@bot.message_handler(commands=['en', 'pl', 'es', 'de', 'fr', 'ru', 'uk', 'zh'])
def change_language(m):
    parts = m.text.lower().split()
    cmd = parts[0] if parts else '/en'
    lang_code, lang_msg = LANG_MAP.get(cmd, ('EN', 'Language: English 🇬🇧'))
    update_user_db(m.from_user.id, m.from_user.username, lang=lang_code)
    inteligentna_odpowiedz(m.chat.id, lang_msg, m.message_thread_id)

@bot.message_handler(commands=['llama', 'fast', 'qwen'])
def change_model(m):
    cmd = m.text.lower()
    model_map = {'/llama': 'llama-3.3-70b-versatile', '/fast': 'llama-3.1-8b-instant', '/qwen': 'qwen-2.5-32b'}
    sel_model = model_map.get(cmd, 'llama-3.3-70b-versatile')
    update_user_db(m.from_user.id, m.from_user.username, model=sel_model)
    inteligentna_odpowiedz(m.chat.id, f"🚀 Model przełączony: `{sel_model}`", m.message_thread_id, parse_mode="Markdown")

@bot.message_handler(commands=['szukaj'])
def explicit_search(m):
    query = m.text.replace('/szukaj', '').strip()
    if not query: return inteligentna_odpowiedz(m.chat.id, "🌐 Użyj: `/szukaj ai news`", m.message_thread_id, parse_mode="Markdown")
    bot.send_chat_action(m.chat.id, 'typing')
    results = search_brave_pro(query, count=5)
    inteligentna_odpowiedz(m.chat.id, f"🌐 **Wyniki z Brave:**\n\n{results}" if results else "❌ Brak wyników.", m.message_thread_id, parse_mode="Markdown", disable_preview=True)

@bot.message_handler(commands=['github'])
def github_search(m):
    query = m.text.replace('/github', '').strip()
    if not query: return inteligentna_odpowiedz(m.chat.id, "🐙 Użyj: `/github python bot`", m.message_thread_id, parse_mode="Markdown")
    bot.send_chat_action(m.chat.id, 'typing')
    headers = {"Accept": "application/vnd.github.v3+json"}
    if GITHUB_TOKEN: headers["Authorization"] = f"token {GITHUB_TOKEN}"
    try:
        url = f"https://api.github.com/search/repositories?q={query}&sort=stars&order=desc&per_page=3"
        response = requests.get(url, headers=headers).json()
        if response.get('items'):
            text = f"🐙 **GitHub dla '{query}':**\n\n"
            for r in response['items']:
                text += f"🔹 [{r['full_name']}]({r['html_url']}) (⭐ {r['stargazers_count']})\n   {r.get('description', '')}\n\n"
            inteligentna_odpowiedz(m.chat.id, text, m.message_thread_id, parse_mode="Markdown", disable_preview=True)
        else:
            inteligentna_odpowiedz(m.chat.id, "❌ Brak repozytoriów.", m.message_thread_id)
    except Exception as e:
        inteligentna_odpowiedz(m.chat.id, f"❌ Błąd GitHub: {str(e)}", m.message_thread_id)

@bot.message_handler(commands=['rysuj'])
def generate_image(m):
    prompt = m.text.replace('/rysuj', '').strip()
    if not prompt: return inteligentna_odpowiedz(m.chat.id, "🎨 Użyj: `/rysuj cyber cat`", m.message_thread_id, parse_mode="Markdown")
    if not HF_TOKEN: return inteligentna_odpowiedz(m.chat.id, "❌ Brak HF_TOKEN.", m.message_thread_id)

    inteligentna_odpowiedz(m.chat.id, f"🎨 Maluję: '{prompt}'...", m.message_thread_id)
    bot.send_chat_action(m.chat.id, 'upload_photo')
    
    API_URL = "https://api-inference.huggingface.co/models/black-forest-labs/FLUX.1-schnell"
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    try:
        response = requests.post(API_URL, headers=headers, json={"inputs": prompt})
        if response.status_code == 200:
            bot.send_photo(m.chat.id, io.BytesIO(response.content), reply_to_message_id=m.message_id)
        else:
            inteligentna_odpowiedz(m.chat.id, f"❌ Błąd HF: {response.json().get('error')}", m.message_thread_id)
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
            temp_name = temp_audio.name

        with open(temp_name, "rb") as f:
            transcription = groq_client.audio.transcriptions.create(file=(temp_name, f.read()), model="whisper-large-v3")
        
        os.remove(temp_name)
        inteligentna_odpowiedz(m.chat.id, f"🎙️ *Usłyszałem:* {transcription.text}", m.message_thread_id, parse_mode="Markdown")
        m.text = transcription.text
        ai_chat(m)
    except Exception as e:
        inteligentna_odpowiedz(m.chat.id, f"❌ Błąd głosu: {str(e)}", m.message_thread_id)

@bot.message_handler(func=lambda m: True)
def ai_chat(m):
    bot.send_chat_action(m.chat.id, 'typing')
    user_id = m.from_user.id
    user_lang, user_model = get_user_data(user_id)
    
    sys_msg = LANG_PROMPTS.get(user_lang, LANG_PROMPTS['EN'])
    
    if any(w in m.text.lower() for w in ["cena", "news", "bitcoin", "kurs", "price"]):
        web_info = search_brave_pro(m.text, count=2)
        if web_info: sys_msg += f"\nNet Info:\n{web_info}"

    if user_id not in user_history: user_history[user_id] = []
    user_history[user_id].append({"role": "user", "content": m.text})
    messages = [{"role": "system", "content": sys_msg}] + user_history[user_id]

    try:
        reply = groq_client.chat.completions.create(messages=messages, model=user_model).choices[0].message.content
        user_history[user_id].append({"role": "assistant", "content": reply})
        if len(user_history[user_id]) > MAX_HISTORY: user_history[user_id] = user_history[user_id][-MAX_HISTORY:]
        inteligentna_odpowiedz(m.chat.id, reply, m.message_thread_id, parse_mode="Markdown")
    except Exception as e:
        inteligentna_odpowiedz(m.chat.id, f"❌ Błąd AI: {str(e)}", m.message_thread_id)

# ==========================================
# 7. WĄTEK W TLE: MONITOROWANIE CEN KRYPTO
# ==========================================
def price_monitor():
    while True:
        time.sleep(60) # Sprawdza co 60 sekund
        if not kucoin or not DB_URL: continue
        try:
            with psycopg2.connect(DB_URL) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT id, user_id, symbol, target_price, direction FROM alerts")
                    alerts = cur.fetchall()
                    
                    if not alerts: continue
                    
                    symbols = list(set([a[2] for a in alerts]))
                    tickers = kucoin.fetch_tickers(symbols)
                    
                    for aid, uid, sym, target, direction in alerts:
                        if sym in tickers:
                            curr_price = float(tickers[sym]['last'])
                            target = float(target)
                            
                            # Logika uderzenia w próg
                            hit = (direction == 'UP' and curr_price >= target) or (direction == 'DOWN' and curr_price <= target)
                            
                            if hit:
                                bot.send_message(uid, f"🚨 **ALERT CENOWY!** 🚨\n\n🎯 Przebito próg dla **{sym}**!\n💰 Aktualna cena: `{curr_price}`", parse_mode="Markdown")
                                cur.execute("DELETE FROM alerts WHERE id = %s", (aid,))
                                conn.commit()
        except Exception as e:
            print(f"Błąd monitora cen: {e}")

# Uruchomienie monitora w osobnym wątku
threading.Thread(target=price_monitor, daemon=True).start()

print("🚀 Bot się uruchamia... Czekam na zamknięcie starych procesów Railway...")
time.sleep(5)
print("✅ GeNCorE Online!")
bot.infinity_polling(timeout=60, long_polling_timeout=60)