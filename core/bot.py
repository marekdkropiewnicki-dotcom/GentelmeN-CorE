import os
import time

import telebot
from groq import Groq

from core.commands import register_handlers
from core.database import init_db
from core.integrations import init_kucoin

TOKEN = os.environ.get("TELEGRAM_TOKEN")
GROQ_KEY = os.environ.get("GROQ_KEY")

bot = telebot.TeleBot(TOKEN)
groq_client = Groq(api_key=GROQ_KEY)
kucoin = init_kucoin()

init_db()
register_handlers(bot, groq_client, kucoin)

print("Czekam 10 sekund na zamknięcie starych procesów Railway...")
time.sleep(10)
bot.infinity_polling()
