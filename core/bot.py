import os
import threading
import time

import ccxt
import psycopg2
import telebot
from groq import Groq

from core.commands import register_handlers
from core.database import init_db

TOKEN = os.environ.get("TELEGRAM_TOKEN")
GROQ_KEY = os.environ.get("GROQ_KEY")
DB_URL = os.environ.get("DATABASE_URL")

# Fix #6: fail fast when required environment variables are absent
if not TOKEN:
    raise RuntimeError("Required environment variable TELEGRAM_TOKEN is not set.")
if not GROQ_KEY:
    raise RuntimeError("Required environment variable GROQ_KEY is not set.")

bot = telebot.TeleBot(TOKEN)
groq_client = Groq(api_key=GROQ_KEY)

try:
    kucoin = ccxt.kucoin({
        'apiKey': os.environ.get("KUCOIN_API_KEY"),
        'secret': os.environ.get("KUCOIN_SECRET"),
        'password': os.environ.get("KUCOIN_PASSWORD"),
    })
except Exception as e:
    print(f"Błąd inicjalizacji KuCoin: {e}")
    kucoin = None

init_db()
register_handlers(bot, groq_client, kucoin)


def price_monitor():
    while True:
        time.sleep(60)
        if not kucoin or not DB_URL:
            continue
        try:
            with psycopg2.connect(DB_URL) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT id, user_id, symbol, target_price, direction FROM alerts"
                    )
                    alerts = cur.fetchall()

                    if not alerts:
                        continue

                    symbols = list({a[2] for a in alerts})
                    tickers = kucoin.fetch_tickers(symbols)

                    for aid, uid, sym, target, direction in alerts:
                        if sym in tickers:
                            curr_price = float(tickers[sym]['last'])
                            target = float(target)

                            hit = (
                                (direction == 'UP' and curr_price >= target)
                                or (direction == 'DOWN' and curr_price <= target)
                            )

                            if hit:
                                bot.send_message(
                                    uid,
                                    f"🚨 **ALERT CENOWY!** 🚨\n\n🎯 Przebito próg dla **{sym}**!\n"
                                    f"💰 Aktualna cena: `{curr_price}`",
                                    parse_mode="Markdown",
                                )
                                cur.execute("DELETE FROM alerts WHERE id = %s", (aid,))
                                conn.commit()
        except Exception as e:
            print(f"Błąd monitora cen: {e}")


threading.Thread(target=price_monitor, daemon=True).start()

print("🚀 Bot się uruchamia... Czekam na zamknięcie starych procesów Railway...")
time.sleep(5)
print("✅ GentelmeN@CorE Online!")
bot.infinity_polling(timeout=60, long_polling_timeout=60)
