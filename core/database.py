import logging
import os
import uuid

import psycopg2

DB_URL = os.environ.get("DATABASE_URL")

user_prefs = {}
user_models = {}
# user_id -> (analytics_consent, analytics_id); consent is None when never asked
user_analytics = {}


def init_db():
    if not DB_URL:
        return
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
                # Analytics consent (opt-in) — see core/analytics.py
                cur.execute("""
                    ALTER TABLE users
                        ADD COLUMN IF NOT EXISTS analytics_consent BOOLEAN,
                        ADD COLUMN IF NOT EXISTS analytics_id UUID,
                        ADD COLUMN IF NOT EXISTS analytics_consent_at TIMESTAMP
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
                conn.commit()
    except Exception as e:
        logging.warning(f"DB error: {e}")


def get_user_data(user_id):
    if user_id in user_prefs and user_id in user_models:
        return user_prefs[user_id], user_models[user_id]
    if not DB_URL:
        return 'EN', 'llama-3.3-70b-versatile'
    try:
        with psycopg2.connect(DB_URL) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT language, model_name FROM users WHERE user_id = %s",
                    (user_id,),
                )
                res = cur.fetchone()
                if res:
                    user_prefs[user_id] = res[0]
                    user_models[user_id] = res[1]
                    return res[0], res[1]
    except Exception as e:
        logging.warning(f"DB error: {e}")
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
        with psycopg2.connect(DB_URL) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO users (user_id, username, language, model_name)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (user_id)
                    DO UPDATE SET language = EXCLUDED.language,
                                  model_name = EXCLUDED.model_name,
                                  username = EXCLUDED.username
                """, (user_id, username, new_lang, new_model))
                conn.commit()
    except Exception as e:
        logging.warning(f"DB error: {e}")


def user_exists(user_id):
    """Return True when the user already has a row (used to detect sign-ups).

    On DB errors this returns True, so a sign-up is never reported twice.
    """
    if not DB_URL:
        return user_id in user_prefs
    try:
        with psycopg2.connect(DB_URL) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM users WHERE user_id = %s", (user_id,))
                return cur.fetchone() is not None
    except Exception as e:
        logging.warning(f"DB error: {e}")
        return True


def get_analytics_consent(user_id):
    """Return (consent, analytics_id). consent is None when the user was never asked."""
    if user_id in user_analytics:
        return user_analytics[user_id]
    if not DB_URL:
        return None, None
    try:
        with psycopg2.connect(DB_URL) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT analytics_consent, analytics_id FROM users WHERE user_id = %s",
                    (user_id,),
                )
                res = cur.fetchone()
    except Exception as e:
        logging.warning(f"DB error: {e}")
        return None, None
    if res:
        consent = res[0]
        analytics_id = str(res[1]) if res[1] else None
    else:
        consent, analytics_id = None, None
    user_analytics[user_id] = (consent, analytics_id)
    return consent, analytics_id


def set_analytics_consent(user_id, username, granted):
    """Store the user's analytics choice.

    Returns (analytics_id, previous_analytics_id). Granting keeps an existing
    ID or creates a random UUID; revoking clears it, so a later opt-in starts
    a new, unlinked Mixpanel identity.
    """
    _, previous_id = get_analytics_consent(user_id)
    analytics_id = (previous_id or str(uuid.uuid4())) if granted else None
    user_analytics[user_id] = (granted, analytics_id)

    if not DB_URL:
        return analytics_id, previous_id
    try:
        with psycopg2.connect(DB_URL) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO users (user_id, username, analytics_consent,
                                       analytics_id, analytics_consent_at)
                    VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (user_id)
                    DO UPDATE SET analytics_consent = EXCLUDED.analytics_consent,
                                  analytics_id = EXCLUDED.analytics_id,
                                  analytics_consent_at = EXCLUDED.analytics_consent_at
                """, (user_id, username, granted, analytics_id))
                conn.commit()
    except Exception as e:
        logging.warning(f"DB error: {e}")
    return analytics_id, previous_id
