# --- KOMENDA JĘZYKOWA (Odporna na błędy) ---
@bot.message_handler(commands=['lang', 'langen', 'en', 'pl'])
def change_language(m):
    text = m.text.upper()
    if "EN" in text:
        set_user_lang(m.from_user.id, m.from_user.username, 'EN')
        user_history[m.from_user.id] = [] # Czyścimy pamięć przy zmianie języka
        bot.reply_to(m, "Language strictly set to English! 🇬🇧 I will now respond ONLY in English.")
    else:
        set_user_lang(m.from_user.id, m.from_user.username, 'PL')
        user_history[m.from_user.id] = []
        bot.reply_to(m, "Język ustawiony na polski! 🇵🇱 Będę odpowiadał tylko po polsku.")

# --- GŁÓWNY SILNIK AI ---
@bot.message_handler(func=lambda m: True)
def ai_chat(m):
    user_id = m.from_user.id
    user_lang = get_user_lang(user_id)
    
    # 1. BARDZO Rygorystyczny System Prompt + potężniejszy model
    if user_lang == 'EN':
        sys_msg = "You are GentelmeN@CorE, an advanced AI. Current date: March 2026. CRITICAL RULE: You MUST write ALL your responses ENTIRELY in English. Even if the user asks a question in Polish, German or any other language, you MUST translate your answer and reply ONLY in English. Do not use any Polish words."
    else:
        sys_msg = "Jesteś GentelmeN@CorE, zaawansowaną AI. Mamy Marzec 2026. KRYTYCZNA ZASADA: Musisz odpowiadać TYLKO I WYŁĄCZNIE po polsku. Nawet jeśli użytkownik zada pytanie po angielsku, musisz odpowiedzieć po polsku."
    
    # 2. Sprawdzanie internetu
    web_info = ""
    if any(word in m.text.lower() for word in ["cena", "news", "bitcoin", "krypto", "kurs", "price", "today", "ile", "co"]):
        web_info = search_brave(m.text)
        if web_info:
            sys_msg += f"\nData from the web: {web_info}"

    # 3. Pamięć Konwersacji
    if user_id not in user_history:
        user_history[user_id] = []
        
    user_history[user_id].append({"role": "user", "content": m.text})
    
    messages = [{"role": "system", "content": sys_msg}] + user_history[user_id]

    try:
        # ZMIANA MÓZGU NA POTĘŻNIEJSZY MODEL 70B!
        completion = groq_client.chat.completions.create(
            messages=messages,
            model="llama-3.3-70b-versatile", 
        )
        reply = completion.choices[0].message.content
        
        user_history[user_id].append({"role": "assistant", "content": reply})
        
        if len(user_history[user_id]) > MAX_HISTORY:
            user_history[user_id] = user_history[user_id][-MAX_HISTORY:]
            
        bot.reply_to(m, reply)
    except Exception as e:
        bot.reply_to(m, f"Error: {str(e)}")