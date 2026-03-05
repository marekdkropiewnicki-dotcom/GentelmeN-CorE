# GentelmeN@CorE — Copilot Instructions

## Projekt
Bot Telegram (Python) uruchamiany na Railway Pro.
Plik główny: `bot.py`
Gałąź: `GentelmeN@CorE`

## Stack technologiczny
- Python + pyTelegramBotAPI (telebot)
- Groq API — LLM + Whisper STT
- Brave Search API — wyszukiwarka PRO
- KuCoin (ccxt) — krypto, alerty, saldo
- HuggingFace Inference API — FLUX.1-schnell
- PostgreSQL (psycopg2)
- GitHub API
- Gravatar API
- Railway — hosting

## Plany Pro
| Serwis | Plan |
|---|---|
| Railway | Pro ($20/mies) |
| Brave Leo AI | Pro ($14.99/mies) |
| Brave VPN | Monthly ($9.99/mies) |
| Brave Search | Pro ($3/mies) |
| HuggingFace | PRO |
| KuCoin | VIP K1 |
| Telegram | Premium |
| GitHub | Pro |
| GitHub Copilot | Pro |
| Groq | Flex Service Tier |
| Gravatar | Pro |

## Zmienne środowiskowe (Railway)
- TELEGRAM_TOKEN
- GROQ_KEY
- BRAVE_API_KEY
- DATABASE_URL
- HF_TOKEN
- GITHUB_TOKEN
- ADMIN_ID
- KUCOIN_API_KEY
- KUCOIN_SECRET
- KUCOIN_PASSWORD

## Modele AI (Groq)
| Komenda | Model |
|---|---|
| /llama | llama-3.3-70b-versatile |
| /fast | llama-3.1-8b-instant |
| /qwen | qwen-2.5-32b |

## Komendy bota
- /start, /reset, /clear, /en, /pl
- /llama, /fast, /qwen
- /szukaj, /github, /rysuj
- /cena, /alert, /alerty, /balance
- Wiadomości głosowe (Whisper)

## Zasady kodowania
- Komentarze po polsku
- Klucze API z os.environ.get()
- Obsługa wyjątków przy każdym API
- Używaj inteligentna_odpowiedz() do wysyłania
- MAX_HISTORY = 40 wiadomości
- Admin-only: sprawdzaj m.from_user.id != ADMIN_ID