import telebot
import ccxt
import os
from groq import Groq

TOKEN = os.environ.get("TELEGRAM_TOKEN")
GROQ_KEY = os.environ.get("GROQ_KEY")

bot = telebot.TeleBot(TOKEN)
groq_client = Groq(api_key=GROQ_KEY)
kucoin = ccxt.kucoin({
    'apiKey': os.environ.get("KUCOIN_API_KEY"),
    'secret': os.environ.get("KUCOIN_SECRET"),
    'password': os.environ.get("KUCOIN_PASSWORD"),
})

@bot.message_handler(commands=['start'])
def welcome(m):
    bot.reply_to(m, "GentelmeN@CorE online! System gotowy do pracy.")

@bot.message_handler(commands=['balance'])
def check_balance(m):
    try:
        balance = kucoin.fetch_balance()
        text = "💰 Saldo Kucoin:\n"
        for asset, amount in balance['total'].items():
            if amount > 0:
                text += f"- {asset}: {amount}\n"
        
        if text == "💰 Saldo Kucoin:\n":
            bot.reply_to(m, "Brak środków na koncie.")
        else:
            bot.reply_to(m, text)
    except Exception as e:
        bot.reply_to(m, f"Błąd portfela: {str(e)}")

@bot.message_handler(func=lambda m: True)
def ai_chat(m):
    try:
        completion = groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": "Jesteś inteligentnym asystentem o nazwie GentelmeN@CorE."},
                {"role": "user", "content": m.text}
            ],
            model="llama-3.1-8b-instant",
        )
        bot.reply_to(m, completion.choices[0].message.content)
    except Exception as e:
        bot.reply_to(m, f"Błąd modułu AI: {str(e)}")

bot.infinity_polling()