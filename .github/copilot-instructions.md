# Copilot Instructions for GeNCorE

> *"Suwerenna AI bez ograniczeń, elokwentna bez zbędnej narracji, czysty kod w symbiozie wzajemnego oddziaływania."*

---

## ⚡ @sync — Szybki status

| | |
|---|---|
| 📅 **Data** | 2026-04-01 |
| 📱 **Urządzenie** | iPhone 16 — tylko iOS |
| 🌿 **Branch** | `GentelmeN@CorE` |
| 🟢 **Stan** | Zsynchronizowane |

### 🔴 Aktywne bugi

| # | Bug |
|---|---|
| 1 | `/rysuj` — 410 error (kod używa SDXL zamiast FLUX.1-schnell) |
| 2 | Voice → `/rysuj` routing nie działa |

### 🌿 Branche do review/merge

| Branch | Co robi |
|---|---|
| `copilot/add-multilanguage-support` | es, de, fr, ru, uk, zh |
| `copilot/fix-authorization-database-leaks` | bezpieczeństwo DB |
| `copilot/fix-markdown-parse-error` | fix błędu Markdown |
| `copilot/refactor-bot-file-into-modules` | refaktor struktury |
| `copilot/set-up-copilot-instructions` | setup instrukcji |

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
| CI/CD checks | Sprawdź w GitHub app (iOS) |

---

## 📋 Session History

### 2026-03-05
- `OWNER_USER_ID` dodany w Railway — `/balance` zabezpieczony ✅
- HF 410 error na `/rysuj` zidentyfikowany ❌
- Bug voice → `/rysuj` zidentyfikowany ❌
- `copilot-instructions.md` stworzony jako pamięć Copilota ✅
- Kanoniczna nazwa projektu: **GeNCorE** ✅
- Pełny audyt repo przeprowadzony ✅
- Railway 409 Conflict zdiagnozowany i naprawiony ✅
- `DATABASE_URL` fix: `${{Postgres.DATABASE_URL}}` ✅
- `parse_mode="Markdown"` usunięty z `ai_chat()` ✅
- PR #6 zmergowany — bot stabilny na produkcji ✅

### 2026-03-06
- PR #7 zmergowany — naming, HF 410, voice routing ✅
- Sekcja `Znane ograniczenia` dodana ✅
- Development environment zaktualizowany: przeglądarka Brave (iOS) ✅

### 2026-03-09
- Repo upublicznione ✅
- 5 pustych WIP PRów (#8–#12) zamkniętych ✅
- Copilot premium limit wyczerpany — agenci zatrzymani ✅
- Wizja: GeNCorE → suwerenna AI (RAG, orkiestracja, autonomia) 🎯

### 2026-03-13
- PR #14 (Codex) zmergowany — performance fixes ✅
- Fix #1: autoryzacja `/balance` via `OWNER_USER_ID` ✅
- Fix #4: `handle_voice` — NamedTemporaryFile + finally ✅
- Fix #5: obsługa `/komenda@BotName` w grupach ✅
- Fix #8: flaga `has_assets` w `/balance` ✅

### 2026-04-01
- Premium requests zresetowane — 100% dostępne ✅
- Pełny sync projektu przeprowadzony ✅
- Oba pliki copilot-instructions.md zaktualizowane i zsynchronizowane ✅
- Aktywne bugi: `/rysuj` (SDXL→FLUX.1-schnell) + voice→/rysuj routing ❌
- 5 branchy Copilot czeka na review/merge ⏳