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