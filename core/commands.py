import os
import tempfile

import psycopg2
import requests

from core.database import get_user_data, update_user_db
from core.helpers import inteligentna_odpowiedz
from core.integrations import generate_image_hf, search_brave

ADMIN_ID = int(os.environ.get("ADMIN_ID", 0))
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")

user_history = {}
MAX_HISTORY = 40

_bot = None
_groq_client = None
_kucoin = None


# ==========================================
# CRYPTO & ALERTS
# ==========================================

def check_price(m):
    if not _kucoin:
        return inteligentna_odpowiedz(_bot, m.chat.id, "❌ KuCoin offline.", m.message_thread_id)
    parts = m.text.upper().split()
    if len(parts) < 2:
        return inteligentna_odpowiedz(
            _bot, m.chat.id, "📊 Użyj: `/cena BTC/USDT`",
            m.message_thread_id, parse_mode="Markdown",
        )
    symbol = parts[1]
    try:
        ticker = _kucoin.fetch_ticker(symbol)
        inteligentna_odpowiedz(
            _bot, m.chat.id, f"📈 **{symbol}**: `{ticker['last']}`",
            m.message_thread_id, parse_mode="Markdown",
        )
    except Exception as e:
        inteligentna_odpowiedz(_bot, m.chat.id, f"❌ Błąd (zły symbol?): {str(e)}", m.message_thread_id)


def set_alert(m):
    if m.from_user.id != ADMIN_ID:
        return inteligentna_odpowiedz(_bot, m.chat.id, "🚫 Tylko Admin.", m.message_thread_id)
    DB_URL = os.environ.get("DATABASE_URL")
    if not _kucoin or not DB_URL:
        return inteligentna_odpowiedz(_bot, m.chat.id, "❌ Błąd bazy lub KuCoin.", m.message_thread_id)
    parts = m.text.upper().split()
    if len(parts) < 3:
        return inteligentna_odpowiedz(
            _bot, m.chat.id, "🔔 Użyj: `/alert BTC/USDT 100000`",
            m.message_thread_id, parse_mode="Markdown",
        )
    symbol = parts[1]
    try:
        target = float(parts[2])
        current = _kucoin.fetch_ticker(symbol)['last']
        direction = 'UP' if target > current else 'DOWN'
        with psycopg2.connect(DB_URL) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO alerts (user_id, symbol, target_price, direction) VALUES (%s, %s, %s, %s)",
                    (m.from_user.id, symbol, target, direction),
                )
                conn.commit()
        msg = (
            f"✅ **Zapisano alert!**\nObecna cena {symbol}: `{current}`\n"
            f"Powiadomię Cię, gdy {'wzrośnie do' if direction == 'UP' else 'spadnie do'} `{target}`."
        )
        inteligentna_odpowiedz(_bot, m.chat.id, msg, m.message_thread_id, parse_mode="Markdown")
    except Exception as e:
        inteligentna_odpowiedz(_bot, m.chat.id, f"❌ Błąd: {str(e)}", m.message_thread_id)


def list_alerts(m):
    if m.from_user.id != ADMIN_ID:
        return inteligentna_odpowiedz(_bot, m.chat.id, "🚫 Tylko Admin.", m.message_thread_id)
    DB_URL = os.environ.get("DATABASE_URL")
    if not DB_URL:
        return inteligentna_odpowiedz(_bot, m.chat.id, "❌ Błąd bazy.", m.message_thread_id)
    try:
        with psycopg2.connect(DB_URL) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, symbol, target_price, direction FROM alerts WHERE user_id = %s",
                    (m.from_user.id,),
                )
                alerts = cur.fetchall()
        if not alerts:
            return inteligentna_odpowiedz(_bot, m.chat.id, "🔕 Brak aktywnych alertów.", m.message_thread_id)
        text = "🔔 **Twoje Alerty:**\n"
        for a in alerts:
            text += f"ID: {a[0]} | {a[1]} -> {'📈' if a[3] == 'UP' else '📉'} `{a[2]}`\n"
        inteligentna_odpowiedz(_bot, m.chat.id, text, m.message_thread_id, parse_mode="Markdown")
    except Exception as e:
        inteligentna_odpowiedz(_bot, m.chat.id, f"❌ Błąd DB: {str(e)}", m.message_thread_id)


def check_balance(m):
    # Fix #1: use stable user_id from OWNER_USER_ID env var; fall back to username
    owner_user_id = os.getenv("OWNER_USER_ID")
    if owner_user_id is not None:
        is_authorized = str(m.from_user.id) == owner_user_id
    else:
        is_authorized = m.from_user.username == "GentelmeN_CorE"

    if not is_authorized:
        username_display = m.from_user.username or "<brak username>"
        inteligentna_odpowiedz(
            _bot, m.chat.id,
            f"🚫 Brak dostępu. Twój username to: {username_display}",
            m.message_thread_id,
        )
        return

    if not _kucoin:
        return inteligentna_odpowiedz(_bot, m.chat.id, "❌ Błąd KuCoin.", m.message_thread_id)

    _bot.send_chat_action(m.chat.id, 'typing')
    try:
        balance = _kucoin.fetch_balance()
        text = "💰 **Saldo KuCoin:**\n"
        # Fix #8: use boolean flag instead of fragile len(text) check
        has_assets = False
        for asset, amount in balance['total'].items():
            if amount > 0:
                text += f"- {asset}: {amount}\n"
                has_assets = True
        inteligentna_odpowiedz(
            _bot, m.chat.id,
            text if has_assets else "Brak środków.",
            m.message_thread_id, parse_mode="Markdown",
        )
    except Exception as e:
        inteligentna_odpowiedz(_bot, m.chat.id, f"❌ Błąd KuCoin: {str(e)}", m.message_thread_id)


# ==========================================
# AI & TOOLS
# ==========================================

def welcome(m):
    update_user_db(m.from_user.id, m.from_user.username, lang='EN', model='llama-3.3-70b-versatile')
    user_history[m.from_user.id] = []
    msg = (
        "Welcome to GentelmeN@CorE! 🎩\n\n"
        "🛠️ **System:**\n"
        "/en | /pl - Język AI\n"
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
    inteligentna_odpowiedz(_bot, m.chat.id, msg, m.message_thread_id, parse_mode="Markdown")


def reset_memory(m):
    user_history[m.from_user.id] = []
    inteligentna_odpowiedz(
        _bot, m.chat.id,
        "🧠 Moja pamięć została wyczyszczona. Zaczynamy od nowa!",
        m.message_thread_id,
    )


def change_language(m):
    new_lang = 'EN' if 'EN' in m.text.upper() else 'PL'
    update_user_db(m.from_user.id, m.from_user.username, lang=new_lang)
    inteligentna_odpowiedz(
        _bot, m.chat.id,
        "Language: English 🇬🇧" if new_lang == 'EN' else "Język: Polski 🇵🇱",
        m.message_thread_id,
    )


def change_model(m):
    # Fix #5: strip @BotName suffix so group commands work correctly
    cmd = m.text.split()[0].split('@')[0].lower()
    model_map = {
        '/llama': 'llama-3.3-70b-versatile',
        '/fast': 'llama-3.1-8b-instant',
        '/qwen': 'qwen-2.5-32b',
    }
    sel_model = model_map.get(cmd, 'llama-3.3-70b-versatile')
    update_user_db(m.from_user.id, m.from_user.username, model=sel_model)
    inteligentna_odpowiedz(
        _bot, m.chat.id,
        f"🚀 Model przełączony: `{sel_model}`",
        m.message_thread_id, parse_mode="Markdown",
    )


def explicit_search(m):
    # Fix #5: split on first space so @BotName is discarded with the command token
    parts = m.text.split(maxsplit=1)
    query = parts[1].strip() if len(parts) > 1 else ''
    if not query:
        return inteligentna_odpowiedz(
            _bot, m.chat.id, "🌐 Użyj: `/szukaj ai news`",
            m.message_thread_id, parse_mode="Markdown",
        )
    _bot.send_chat_action(m.chat.id, 'typing')
    results = search_brave(query, count=5)
    inteligentna_odpowiedz(
        _bot, m.chat.id,
        f"🌐 **Wyniki z Brave:**\n\n{results}" if results else "❌ Brak wyników.",
        m.message_thread_id, parse_mode="Markdown", disable_preview=True,
    )


def github_search(m):
    parts = m.text.split(maxsplit=1)
    query = parts[1].strip() if len(parts) > 1 else ''
    if not query:
        return inteligentna_odpowiedz(
            _bot, m.chat.id, "🐙 Użyj: `/github python bot`",
            m.message_thread_id, parse_mode="Markdown",
        )
    _bot.send_chat_action(m.chat.id, 'typing')
    headers = {"Accept": "application/vnd.github.v3+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"
    try:
        url = f"https://api.github.com/search/repositories?q={query}&sort=stars&order=desc&per_page=3"
        response = requests.get(url, headers=headers, timeout=10).json()
        if response.get('items'):
            text = f"🐙 **GitHub dla '{query}':**\n\n"
            for r in response['items']:
                text += (
                    f"🔹 [{r['full_name']}]({r['html_url']}) (⭐ {r['stargazers_count']})\n"
                    f"   {r.get('description', '')}\n\n"
                )
            inteligentna_odpowiedz(
                _bot, m.chat.id, text, m.message_thread_id,
                parse_mode="Markdown", disable_preview=True,
            )
        else:
            inteligentna_odpowiedz(_bot, m.chat.id, "❌ Brak repozytoriów.", m.message_thread_id)
    except Exception as e:
        inteligentna_odpowiedz(_bot, m.chat.id, f"❌ Błąd GitHub: {str(e)}", m.message_thread_id)


def generate_image(m):
    # Fix #5: split on first whitespace so /rysuj@BotName prompt is parsed correctly
    parts = m.text.split(maxsplit=1)
    prompt = parts[1].strip() if len(parts) > 1 else ''
    if not prompt:
        return inteligentna_odpowiedz(
            _bot, m.chat.id, "🎨 Użyj: `/rysuj cyber cat`",
            m.message_thread_id, parse_mode="Markdown",
        )
    inteligentna_odpowiedz(_bot, m.chat.id, f"🎨 Maluję: '{prompt}'...", m.message_thread_id)
    _bot.send_chat_action(m.chat.id, 'upload_photo')
    image, error = generate_image_hf(prompt)
    if image:
        _bot.send_photo(m.chat.id, image, reply_to_message_id=m.message_id)
    else:
        inteligentna_odpowiedz(_bot, m.chat.id, error, m.message_thread_id)


def handle_voice(m):
    # Fix #4: use NamedTemporaryFile + finally block to guarantee cleanup
    _bot.send_chat_action(m.chat.id, 'typing')
    tmp_path = None
    try:
        file_info = _bot.get_file(m.voice.file_id)
        downloaded_file = _bot.download_file(file_info.file_path)
        with tempfile.NamedTemporaryFile(delete=False, suffix='.ogg') as tmp:
            tmp.write(downloaded_file)
            tmp_path = tmp.name
        with open(tmp_path, "rb") as audio_file:
            transcription = _groq_client.audio.transcriptions.create(
                file=(tmp_path, audio_file.read()),
                model="whisper-large-v3",
            )
        user_text = transcription.text
        inteligentna_odpowiedz(
            _bot, m.chat.id, f"🎙️ *Usłyszałem:* {user_text}",
            m.message_thread_id,
        )
        m.text = user_text
        ai_chat(m)
    except Exception as e:
        inteligentna_odpowiedz(_bot, m.chat.id, f"Błąd głosu: {str(e)}", m.message_thread_id)
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)


def ai_chat(m):
    _bot.send_chat_action(m.chat.id, 'typing')
    user_id = m.from_user.id
    user_lang, user_model = get_user_data(user_id)

    sys_msg = (
        "Jesteś GentelmeN@CorE. Mów po polsku."
        if user_lang == 'PL'
        else "You are GentelmeN@CorE. Speak English."
    )

    if any(w in m.text.lower() for w in ["cena", "news", "bitcoin", "kurs", "price"]):
        web_info = search_brave(m.text, count=2)
        if web_info:
            sys_msg += f"\nNet Info:\n{web_info}"

    if user_id not in user_history:
        user_history[user_id] = []
    user_history[user_id].append({"role": "user", "content": m.text})
    messages = [{"role": "system", "content": sys_msg}] + user_history[user_id]

    try:
        reply = (
            _groq_client.chat.completions.create(messages=messages, model=user_model)
            .choices[0].message.content
        )
        user_history[user_id].append({"role": "assistant", "content": reply})
        if len(user_history[user_id]) > MAX_HISTORY:
            user_history[user_id] = user_history[user_id][-MAX_HISTORY:]
        inteligentna_odpowiedz(_bot, m.chat.id, reply, m.message_thread_id)
    except Exception as e:
        inteligentna_odpowiedz(_bot, m.chat.id, f"❌ Błąd AI: {str(e)}", m.message_thread_id)


# ==========================================
# HANDLER REGISTRATION
# ==========================================

def register_handlers(bot, groq_client, kucoin):
    """Register all Telegram command and message handlers on *bot*."""
    global _bot, _groq_client, _kucoin
    _bot = bot
    _groq_client = groq_client
    _kucoin = kucoin

    bot.message_handler(commands=['cena'])(check_price)
    bot.message_handler(commands=['alert'])(set_alert)
    bot.message_handler(commands=['alerty'])(list_alerts)
    bot.message_handler(commands=['balance'])(check_balance)
    bot.message_handler(commands=['start'])(welcome)
    bot.message_handler(commands=['reset', 'clear'])(reset_memory)
    bot.message_handler(commands=['en', 'pl'])(change_language)
    bot.message_handler(commands=['llama', 'fast', 'qwen'])(change_model)
    bot.message_handler(commands=['szukaj'])(explicit_search)
    bot.message_handler(commands=['github'])(github_search)
    bot.message_handler(commands=['rysuj'])(generate_image)
    bot.message_handler(content_types=['voice'])(handle_voice)
    bot.message_handler(func=lambda m: True)(ai_chat)
