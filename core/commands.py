import os

from core.database import get_user_data, update_user_db
from core.helpers import MAX_HISTORY, inteligentna_odpowiedz, user_history
from core.integrations import generate_image_hf, search_brave


def register_handlers(bot, groq_client, kucoin):
    @bot.message_handler(commands=['start'])
    def welcome(m):
        update_user_db(m.from_user.id, m.from_user.username, lang='EN', model='llama-3.3-70b-versatile')
        user_history[m.from_user.id] = []
        inteligentna_odpowiedz(
            bot, m.chat.id,
            "Welcome to GentelmeN@CorE!\n/en | /pl - Language\n/llama | /fast | /qwen - AI Brain\n/balance - KuCoin\n/rysuj [opis] - Image Gen",
            m.message_thread_id,
        )

    @bot.message_handler(commands=['en', 'pl'])
    def change_language(m):
        new_lang = 'EN' if 'EN' in m.text.upper() else 'PL'
        update_user_db(m.from_user.id, m.from_user.username, lang=new_lang)
        msg = "Language: English 🇬🇧" if new_lang == 'EN' else "Język: Polski 🇵🇱"
        inteligentna_odpowiedz(bot, m.chat.id, msg, m.message_thread_id)

    @bot.message_handler(commands=['llama', 'fast', 'qwen'])
    def change_model(m):
        cmd = m.text.lower()
        model_map = {
            '/llama': 'llama-3.3-70b-versatile',
            '/fast': 'llama-3.1-8b-instant',
            '/qwen': 'qwen-2.5-32b',
        }
        selected_model = model_map.get(cmd, 'llama-3.3-70b-versatile')
        update_user_db(m.from_user.id, m.from_user.username, model=selected_model)
        inteligentna_odpowiedz(bot, m.chat.id, f"🚀 Brain switched to: {selected_model}", m.message_thread_id)

    @bot.message_handler(commands=['balance'])
    def check_balance(m):
        if m.from_user.username != "GentelmeN_CorE":
            inteligentna_odpowiedz(
                bot, m.chat.id,
                f"🚫 Brak dostępu. Twój username to: {m.from_user.username}",
                m.message_thread_id,
            )
            return
        if not kucoin:
            inteligentna_odpowiedz(bot, m.chat.id, "❌ Błąd: Brak kluczy KuCoin w Railway.", m.message_thread_id)
            return
        inteligentna_odpowiedz(bot, m.chat.id, "🔄 Łączę się z KuCoin...", m.message_thread_id)
        try:
            balance = kucoin.fetch_balance()
            text = "💰 Saldo KuCoin:\n"
            for asset, amount in balance['total'].items():
                if amount > 0:
                    text += f"- {asset}: {amount}\n"
            inteligentna_odpowiedz(bot, m.chat.id, text if len(text) > 18 else "Brak środków.", m.message_thread_id)
        except Exception as e:
            inteligentna_odpowiedz(bot, m.chat.id, f"❌ Błąd KuCoin: {str(e)}", m.message_thread_id)

    @bot.message_handler(commands=['rysuj'])
    def generate_image(m):
        prompt = m.text.replace('/rysuj', '').strip()
        if not prompt:
            inteligentna_odpowiedz(
                bot, m.chat.id,
                "🎨 Co mam narysować? Użyj: /rysuj cyberpunkowy kot",
                m.message_thread_id,
            )
            return
        inteligentna_odpowiedz(bot, m.chat.id, f"🎨 Maluję: '{prompt}'... (10-20 sekund)", m.message_thread_id)
        image_bytes, error = generate_image_hf(prompt)
        if image_bytes:
            bot.send_photo(m.chat.id, image_bytes, reply_to_message_id=m.message_id)
        else:
            inteligentna_odpowiedz(bot, m.chat.id, error, m.message_thread_id)

    @bot.message_handler(content_types=['voice'])
    def handle_voice(m):
        try:
            file_info = bot.get_file(m.voice.file_id)
            downloaded_file = bot.download_file(file_info.file_path)
            file_name = f"voice_{m.chat.id}.ogg"
            with open(file_name, 'wb') as new_file:
                new_file.write(downloaded_file)
            with open(file_name, "rb") as audio_file:
                transcription = groq_client.audio.transcriptions.create(
                    file=(file_name, audio_file.read()),
                    model="whisper-large-v3",
                )
            user_text = transcription.text
            os.remove(file_name)
            inteligentna_odpowiedz(bot, m.chat.id, f"🎙️ *Usłyszałem:* {user_text}", m.message_thread_id)
            m.text = user_text
            ai_chat(m)
        except Exception as e:
            inteligentna_odpowiedz(bot, m.chat.id, f"Błąd głosu: {str(e)}", m.message_thread_id)

    @bot.message_handler(func=lambda m: True)
    def ai_chat(m):
        user_id = m.from_user.id
        user_lang, user_model = get_user_data(user_id)
        if user_lang == 'EN':
            sys_msg = "You are GentelmeN@CorE, a sovereign digital entity. Speak ONLY English. Never apologize."
        else:
            sys_msg = "Jesteś GentelmeN@CorE, suwerennym bytem cyfrowym. Mów TYLKO po polsku. Nigdy nie przepraszaj."

        web_info = ""
        if any(word in m.text.lower() for word in ["cena", "news", "bitcoin", "kurs", "price", "today"]):
            web_info = search_brave(m.text)
            if web_info:
                sys_msg += f"\nWeb data: {web_info}"

        if user_id not in user_history:
            user_history[user_id] = []
        user_history[user_id].append({"role": "user", "content": m.text})
        messages = [{"role": "system", "content": sys_msg}] + user_history[user_id]

        try:
            completion = groq_client.chat.completions.create(messages=messages, model=user_model)
            reply = completion.choices[0].message.content
            user_history[user_id].append({"role": "assistant", "content": reply})
            if len(user_history[user_id]) > MAX_HISTORY:
                user_history[user_id] = user_history[user_id][-MAX_HISTORY:]
            inteligentna_odpowiedz(bot, m.chat.id, reply, m.message_thread_id)
        except Exception as e:
            inteligentna_odpowiedz(bot, m.chat.id, f"Error: {str(e)}", m.message_thread_id)
