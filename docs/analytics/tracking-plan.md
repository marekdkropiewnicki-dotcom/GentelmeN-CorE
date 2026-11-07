# GeNCorE — Mixpanel Tracking Plan

| | |
|---|---|
| **Status** | Draft for review — approve or change it in the pull request |
| **Data owner** | Marek (approves every new event before it ships) |
| **Tracking method** | Server-side, Python SDK (`mixpanel`), opt-in consent |
| **Last updated** | 2026-11-07 |

## 1. Context

GeNCorE is a Telegram AI assistant: AI chat (Groq), voice messages (Whisper), image generation, web and GitHub search, and crypto prices. Users start it with `/start`; there is no separate account, login or logout.

The commercial priority right now is **activation and engagement**: do people who start the bot come back to talk to it?

## 2. Analytics strategy

**Value Moment:** `ai_reply_sent` — a user receives an AI answer. Natural frequency: daily.

| KPI (RAE) | Definition | Mixpanel report |
|---|---|---|
| **Reach** | New opted-in users per week | Insights: total `sign_up_completed`, weekly |
| **Activation** | Share of new users with at least one `ai_reply_sent` within 24 hours of `sign_up_completed` | Funnel: `sign_up_completed` → `ai_reply_sent`, 1-day window |
| **Engagement** | Weekly active users: unique users with 3+ `ai_reply_sent` in a week | Insights: unique users, weekly, filter count ≥ 3 |

All three are meaningful, measurable from day one, small enough to manage, movable by product work and time-bound (weekly).

**Consent rate is not in Mixpanel.** Users who decline send nothing, so measure it in PostgreSQL: `SELECT analytics_consent, count(*) FROM users GROUP BY 1;`

## 3. Project setup

| Setting | Value |
|---|---|
| **Data residency** | EU — events go to `api-eu.mixpanel.com` (`MIXPANEL_API_HOST`) |
| **Projects** | `GeNCorE - Development` and `GeNCorE - Production`, one token per Railway environment |
| **Timezone** | Europe/Dublin — set when creating each project; it can't be changed retroactively |
| **Identity mode** | Simplified ID Merge (the default). GeNCorE has no anonymous phase, so no merges happen |
| **Token** | `MIXPANEL_TOKEN` environment variable — never in code or in the repository |

If a project was created with US residency, set `MIXPANEL_API_HOST=api.mixpanel.com`. Residency is fixed per project.

## 4. Consent and privacy

- **Opt-in.** After `/start` the bot asks once. Nothing is sent before the user taps "Zgadzam się". Users who decline are never tracked.
- **Change anytime** with `/analityka` (alias `/analytics`).
- **Stored server-side** in `users.analytics_consent` and `users.analytics_consent_at`. The bot checks consent before every Mixpanel call.
- **Withdrawal** deletes the Mixpanel profile and clears `analytics_id`. A later opt-in starts a new, unlinked identity. Events already sent stay in Mixpanel until deleted through Mixpanel's data deletion tools — handle erasure requests there.
- **Data minimisation.** No message content, prompts, usernames, Telegram IDs or IP addresses. The SDK sends `ip=0` on every request and profile updates send `$ip: 0`, so Mixpanel doesn't geolocate users by the server's address.
- Add a short privacy notice that explains this. This plan is implementation guidance, not legal advice.

## 5. Identity

| Item | Value |
|---|---|
| **distinct_id** | `users.analytics_id` — a random UUID v4 created at opt-in |
| **Never used as an ID** | Telegram user ID, username, email |
| **Profile properties** (set at opt-in) | `language` (string, `"en"` / `"pl"`), `ai_model` (string), `analytics_consent_at` (datetime, UTC) |

Order at sign-up: user row created on `/start` → consent stored → profile set → `sign_up_completed` tracked.

## 6. Global properties (sent with every event)

| Property | Type | Value |
|---|---|---|
| `platform` | string | `"telegram"` |
| `environment` | string | Railway environment name, or `"local"` |
| `app_version` | string | First 7 characters of `RAILWAY_GIT_COMMIT_SHA`, or `"local"` |

## 7. Events

### Implemented

| Event | Trigger | Properties | Code |
|---|---|---|---|
| `sign_up_completed` | A new user (first `/start`) taps "Zgadzam się" in the consent prompt. Fires once per user, after the profile is set | `sign_up_method` (string, `"telegram_start"`), `language` (string), `chat_type` (string: `private` / `group` / `supergroup`), `referral_source` (string, optional — the `/start` deep-link payload, omitted when absent) | `core/commands.py` → `handle_analytics_consent`; `core/analytics.py` → `record_consent_granted` |
| `ai_reply_sent` | An AI reply was delivered to the user | `model` (string), `language` (string), `input_type` (string: `text` / `voice`), `chat_type` (string), `is_web_context_used` (boolean), `history_message_count` (number), `reply_character_count` (number) | `core/commands.py` → `ai_chat` |

### Planned — add after both events above are confirmed in Live View

| Event | Trigger | Properties |
|---|---|---|
| `image_generated` | `/rysuj` returns an image | `input_type`, `prompt_character_count`, `provider`, `model` |
| `image_generation_failed` | `/rysuj` returns an error | `input_type`, `error_type` (`http_4xx` / `http_5xx` / `timeout` / `missing_token` / `connection`) |
| `voice_message_transcribed` | Whisper transcription succeeds | `routed_to` (`ai_chat` / `image`) |
| `ai_reply_failed` | The Groq call fails | `model`, `error_type` |
| `web_search_performed` | `/szukaj` returns | `result_count`, `is_empty` |
| `github_search_performed` | `/github` returns | `result_count` |
| `crypto_price_checked` | `/cena` succeeds | `symbol` (e.g. `"BTC/USDT"`) |
| `ai_model_changed` | `/llama`, `/fast`, `/qwen` | `model` |
| `language_changed` | `/en`, `/pl` | `language` |
| `conversation_reset` | `/reset` | `history_message_count` |

Admin-only commands (`/alert`, `/alerty`, `/balance`) are intentionally not tracked.

## 8. Naming conventions

- Events: `object_verb` in past tense, `snake_case` — `ai_reply_sent`, not `AI Reply` or `replySent`.
- Properties: `snake_case`, full words, booleans start with `is_`.
- Values: lowercase, consistent strings. Send numbers as numbers.
- Omit properties that don't apply — never send `null`, `""` or `"N/A"`.
- No `$` or `mp_` prefixes on custom names, and never build names at runtime.
- One event, one meaning. Before adding an event, check this plan and Lexicon.

## 9. Governance

- **Approval:** a new event ships only after it is added here and approved in a pull request.
- **Lexicon:** add a one-sentence description to both events and every property (copy the trigger column).
- **Data Standards and Event Approval:** enable both in the Production project, so unreviewed names wait in a queue.
- **Hide before drop:** hide a deprecated event for one quarter before dropping it — dropping can't be undone.
- **Quarterly review:** zero-volume events, missing descriptions, naming drift.

## 10. Verification in Live View

1. Create `GeNCorE - Development` (EU residency, Europe/Dublin) and copy its project token.
2. Set `MIXPANEL_TOKEN` (and `MIXPANEL_API_HOST` if needed) in a non-production Railway environment or locally, and run this branch.
3. From a Telegram account that never used the bot, open `t.me/<bot_username>?start=test_ref` and tap "Zgadzam się".
4. In Live View, check that a profile appeared and `sign_up_completed` arrived with `sign_up_method = telegram_start` and `referral_source = test_ref`.
5. Send a text message and a voice message. Each should produce `ai_reply_sent`, with `input_type` set to `text` and `voice`.
6. Run `/analityka`, tap "Nie, dziękuję", send another message. The profile should disappear and no new event should arrive.
7. In Insights, filter each event by today's date and check property values. Event names are case-sensitive.
8. Only then set the Production token in the production Railway environment.
