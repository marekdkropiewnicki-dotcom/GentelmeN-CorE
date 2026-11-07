# Analytics Tracking — Mixpanel

This project uses **Mixpanel** for all product analytics. Mixpanel is the single source of truth for event tracking, user identification and behavioural data. Do not introduce any other analytics tools, SDKs or tracking libraries without explicit instruction from the user.

The full tracking plan, KPIs and verification steps are in [`docs/analytics/tracking-plan.md`](docs/analytics/tracking-plan.md).

---

## Before You Add or Modify Any Tracking

⛔ **Do not write Mixpanel tracking code without reading this file first.**

Wrong assumptions about platform, identity or consent produce broken Mixpanel data that needs manual cleanup or deletion requests.

### Mandatory checklist before writing any Mixpanel code

- [ ] Use the Python server-side SDK through `core/analytics.py` — never call `mixpanel` directly from feature code.
- [ ] This project does not route data through a CDP. Send events with `core.analytics`.
- [ ] Consent is required: GeNCorE serves EU users. Only `track_user_event()` may send events, because it checks the user's stored opt-in first.
- [ ] Check the tracking plan below and in `docs/analytics/tracking-plan.md` before adding events.

---

## Tech Stack

| Detail | Value |
|---|---|
| **Platform** | Python 3 Telegram bot (`pyTelegramBotAPI`, long polling), deployed on Railway |
| **Mixpanel SDK** | `mixpanel` (Python) |
| **SDK version** | `>=5.4` (tested with 5.4.1) |
| **Tracking method** | Server-side, delivered by one background worker thread |
| **CDP (if any)** | None |
| **Consent required** | Yes — opt-in, stored in PostgreSQL (`users.analytics_consent`) |
| **Mixpanel project token location** | Environment variable `MIXPANEL_TOKEN`; region in `MIXPANEL_API_HOST` (default `api-eu.mixpanel.com`) |

---

## Mixpanel Initialization

Mixpanel is initialized in:

**File:** `core/analytics.py` → `init_analytics()`, called once at startup from `core/bot.py`.

```python
# core/bot.py
init_db()
if init_analytics():  # reads MIXPANEL_TOKEN and MIXPANEL_API_HOST
    ...
```

Without `MIXPANEL_TOKEN`, analytics is disabled: no consent prompt is shown and every helper is a no-op.

**Do not:**
- Initialize Mixpanel in multiple places.
- Create separate `Mixpanel` instances per module.
- Import `mixpanel` in feature files — use the helpers in `core.analytics`.

---

## Mixpanel Identity

This is a server-side implementation with no anonymous phase, so there is no `identify()` / `reset()` pair. The equivalents are:

| Action | When to call | Code location |
|---|---|---|
| `record_consent_granted(analytics_id, ...)` — sets the profile (and tracks `sign_up_completed` for new users) | After the user opts in | `core/commands.py` → `handle_analytics_consent` |
| `record_consent_revoked(previous_analytics_id)` — deletes the profile | After the user withdraws consent | `core/commands.py` → `handle_analytics_consent` |

**Rules:**
- The Mixpanel `distinct_id` is `users.analytics_id`, a random UUID created at opt-in. Never use the Telegram user ID, username or email.
- `track_user_event(user_id, ...)` takes the Telegram user ID and looks up consent and `analytics_id` itself.
- Withdrawal clears `analytics_id`. A later opt-in gets a new, unlinked ID — never reuse an old one.

---

## Mixpanel Tracking Plan

These are the Mixpanel events currently tracked in this project. **All new Mixpanel events must follow the same conventions.**

### Naming conventions

- Mixpanel event names: `snake_case`, past-tense verb + noun (e.g., `ai_reply_sent`, `image_generated`).
- Mixpanel property names: `snake_case` (e.g., `sign_up_method`, `input_type`).
- No abbreviations in Mixpanel event or property names — use full words.
- Boolean Mixpanel properties: use the `is_` prefix (e.g., `is_web_context_used`).

### Current Mixpanel events

| Mixpanel Event | Trigger | Key Properties | File |
|---|---|---|---|
| `sign_up_completed` | A new user (first `/start`) opts in to analytics | `sign_up_method`, `language`, `chat_type`, `referral_source` (optional) | `core/commands.py`, `core/analytics.py` |
| `ai_reply_sent` | An AI reply was delivered (Value Moment) | `model`, `language`, `input_type`, `chat_type`, `is_web_context_used`, `history_message_count`, `reply_character_count` | `core/commands.py` → `ai_chat` |

Every event also carries `platform`, `environment` and `app_version` (added by `core.analytics`).

---

## How to Add a New Mixpanel Event

1. **Check the tracking plan above** and in `docs/analytics/tracking-plan.md` — if the Mixpanel event already exists, use it. Do not create duplicate Mixpanel events.
2. **Name the Mixpanel event** using the conventions above: `snake_case`, past tense, descriptive.
3. **Define Mixpanel properties** — only include properties available at the moment the event fires. Do not fetch additional data just for Mixpanel tracking.
4. **Place the Mixpanel tracking call** at the right moment — after the action succeeds (after the reply is sent, after the DB write), not when the command arrives.
5. **Update this file and the tracking plan** — add the new Mixpanel event to both tables.
6. **Add a test** in `tests/test_analytics.py` that checks the event fires only with consent and never contains message content.
7. **Verify in Mixpanel Live View** — confirm the event appears with correct properties before considering it done.

### Mixpanel event template

```python
# Track [description of what happened] in Mixpanel (sent only if the user opted in)
analytics.track_user_event(m.from_user.id, "event_name", {
    "property_name": value,
})
```

---

## What Not to Do

- **Do not introduce other analytics tools.** All tracking goes through Mixpanel via `core.analytics`.
- **Do not track before consent** — never call the Mixpanel client directly; `track_user_event()` enforces the opt-in.
- **Do not track PII or content as Mixpanel properties** — no message text, prompts, usernames, Telegram IDs, emails, phone numbers or IP addresses.
- **Do not fire Mixpanel events inside loops** — each event is a network request.
- **Do not hardcode the Mixpanel project token** — read it from `MIXPANEL_TOKEN`.
- **Do not reuse a previous `analytics_id` after consent is withdrawn.**
- **Do not track admin-only commands** (`/alert`, `/alerty`, `/balance`).
