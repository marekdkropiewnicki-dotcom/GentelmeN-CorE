"""Mixpanel product analytics for GeNCorE.

Server-side, consent-gated (opt-in) tracking:

* Nothing is sent unless ``MIXPANEL_TOKEN`` is set.
* Events are sent only for users who opted in (consent is stored in
  PostgreSQL, see ``core.database``). Users are identified by a random
  ``analytics_id`` (UUID) — never by their Telegram ID, username or
  message content.
* Delivery happens on one background worker thread, so a slow or failing
  Mixpanel API never delays a bot reply and never raises into a handler.

See ``docs/analytics/tracking-plan.md`` and ``AGENTS.md`` before adding events.
"""
import logging
import os
import queue
import threading
import time
from datetime import datetime, timezone

from mixpanel import Consumer, Mixpanel

from core.database import get_analytics_consent

logger = logging.getLogger(__name__)

DEFAULT_API_HOST = "api-eu.mixpanel.com"
PLATFORM = "telegram"
MAX_QUEUE_SIZE = 1000
REQUEST_TIMEOUT_SECONDS = 5
RETRY_LIMIT = 2

_lock = threading.Lock()
_client = None
_queue = None
_worker = None
_worker_queue = None
_api_host = DEFAULT_API_HOST
_global_properties = {}


def _build_global_properties():
    """Properties attached to every event (server-side 'super properties')."""
    commit = os.environ.get("RAILWAY_GIT_COMMIT_SHA", "")
    return {
        "platform": PLATFORM,
        "environment": os.environ.get("RAILWAY_ENVIRONMENT_NAME") or "local",
        "app_version": commit[:7] if commit else "local",
    }


def init_analytics(token=None, api_host=None, client=None, start_worker=True):
    """Configure Mixpanel once at startup. Returns True when analytics is enabled.

    ``token`` and ``api_host`` default to ``MIXPANEL_TOKEN`` and
    ``MIXPANEL_API_HOST`` (EU residency by default). ``client`` and
    ``start_worker`` exist for tests: pass a fake client and
    ``start_worker=False`` to deliver synchronously.
    """
    global _client, _queue, _worker, _worker_queue, _api_host, _global_properties
    with _lock:
        if token is None:
            token = os.environ.get("MIXPANEL_TOKEN", "")
        token = token.strip()
        host = (api_host or os.environ.get("MIXPANEL_API_HOST") or DEFAULT_API_HOST).strip()
        _global_properties = _build_global_properties()

        if client is None:
            if not token:
                _client = None
                _queue = None
                return False
            client = Mixpanel(
                token,
                consumer=Consumer(
                    api_host=host,
                    request_timeout=REQUEST_TIMEOUT_SECONDS,
                    retry_limit=RETRY_LIMIT,
                ),
            )

        _client = client
        _api_host = host
        if start_worker:
            if _worker is None or not _worker.is_alive():
                _worker_queue = queue.Queue(maxsize=MAX_QUEUE_SIZE)
                _worker = threading.Thread(
                    target=_worker_loop,
                    args=(_worker_queue,),
                    name="mixpanel-worker",
                    daemon=True,
                )
                _worker.start()
            _queue = _worker_queue
        else:
            _queue = None
        return True


def is_enabled():
    return _client is not None


def api_host():
    return _api_host


def _worker_loop(work_queue):
    while True:
        item = work_queue.get()
        try:
            _deliver(item)
        finally:
            work_queue.task_done()


def _deliver(item):
    client, method, args, kwargs = item
    try:
        getattr(client, method)(*args, **kwargs)
    except Exception as e:
        logger.warning("Mixpanel %s failed: %s", method, e)


def _dispatch(method, *args, **kwargs):
    client = _client
    if client is None:
        return False
    item = (client, method, args, kwargs)
    if _queue is None:
        _deliver(item)
        return True
    try:
        _queue.put_nowait(item)
    except queue.Full:
        logger.warning("Mixpanel queue full, dropping %s", method)
        return False
    return True


def flush(timeout=5.0):
    """Wait until queued messages are delivered (used in tests and shutdown)."""
    work_queue = _queue
    if work_queue is None:
        return True
    deadline = time.monotonic() + timeout
    while work_queue.unfinished_tasks:
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.01)
    return True


def _with_global_properties(properties):
    merged = dict(_global_properties)
    merged.update(properties or {})
    return merged


def track_user_event(user_id, event_name, properties=None):
    """Track ``event_name`` for a Telegram user, only if they opted in.

    Returns True when the event was handed to Mixpanel. Never raises.
    """
    try:
        if not is_enabled():
            return False
        consent, analytics_id = get_analytics_consent(user_id)
        if consent is not True or not analytics_id:
            return False
        return _dispatch(
            "track", analytics_id, event_name, _with_global_properties(properties)
        )
    except Exception as e:
        logger.warning("Mixpanel tracking skipped for %s: %s", event_name, e)
        return False


def record_consent_granted(
    analytics_id, *, language, model, chat_type, is_signup=False, referral_source=None
):
    """Create the user's profile after opt-in; track sign-up for new users.

    Order follows Mixpanel's identity guidance: the user row exists, then
    the profile is set, then ``sign_up_completed`` is tracked.
    """
    try:
        if not is_enabled() or not analytics_id:
            return False
        consent_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
        _dispatch(
            "people_set",
            analytics_id,
            {
                "language": language,
                "ai_model": model,
                "analytics_consent_at": consent_time,
            },
            meta={"$ip": 0},
        )
        if is_signup:
            properties = {
                "sign_up_method": "telegram_start",
                "language": language,
                "chat_type": chat_type,
            }
            if referral_source:
                properties["referral_source"] = referral_source
            _dispatch(
                "track",
                analytics_id,
                "sign_up_completed",
                _with_global_properties(properties),
            )
        return True
    except Exception as e:
        logger.warning("Mixpanel consent sync failed: %s", e)
        return False


def record_consent_revoked(previous_analytics_id):
    """Delete the user's Mixpanel profile after they withdraw consent."""
    try:
        if not is_enabled() or not previous_analytics_id:
            return False
        return _dispatch("people_delete", previous_analytics_id)
    except Exception as e:
        logger.warning("Mixpanel profile deletion failed: %s", e)
        return False
