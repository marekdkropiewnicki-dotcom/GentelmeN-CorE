user_history = {}
MAX_HISTORY = 6


def inteligentna_odpowiedz(bot, chat_id, text, thread_id):
    if thread_id:
        bot.send_message(chat_id, text, message_thread_id=thread_id)
    else:
        bot.send_message(chat_id, text)
