def inteligentna_odpowiedz(
    bot, chat_id, text, thread_id, parse_mode=None, disable_preview=False, reply_markup=None,
):
    extra = {"reply_markup": reply_markup} if reply_markup is not None else {}
    if thread_id:
        bot.send_message(
            chat_id, text,
            message_thread_id=thread_id,
            parse_mode=parse_mode,
            disable_web_page_preview=disable_preview,
            **extra,
        )
    else:
        bot.send_message(
            chat_id, text,
            parse_mode=parse_mode,
            disable_web_page_preview=disable_preview,
            **extra,
        )
