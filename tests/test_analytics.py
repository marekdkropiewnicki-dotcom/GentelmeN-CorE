"""
Tests for consent-gated Mixpanel analytics (core/analytics.py) and its wiring
into the database layer and bot commands.
Run with: python -m pytest tests/ -v
"""
import os
import unittest
import uuid
from unittest.mock import MagicMock, patch

from mixpanel import MixpanelException

import core.analytics as analytics
import core.commands as cmds
import core.database as db


def _reset_state():
    db.DB_URL = None
    db.user_prefs.clear()
    db.user_models.clear()
    db.user_analytics.clear()
    cmds._pending_referrals.clear()
    cmds.user_history.clear()


def _enable_sync(client=None):
    """Enable analytics with a fake client and synchronous delivery."""
    client = client or MagicMock()
    analytics.init_analytics(token="test-token", client=client, start_worker=False)
    return client


def _disable():
    analytics.init_analytics(token="")


def _make_message(user_id=1, username="testuser", chat_id=100, text="", chat_type="private"):
    m = MagicMock()
    m.from_user.id = user_id
    m.from_user.username = username
    m.chat.id = chat_id
    m.chat.type = chat_type
    m.message_thread_id = None
    m.text = text
    del m.gencore_input_type  # plain text messages carry no input-type marker
    return m


def _make_call(data, from_user_id=1, username="testuser", chat_type="private"):
    call = MagicMock()
    call.id = "cb-1"
    call.data = data
    call.from_user.id = from_user_id
    call.from_user.username = username
    call.message.chat.id = 100
    call.message.chat.type = chat_type
    call.message.message_id = 555
    return call


def _tracked(client, event_name):
    return [c for c in client.track.call_args_list if c.args[1] == event_name]


# ---------------------------------------------------------------------------
# core.analytics — configuration and delivery
# ---------------------------------------------------------------------------

class TestAnalyticsConfig(unittest.TestCase):
    def tearDown(self):
        _disable()

    def test_disabled_without_token(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(analytics.init_analytics())
        self.assertFalse(analytics.is_enabled())

    def test_eu_host_by_default(self):
        with patch.dict(os.environ, {"MIXPANEL_TOKEN": "tok"}, clear=True):
            self.assertTrue(analytics.init_analytics(start_worker=False))
        self.assertEqual(analytics.api_host(), "api-eu.mixpanel.com")
        endpoints = analytics._client._consumer._endpoints
        self.assertEqual(endpoints["events"], "https://api-eu.mixpanel.com/track")
        self.assertEqual(endpoints["people"], "https://api-eu.mixpanel.com/engage")

    def test_api_host_override_for_us_projects(self):
        env = {"MIXPANEL_TOKEN": "tok", "MIXPANEL_API_HOST": "api.mixpanel.com"}
        with patch.dict(os.environ, env, clear=True):
            analytics.init_analytics(start_worker=False)
        self.assertEqual(
            analytics._client._consumer._endpoints["events"], "https://api.mixpanel.com/track"
        )

    def test_global_properties_from_railway_env(self):
        env = {"RAILWAY_GIT_COMMIT_SHA": "abcdef1234567", "RAILWAY_ENVIRONMENT_NAME": "production"}
        with patch.dict(os.environ, env, clear=True):
            props = analytics._build_global_properties()
        self.assertEqual(
            props, {"platform": "telegram", "environment": "production", "app_version": "abcdef1"}
        )

    def test_global_properties_fallback_locally(self):
        with patch.dict(os.environ, {}, clear=True):
            props = analytics._build_global_properties()
        self.assertEqual(props["environment"], "local")
        self.assertEqual(props["app_version"], "local")


class TestAnalyticsDelivery(unittest.TestCase):
    def setUp(self):
        _reset_state()

    def tearDown(self):
        _disable()
        _reset_state()

    def test_background_worker_delivers(self):
        client = MagicMock()
        analytics.init_analytics(token="tok", client=client, start_worker=True)
        db.user_analytics[7] = (True, "aid-7")
        self.assertTrue(analytics.track_user_event(7, "ai_reply_sent", {"model": "m"}))
        self.assertTrue(analytics.flush(timeout=2))
        client.track.assert_called_once()

    def test_send_errors_never_raise(self):
        client = MagicMock()
        client.track.side_effect = MixpanelException("network down")
        _enable_sync(client)
        db.user_analytics[7] = (True, "aid-7")
        with self.assertLogs("core.analytics", level="WARNING"):
            analytics.track_user_event(7, "ai_reply_sent")

    def test_consent_lookup_errors_never_raise(self):
        _enable_sync()
        with patch("core.analytics.get_analytics_consent", side_effect=RuntimeError("boom")):
            with self.assertLogs("core.analytics", level="WARNING"):
                self.assertFalse(analytics.track_user_event(7, "ai_reply_sent"))

    def test_full_queue_drops_instead_of_blocking(self):
        _enable_sync()
        full_queue = MagicMock()
        full_queue.put_nowait.side_effect = analytics.queue.Full
        with patch.object(analytics, "_queue", full_queue):
            with self.assertLogs("core.analytics", level="WARNING"):
                self.assertFalse(analytics._dispatch("track", "aid", "event", {}))


class TestTrackUserEvent(unittest.TestCase):
    def setUp(self):
        _reset_state()
        self.client = _enable_sync()

    def tearDown(self):
        _disable()
        _reset_state()

    def test_never_asked_is_not_tracked(self):
        self.assertFalse(analytics.track_user_event(1, "ai_reply_sent"))
        self.client.track.assert_not_called()

    def test_declined_is_not_tracked(self):
        db.user_analytics[1] = (False, None)
        self.assertFalse(analytics.track_user_event(1, "ai_reply_sent"))
        self.client.track.assert_not_called()

    def test_opted_in_uses_analytics_id_and_global_properties(self):
        db.user_analytics[123456789] = (True, "aid-1")
        self.assertTrue(analytics.track_user_event(123456789, "ai_reply_sent", {"model": "m"}))
        distinct_id, event, props = self.client.track.call_args.args
        self.assertEqual(distinct_id, "aid-1")
        self.assertEqual(event, "ai_reply_sent")
        self.assertEqual(props["model"], "m")
        self.assertEqual(props["platform"], "telegram")
        self.assertNotIn("123456789", str(self.client.track.call_args))

    def test_disabled_analytics_skips_consent_lookup(self):
        _disable()
        with patch("core.analytics.get_analytics_consent") as lookup:
            self.assertFalse(analytics.track_user_event(1, "ai_reply_sent"))
        lookup.assert_not_called()


class TestConsentSync(unittest.TestCase):
    def setUp(self):
        self.client = _enable_sync()

    def tearDown(self):
        _disable()

    def test_granted_sets_profile_without_ip_geolocation(self):
        analytics.record_consent_granted("aid-1", language="pl", model="m", chat_type="private")
        args, kwargs = self.client.people_set.call_args
        self.assertEqual(args[0], "aid-1")
        self.assertEqual(args[1]["language"], "pl")
        self.assertEqual(args[1]["ai_model"], "m")
        self.assertEqual(kwargs["meta"], {"$ip": 0})
        self.client.track.assert_not_called()

    def test_signup_tracked_after_profile(self):
        analytics.record_consent_granted(
            "aid-1", language="en", model="m", chat_type="private",
            is_signup=True, referral_source="promo_1",
        )
        method_order = [c[0] for c in self.client.method_calls]
        self.assertEqual(method_order, ["people_set", "track"])
        _, event, props = self.client.track.call_args.args
        self.assertEqual(event, "sign_up_completed")
        self.assertEqual(props["sign_up_method"], "telegram_start")
        self.assertEqual(props["referral_source"], "promo_1")

    def test_signup_omits_missing_referral(self):
        analytics.record_consent_granted(
            "aid-1", language="en", model="m", chat_type="private", is_signup=True,
        )
        self.assertNotIn("referral_source", self.client.track.call_args.args[2])

    def test_revoked_deletes_profile(self):
        analytics.record_consent_revoked("aid-1")
        self.client.people_delete.assert_called_once_with("aid-1")

    def test_revoked_without_previous_id_is_noop(self):
        analytics.record_consent_revoked(None)
        self.client.people_delete.assert_not_called()


# ---------------------------------------------------------------------------
# core.database — consent storage
# ---------------------------------------------------------------------------

def _mock_db(mock_connect, fetchone=None):
    conn = MagicMock()
    mock_connect.return_value.__enter__ = lambda s: conn
    mock_connect.return_value.__exit__ = MagicMock(return_value=False)
    cur = MagicMock()
    cur.fetchone.return_value = fetchone
    conn.cursor.return_value.__enter__ = lambda s: cur
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return cur


class TestConsentStorage(unittest.TestCase):
    def setUp(self):
        _reset_state()

    def tearDown(self):
        _reset_state()

    def test_grant_creates_uuid_and_keeps_it(self):
        analytics_id, previous = db.set_analytics_consent(1, "u", True)
        uuid.UUID(analytics_id)  # valid UUID
        self.assertIsNone(previous)
        again, previous_again = db.set_analytics_consent(1, "u", True)
        self.assertEqual(again, analytics_id)
        self.assertEqual(previous_again, analytics_id)

    def test_revoke_clears_id_and_reports_previous(self):
        analytics_id, _ = db.set_analytics_consent(1, "u", True)
        cleared, previous = db.set_analytics_consent(1, "u", False)
        self.assertIsNone(cleared)
        self.assertEqual(previous, analytics_id)
        self.assertEqual(db.get_analytics_consent(1), (False, None))

    def test_regrant_after_revoke_starts_new_identity(self):
        first, _ = db.set_analytics_consent(1, "u", True)
        db.set_analytics_consent(1, "u", False)
        second, _ = db.set_analytics_consent(1, "u", True)
        self.assertNotEqual(first, second)

    @patch("core.database.psycopg2.connect")
    def test_consent_read_from_db_and_cached(self, mock_connect):
        db.DB_URL = "postgresql://mock"
        _mock_db(mock_connect, fetchone=(True, "11111111-1111-1111-1111-111111111111"))
        self.assertEqual(
            db.get_analytics_consent(5), (True, "11111111-1111-1111-1111-111111111111")
        )
        db.get_analytics_consent(5)
        self.assertEqual(mock_connect.call_count, 1)

    @patch("core.database.psycopg2.connect", side_effect=Exception("db down"))
    def test_consent_db_error_is_not_cached(self, _):
        db.DB_URL = "postgresql://mock"
        with self.assertLogs("root", level="WARNING"):
            self.assertEqual(db.get_analytics_consent(5), (None, None))
        self.assertNotIn(5, db.user_analytics)

    @patch("core.database.psycopg2.connect")
    def test_consent_written_with_parameters(self, mock_connect):
        db.DB_URL = "postgresql://mock"
        db.user_analytics[5] = (None, None)
        cur = _mock_db(mock_connect)
        analytics_id, _ = db.set_analytics_consent(5, "u5", True)
        sql, params = cur.execute.call_args.args
        self.assertIn("ON CONFLICT (user_id)", sql)
        self.assertEqual(params, (5, "u5", True, analytics_id))

    @patch("core.database.psycopg2.connect", side_effect=Exception("db down"))
    def test_user_exists_assumes_existing_on_error(self, _):
        db.DB_URL = "postgresql://mock"
        with self.assertLogs("root", level="WARNING"):
            self.assertTrue(db.user_exists(5))

    def test_user_exists_without_db_uses_cache(self):
        self.assertFalse(db.user_exists(5))
        db.user_prefs[5] = "EN"
        self.assertTrue(db.user_exists(5))

    @patch("core.database.psycopg2.connect")
    def test_init_db_adds_consent_columns(self, mock_connect):
        db.DB_URL = "postgresql://mock"
        cur = _mock_db(mock_connect)
        db.init_db()
        executed = " ".join(str(c.args[0]) for c in cur.execute.call_args_list)
        self.assertIn("ADD COLUMN IF NOT EXISTS analytics_consent BOOLEAN", executed)
        self.assertIn("ADD COLUMN IF NOT EXISTS analytics_id UUID", executed)


# ---------------------------------------------------------------------------
# core.commands — consent UI and event wiring
# ---------------------------------------------------------------------------

class CommandsTestCase(unittest.TestCase):
    def setUp(self):
        _reset_state()
        self.bot = MagicMock()
        self.groq = MagicMock()
        cmds.register_handlers(self.bot, self.groq, MagicMock())
        self.client = _enable_sync()

    def tearDown(self):
        _disable()
        _reset_state()

    def sent_texts(self):
        return [str(c.args[1]) for c in self.bot.send_message.call_args_list]


class TestWelcomeConsentPrompt(CommandsTestCase):
    def test_new_user_gets_prompt_with_signup_origin(self):
        cmds.welcome(_make_message(user_id=1, text="/start promo_1"))
        prompt = self.bot.send_message.call_args_list[-1]
        self.assertIn("Mixpanel", prompt.args[1])
        markup = prompt.kwargs["reply_markup"]
        data = [b.callback_data for b in markup.keyboard[0]]
        self.assertEqual(data, ["analytics:yes:1:signup", "analytics:no:1:signup"])
        self.assertEqual(cmds._pending_referrals[1], "promo_1")

    def test_existing_user_without_decision_gets_start_origin(self):
        db.user_prefs[1] = "EN"  # row already exists
        cmds.welcome(_make_message(user_id=1, text="/start"))
        markup = self.bot.send_message.call_args_list[-1].kwargs["reply_markup"]
        self.assertTrue(markup.keyboard[0][0].callback_data.endswith(":start"))
        self.assertNotIn(1, cmds._pending_referrals)

    def test_decided_user_is_not_asked_again(self):
        db.user_analytics[1] = (False, None)
        cmds.welcome(_make_message(user_id=1, text="/start"))
        self.assertEqual(len(self.bot.send_message.call_args_list), 1)

    def test_no_prompt_when_analytics_disabled(self):
        _disable()
        cmds.welcome(_make_message(user_id=1, text="/start"))
        self.assertEqual(len(self.bot.send_message.call_args_list), 1)
        self.assertNotIn("reply_markup", self.bot.send_message.call_args.kwargs)

    def test_invalid_referral_payload_ignored(self):
        cmds.welcome(_make_message(user_id=1, text="/start bad payload!"))
        self.assertNotIn(1, cmds._pending_referrals)


class TestConsentCallback(CommandsTestCase):
    def test_signup_yes_sets_profile_then_tracks_signup(self):
        cmds._pending_referrals[1] = "promo_1"
        cmds.handle_analytics_consent(_make_call("analytics:yes:1:signup"))
        consent, analytics_id = db.get_analytics_consent(1)
        self.assertTrue(consent)
        self.client.people_set.assert_called_once()
        signup = _tracked(self.client, "sign_up_completed")
        self.assertEqual(len(signup), 1)
        self.assertEqual(signup[0].args[0], analytics_id)
        self.assertEqual(signup[0].args[2]["referral_source"], "promo_1")
        self.bot.edit_message_text.assert_called_once()

    def test_repeated_yes_does_not_duplicate_signup(self):
        cmds.handle_analytics_consent(_make_call("analytics:yes:1:signup"))
        cmds.handle_analytics_consent(_make_call("analytics:yes:1:signup"))
        self.assertEqual(len(_tracked(self.client, "sign_up_completed")), 1)

    def test_settings_opt_in_is_not_a_signup(self):
        cmds.handle_analytics_consent(_make_call("analytics:yes:1:settings"))
        self.client.people_set.assert_called_once()
        self.assertEqual(_tracked(self.client, "sign_up_completed"), [])

    def test_no_stores_decline_and_tracks_nothing(self):
        cmds._pending_referrals[1] = "promo_1"
        cmds.handle_analytics_consent(_make_call("analytics:no:1:signup"))
        self.assertEqual(db.get_analytics_consent(1), (False, None))
        self.client.track.assert_not_called()
        self.client.people_set.assert_not_called()
        self.assertNotIn(1, cmds._pending_referrals)

    def test_withdrawal_deletes_previous_profile(self):
        cmds.handle_analytics_consent(_make_call("analytics:yes:1:settings"))
        _, analytics_id = db.get_analytics_consent(1)
        cmds.handle_analytics_consent(_make_call("analytics:no:1:settings"))
        self.client.people_delete.assert_called_once_with(analytics_id)

    def test_other_user_cannot_answer(self):
        cmds.handle_analytics_consent(_make_call("analytics:yes:1:signup", from_user_id=2))
        self.assertEqual(db.get_analytics_consent(1), (None, None))
        self.assertEqual(db.get_analytics_consent(2), (None, None))
        self.bot.answer_callback_query.assert_called_once_with(
            "cb-1", "To pytanie jest do innej osoby."
        )

    def test_malformed_callback_is_ignored(self):
        cmds.handle_analytics_consent(_make_call("analytics:yes"))
        self.client.track.assert_not_called()
        self.bot.answer_callback_query.assert_called_once()

    def test_message_edit_failure_is_logged(self):
        self.bot.edit_message_text.side_effect = Exception("message too old")
        with self.assertLogs("root", level="WARNING"):
            cmds.handle_analytics_consent(_make_call("analytics:yes:1:settings"))


class TestAnalyticsSettingsCommand(CommandsTestCase):
    def test_shows_status_and_keyboard(self):
        db.user_analytics[1] = (True, "aid-1")
        cmds.analytics_settings(_make_message(user_id=1, text="/analityka"))
        call = self.bot.send_message.call_args
        self.assertIn("włączone", call.args[1])
        self.assertTrue(
            call.kwargs["reply_markup"].keyboard[0][0].callback_data.endswith(":settings")
        )

    def test_reports_disabled_server(self):
        _disable()
        cmds.analytics_settings(_make_message(user_id=1, text="/analityka"))
        self.assertIn("nie są włączone", self.bot.send_message.call_args.args[1])

    def test_command_registered_before_catch_all(self):
        registered = [
            c.kwargs.get("commands") or c.kwargs.get("func")
            for c in self.bot.message_handler.call_args_list
        ]
        self.assertIn(["analityka", "analytics"], registered)
        self.assertLess(
            registered.index(["analityka", "analytics"]), len(registered) - 1
        )
        self.bot.callback_query_handler.assert_called_once()


class TestAiReplyTracking(CommandsTestCase):
    def _reply(self, text="Hello there"):
        completion = MagicMock()
        completion.choices[0].message.content = text
        self.groq.chat.completions.create.return_value = completion

    @patch("core.commands.get_user_data", return_value=("PL", "llama-3.3-70b-versatile"))
    def test_opted_in_user_tracks_value_moment(self, _):
        db.user_analytics[1] = (True, "aid-1")
        self._reply("Cześć!")
        cmds.ai_chat(_make_message(user_id=1, text="tajny plan na jutro"))
        events = _tracked(self.client, "ai_reply_sent")
        self.assertEqual(len(events), 1)
        distinct_id, _, props = events[0].args
        self.assertEqual(distinct_id, "aid-1")
        self.assertEqual(props["model"], "llama-3.3-70b-versatile")
        self.assertEqual(props["language"], "pl")
        self.assertEqual(props["input_type"], "text")
        self.assertEqual(props["chat_type"], "private")
        self.assertFalse(props["is_web_context_used"])
        self.assertEqual(props["history_message_count"], 2)
        self.assertEqual(props["reply_character_count"], len("Cześć!"))
        self.assertNotIn("tajny plan", str(events[0]))  # never message content
        self.assertNotIn("Cześć", str(events[0]))

    @patch("core.commands.get_user_data", return_value=("EN", "m"))
    def test_not_tracked_without_consent(self, _):
        self._reply()
        cmds.ai_chat(_make_message(user_id=1, text="hi"))
        self.client.track.assert_not_called()

    @patch("core.commands.search_brave", return_value="BTC news")
    @patch("core.commands.get_user_data", return_value=("EN", "m"))
    def test_web_context_flag(self, _, __):
        db.user_analytics[1] = (True, "aid-1")
        self._reply()
        cmds.ai_chat(_make_message(user_id=1, text="bitcoin price?"))
        self.assertTrue(_tracked(self.client, "ai_reply_sent")[0].args[2]["is_web_context_used"])

    @patch("core.commands.get_user_data", return_value=("EN", "m"))
    def test_ai_failure_tracks_nothing(self, _):
        db.user_analytics[1] = (True, "aid-1")
        self.groq.chat.completions.create.side_effect = Exception("groq down")
        cmds.ai_chat(_make_message(user_id=1, text="hi"))
        self.client.track.assert_not_called()

    @patch("core.commands.get_user_data", return_value=("EN", "m"))
    def test_voice_input_type(self, _):
        db.user_analytics[1] = (True, "aid-1")
        self._reply()
        self.bot.get_file.return_value = MagicMock()
        self.bot.download_file.return_value = b"ogg"
        transcript = MagicMock()
        transcript.text = "what is new"
        self.groq.audio.transcriptions.create.return_value = transcript
        m = _make_message(user_id=1)
        m.voice.file_id = "fid"
        cmds.handle_voice(m)
        self.assertEqual(_tracked(self.client, "ai_reply_sent")[0].args[2]["input_type"], "voice")


class TestReplyHelperMarkup(unittest.TestCase):
    def test_reply_markup_forwarded_only_when_given(self):
        from core.helpers import inteligentna_odpowiedz
        bot = MagicMock()
        markup = object()
        inteligentna_odpowiedz(bot, 1, "hi", 42, reply_markup=markup)
        self.assertIs(bot.send_message.call_args.kwargs["reply_markup"], markup)
        inteligentna_odpowiedz(bot, 1, "hi", None)
        self.assertNotIn("reply_markup", bot.send_message.call_args.kwargs)


if __name__ == "__main__":
    unittest.main()
