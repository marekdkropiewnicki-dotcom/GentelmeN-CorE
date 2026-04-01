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

- Tylko 1 branch: `GentelmeN@CorE` ✅
- 5 branchy `copilot/*` → ✅ Usunięte przez Marka (2026-04-01)

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
bot.py                        # Entry point
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

## 📦 Zależności

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
❌ Nie używaj: `GentelmeN-CorE`, `GentelmeN@CorE`, `GentelmenCore`, `Gentlemen_CorE` itp.

---

## 📐 Code Conventions

- **Python 3** — komunikaty bota w PL lub EN
- **Error handling** — każde wywołanie API/DB owijaj w `try/except`
- **Baza danych** — zawsze parametryzowane zapytania (`%s`)
- **Odpowiedzi** — używaj `inteligentna_odpowiedz()`
- **Sekrety** — tylko `os.environ.get(...)`
- **AI chat** — NIE używaj `parse_mode="Markdown"` w `ai_chat()`

---

## ⚠️ Znane ograniczenia (Copilot API)

| Ograniczenie | Alternatywa |
|---|---|
| Draft PR → Ready for review | GitHub app (iOS) → PR → Convert to ready |
| Usuwanie plików | Zastąp pustym plikiem + commit `chore: remove` |
| Merge draftu | Najpierw Ready for review, potem merge |
| Usuwanie branchy | GitHub UI → Branches → 🗑️ |

---

## 📋 Session History

### 2026-03-05
- `copilot-instructions.md` stworzony ✅
- Kanoniczna nazwa: **GeNCorE** ✅
- PR #6 zmergowany — bot stabilny ✅

### 2026-03-06
- PR #7 zmergowany — naming, HF 410, voice routing ✅

### 2026-03-09
- Repo upublicznione ✅
- 5 pustych WIP PRów zamkniętych ✅

### 2026-03-13
- PR #14 (Codex) zmergowany — performance fixes ✅

### 2026-04-01
- Premium requests zresetowane — 100% ✅
- Bug #1 `/rysuj` naprawiony: SDXL → FLUX.1-schnell (`ac1f084`) ✅
- Bug #2 voice→/rysuj — zweryfikowany, już działał ✅
- 5 branchy `copilot/*` → ✅ Usunięte przez Marka
- GeNCorE skrupulatnie przejrzany: 1 branch ✅, 0 otwartych PRów ✅, ostatni commit `259f6bb` ✅
- GeNCorE stabilny — focus przechodzi na `claude-remote-control` 🎯
