# Copilot Instructions for GeNCorE

> *"Suwerenna AI bez ograniczeń, elokwentna bez zbędnej narracji, czysty kod w symbiozie wzajemnego oddziaływania."*

---

## ⚡ @sync — Szybki status

| | |
|---|---|
| 📅 **Data** | 2026-04-01 |
| 📱 **Urządzenie** | iPhone 16 — tylko iOS |
| 🌿 **Branch** | `GentelmeN@CorE` |
| 🟢 **Stan** | Stabilny — produkcja działa |

### ✅ Bugi — rozwiązane

| # | Bug | Status |
|---|---|---|
| 1 | `/rysuj` — 410 error (SDXL → FLUX.1-schnell) | ✅ Naprawiony `ac1f084` |
| 2 | Voice → `/rysuj` routing | ✅ Działało — zweryfikowane |

### 🌿 Branche

Wszystkie 5 branchy `copilot/*` — **do usunięcia przez Marka w GitHub UI**.
Kod ze wszystkich branchy już jest w `GentelmeN@CorE`. ✅
👉 https://github.com/marekdkropiewnicki-dotcom/GentelmeN-CorE/branches

---

## 🚀 Project Overview

**GeNCorE** — Telegram bot napisany w Pythonie. Deployment na Railway.

| Komponent | Technologia |
|---|---|
| AI chat | Groq (`llama-3.3-70b-versatile`, `llama-3.1-8b-instant`, `qwen-2.5-32b`) |
| Transkrypcja głosu | Groq Whisper |
| Generowanie obrazów | Hugging Face (FLUX.1-schnell) |
| Kryptowaluty | KuCoin via `ccxt` |
| Wyszukiwanie | Brave Search API |
| GitHub search | GitHub REST API |
| Baza danych | PostgreSQL via `psycopg2` |
| Deployment | Railway Pro |

---

## 🗂️ Struktura repo

```
bot.py                        # Entry point — uruchamia core/bot.py via runpy
railway.json                  # Railway deployment config
requirements.txt              # Zależności Python
configs/
  example.env                 # Szablon zmiennych środowiskowych
core/
  __init__.py
  bot.py                      # Startup bota + wątek monitora cen
  commands.py                 # Wszystkie handlery komend Telegram
  database.py                 # Operacje PostgreSQL
  helpers.py                  # inteligentna_odpowiedz()
  integrations.py             # Brave Search + HF image generation
tests/
  test_commands.py            # Testy pytest
.github/
  copilot-instructions.md     # Ten plik
```

---

## 🔑 Zmienne środowiskowe

| Zmienna | Cel |
|---|---|
| `TELEGRAM_TOKEN` | Telegram Bot API token |
| `GROQ_KEY` | Groq API — AI chat + Whisper |
| `BRAVE_API_KEY` | Brave Search API |
| `DATABASE_URL` | PostgreSQL connection string |
| `HF_TOKEN` | Hugging Face — generowanie obrazów |
| `GITHUB_TOKEN` | GitHub API — wyszukiwanie repo |
| `KUCOIN_API_KEY` | KuCoin API key |
| `KUCOIN_SECRET` | KuCoin secret |
| `KUCOIN_PASSWORD` | KuCoin passphrase |
| `ADMIN_ID` | Telegram user ID admina |
| `OWNER_USER_ID` | Telegram user ID właściciela (dla `/balance`) |

> Nigdy nie hardkoduj sekretów — zawsze `os.environ.get(...)`.

---

## 📦 Zależności (`requirements.txt`)

| Pakiet | Cel |
|---|---|
| `pyTelegramBotAPI` | Framework Telegram bota |
| `requests` | HTTP client |
| `groq` | Groq SDK — AI chat + transkrypcja |
| `ccxt` | KuCoin exchange |
| `psycopg2-binary` | PostgreSQL adapter |
| `pytest` | Testy jednostkowe |

---

## 🏷️ Naming Convention

Kanoniczna nazwa projektu to **GeNCorE**.
Wszystkie referencje w kodzie, komentarzach i dokumentacji muszą używać `GeNCorE`.
❌ Nie używaj: `GentelmeN-CorE`, `GentelmeN@CorE`, `GentelmenCore`, `Gentlemen_CorE` itp.

---

## 📐 Code Conventions

- **Python 3** — komunikaty bota w PL lub EN zależnie od preferencji użytkownika
- **Error handling** — każde wywołanie API/DB owijaj w `try/except`, odpowiadaj user-friendly
- **Baza danych** — `psycopg2`, zawsze parametryzowane zapytania (`%s`), graceful skip gdy brak `DATABASE_URL`
- **Odpowiedzi** — używaj `inteligentna_odpowiedz()` dla wszystkich wiadomości wychodzących
- **Sekrety** — tylko `os.environ.get(...)`
- **Wątki** — długie zadania (monitor cen) jako daemon threads
- **AI chat** — NIE używaj `parse_mode="Markdown"` w `ai_chat()` — Groq zwraca niesformatowany Markdown który łamie Telegram API (error 400)

---

## ➕ Dodawanie nowych komend

1. Handler: `@bot.message_handler(commands=['komenda'])`
2. Parsuj argumenty z `m.text`
3. Odpowiedzi przez `inteligentna_odpowiedz(_bot, m.chat.id, ..., m.message_thread_id)`
4. Dodaj komendę do wiadomości `/start`
5. Obsłuż wszystkie wyjątki

---

## ⚠️ Znane ograniczenia (Copilot API)

| Ograniczenie | Alternatywa |
|---|---|
| Draft PR → Ready for review | GitHub app (iOS) → PR → Convert to ready |
| Usuwanie plików | Zastąp pustym plikiem + commit `chore: remove` |
| Merge draftu | Najpierw Ready for review, potem merge |
| Usuwanie branchy | GitHub UI → Branches → 🗑️ |
| CI/CD checks | Sprawdź w GitHub app (iOS) |

---

## 📋 Session History

### 2026-03-05
- `OWNER_USER_ID` dodany w Railway — `/balance` zabezpieczony ✅
- `copilot-instructions.md` stworzony ✅
- Kanoniczna nazwa: **GeNCorE** ✅
- Railway 409 Conflict naprawiony ✅
- `DATABASE_URL` fix: `${{Postgres.DATABASE_URL}}` ✅
- `parse_mode="Markdown"` usunięty z `ai_chat()` ✅
- PR #6 zmergowany — bot stabilny ✅

### 2026-03-06
- PR #7 zmergowany — naming, HF 410, voice routing ✅

### 2026-03-09
- Repo upublicznione ✅
- 5 pustych WIP PRów zamkniętych ✅
- Copilot premium limit wyczerpany ✅

### 2026-03-13
- PR #14 (Codex) zmergowany — performance fixes ✅

### 2026-04-01
- Premium requests zresetowane — 100% ✅
- Bug #1 `/rysuj` naprawiony: SDXL → FLUX.1-schnell (`ac1f084`) ✅
- Bug #2 voice→/rysuj — zweryfikowany, już działał ✅
- 5 branchy `copilot/*` — do usunięcia przez Marka (GitHub UI) ⏳
- GeNCorE stabilny — focus przechodzi na `claude-remote-control` 🎯