def inteligentna_odpowiedz(bot, chat_id, text, thread_id, parse_mode=None, disable_preview=False):
    if thread_id:
        bot.send_message(
            chat_id, text,
            message_thread_id=thread_id,
            parse_mode=parse_mode,
            disable_web_page_preview=disable_preview,
        )
    else:
        bot.send_message(
            chat_id, text,
            parse_mode=parse_mode,
            disable_web_page_preview=disable_preview,
        )
