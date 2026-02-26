import telebot

bot = telebot.TeleBot("8616433290:AAHj-PNbbp2gmgzzd7PMD-E-Yj48wQNAJ64")

@bot.message_handler(func=lambda m: True)
def echo(m):
    bot.reply_to(m, "GentelmeN@CorE online!")

bot.infinity_polling()