# Copilot Instructions for GentelmeN-CorE

## Project Overview

**GentelmeN-CorE** is a Telegram bot written in Python. It provides:
- AI chat powered by [Groq](https://groq.com/) (models: `llama-3.3-70b-versatile`, `llama-3.1-8b-instant`, `qwen-2.5-32b`)
- Voice message transcription via Groq Whisper
- Cryptocurrency price checks and price-alert monitoring via KuCoin (ccxt)
- Web search via Brave Search API
- GitHub repository search
- AI image generation via Hugging Face Inference API (FLUX.1-schnell)
- Per-user language (EN/PL) and model preferences stored in PostgreSQL
- `/balance` command restricted to OWNER only (via `OWNER_USER_ID` env variable)

## Repository Structure

```
bot.py           # Main bot entry point (all logic lives here)
railway.json     # Railway deployment config (runs `python bot.py`)
requirements.txt # Python dependencies
configs/         # Configuration files
core/            # Core modules
tests/           # Tests
.github/
  copilot-instructions.md
```

## Running the Bot

```bash
python bot.py
```

Deployment is managed by [Railway](https://railway.com). The start command is `python bot.py`.

## Environment Variables

All secrets are loaded from environment variables — never hard-code them:

| Variable            | Purpose                                      |
|---------------------|----------------------------------------------|
| `TELEGRAM_TOKEN`    | Telegram Bot API token                       |
| `GROQ_KEY`          | Groq API key for AI chat & transcription     |
| `BRAVE_API_KEY`     | Brave Search API key                         |
| `DATABASE_URL`      | PostgreSQL connection string                 |
| `HF_TOKEN`          | Hugging Face API token for image generation  |
| `GITHUB_TOKEN`      | GitHub API token for repository search       |
| `KUCOIN_API_KEY`    | KuCoin exchange API key                      |
| `KUCOIN_SECRET`     | KuCoin exchange secret                       |
| `KUCOIN_PASSWORD`   | KuCoin exchange passphrase                   |
| `ADMIN_ID`          | Telegram user ID of the bot admin            |
| `OWNER_USER_ID`     | Telegram user ID of the owner (for /balance) |

## Dependencies (`requirements.txt`)

- `pyTelegramBotAPI` — Telegram bot framework
- `requests` — HTTP client
- `groq` — Groq SDK for AI and transcription
- `ccxt` — Cryptocurrency exchange library (KuCoin)
- `psycopg2-binary` — PostgreSQL adapter

Install with:
```bash
pip install -r requirements.txt
```

## Code Conventions

- **Language**: Python 3; bot messages can be Polish or English depending on user preference.
- **Error handling**: Wrap all external API/DB calls in `try/except` and reply with a user-friendly error message — never let exceptions bubble up to the bot framework.
- **Database**: Use PostgreSQL via `psycopg2`. Always use parameterised queries (`%s` placeholders). Gracefully skip DB operations when `DATABASE_URL` is not set.
- **Telegram replies**: Use `inteligentna_odpowiedz()` helper for all outgoing messages so that Telegram Supergroup thread IDs (`message_thread_id`) are handled correctly.
- **No secrets in code**: Read every credential from `os.environ.get(...)`.
- **Background threads**: Long-running tasks (e.g. price monitor) run as daemon threads so they don't block bot shutdown.
- **Access control**: `/balance` and other sensitive commands check `OWNER_USER_ID` before executing.

## Adding New Commands

1. Decorate a handler with `@bot.message_handler(commands=['your_command'])`.
2. Parse arguments from `m.text`.
3. Use `inteligentna_odpowiedz(m.chat.id, ..., m.message_thread_id)` to send replies.
4. Add the new command to the `/start` welcome message.
5. Handle all exceptions and reply with a clear error.

## Known Issues (as of 2026-03-05)

- **HF image generation** (`/rysuj`): Returns 410 error — model FLUX.1-schnell may have changed endpoint. Needs new HF model or updated API call.
- **Voice → /rysuj**: Voice messages are not being forwarded to image generation handler. Bug to fix.

## Testing

There is no automated test suite in the repository. Manual testing is done by running the bot against a real Telegram bot token. When adding significant logic, consider adding unit tests using `pytest` (which is not yet a listed dependency — add it to `requirements.txt` if tests are introduced).

## Session History

### 2026-03-05
- Added `OWNER_USER_ID` env variable in Railway to restrict `/balance` to owner only
- Identified HF 410 error on `/rysuj` (image generation)
- Identified voice message → `/rysuj` bug
- Added `.github/copilot-instructions.md` as Copilot memory