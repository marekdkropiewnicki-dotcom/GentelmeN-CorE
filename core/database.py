import os
import psycopg2

DB_URL = os.environ.get("DATABASE_URL")

user_prefs = {}
user_models = {}


def init_db():
    if not DB_URL:
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
    except Exception:
        pass


def get_user_data(user_id):
    if user_id in user_prefs and user_id in user_models:
        return user_prefs[user_id], user_models[user_id]
    if not DB_URL:
        return 'EN', 'llama-3.3-70b-versatile'
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
    except Exception:
        pass
    return 'EN', 'llama-3.3-70b-versatile'


def update_user_db(user_id, username, lang=None, model=None):
    current_lang, current_model = get_user_data(user_id)
    new_lang = lang if lang else current_lang
    new_model = model if model else current_model
    user_prefs[user_id] = new_lang
    user_models[user_id] = new_model
    if not DB_URL:
        return
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
    except Exception:
        pass
