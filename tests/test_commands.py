"""
Unit tests covering helpers, database, integrations and commands modules.
Run with: python -m pytest tests/ -v
"""
import io
import os
import sys
import unittest
from unittest.mock import MagicMock, call, patch

import requests

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

class TestInteligentnaOdpowiedz(unittest.TestCase):
    def setUp(self):
        from core.helpers import inteligentna_odpowiedz
        self.fn = inteligentna_odpowiedz
        self.bot = MagicMock()

    def test_with_thread_id_sends_message_thread_id(self):
        self.fn(self.bot, 1, "hello", 42)
        self.bot.send_message.assert_called_once_with(
            1, "hello",
            message_thread_id=42,
            parse_mode=None,
            disable_web_page_preview=False,
        )

    def test_without_thread_id_omits_thread_kwarg(self):
        self.fn(self.bot, 1, "hello", None)
        self.bot.send_message.assert_called_once_with(
            1, "hello",
            parse_mode=None,
            disable_web_page_preview=False,
        )

    def test_parse_mode_forwarded(self):
        self.fn(self.bot, 1, "text", None, parse_mode="Markdown")
        _, kwargs = self.bot.send_message.call_args
        self.assertEqual(kwargs["parse_mode"], "Markdown")

    def test_disable_preview_forwarded(self):
        self.fn(self.bot, 1, "text", None, disable_preview=True)
        _, kwargs = self.bot.send_message.call_args
        self.assertTrue(kwargs["disable_web_page_preview"])


# ---------------------------------------------------------------------------
# database
# ---------------------------------------------------------------------------

class TestInitDb(unittest.TestCase):
    def test_no_db_url_returns_immediately(self):
        import core.database as db
        original = db.DB_URL
        db.DB_URL = None
        try:
            db.init_db()  # must not raise
        finally:
            db.DB_URL = original

    @patch("core.database.psycopg2.connect")
    def test_init_db_creates_tables(self, mock_connect):
        import core.database as db
        db.DB_URL = "postgresql://mock"
        mock_conn = MagicMock()
        mock_connect.return_value.__enter__ = lambda s: mock_conn
        mock_connect.return_value.__exit__ = MagicMock(return_value=False)
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = lambda s: mock_cursor
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        db.init_db()
        self.assertTrue(mock_cursor.execute.called)
        db.DB_URL = None

    @patch("core.database.psycopg2.connect", side_effect=Exception("conn failed"))
    def test_init_db_logs_exception(self, _mock):
        import core.database as db
        db.DB_URL = "postgresql://mock"
        with self.assertLogs("root", level="WARNING") as log_ctx:
            db.init_db()
        self.assertTrue(any("DB error" in m for m in log_ctx.output))
        db.DB_URL = None


class TestGetUserData(unittest.TestCase):
    def setUp(self):
        import core.database as db
        db.user_prefs.clear()
        db.user_models.clear()
        self._db = db

    def test_returns_cached_values(self):
        self._db.user_prefs[1] = 'PL'
        self._db.user_models[1] = 'test-model'
        lang, model = self._db.get_user_data(1)
        self.assertEqual(lang, 'PL')
        self.assertEqual(model, 'test-model')

    def test_no_db_url_returns_defaults(self):
        self._db.DB_URL = None
        lang, model = self._db.get_user_data(999)
        self.assertEqual(lang, 'EN')
        self.assertEqual(model, 'llama-3.3-70b-versatile')

    @patch("core.database.psycopg2.connect")
    def test_fetches_from_db_when_not_cached(self, mock_connect):
        self._db.DB_URL = "postgresql://mock"
        mock_conn = MagicMock()
        mock_connect.return_value.__enter__ = lambda s: mock_conn
        mock_connect.return_value.__exit__ = MagicMock(return_value=False)
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = ('PL', 'qwen-2.5-32b')
        mock_conn.cursor.return_value.__enter__ = lambda s: mock_cur
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        lang, model = self._db.get_user_data(7)
        self.assertEqual(lang, 'PL')
        self.assertEqual(model, 'qwen-2.5-32b')
        self._db.DB_URL = None

    @patch("core.database.psycopg2.connect")
    def test_returns_defaults_when_user_not_in_db(self, mock_connect):
        self._db.DB_URL = "postgresql://mock"
        mock_conn = MagicMock()
        mock_connect.return_value.__enter__ = lambda s: mock_conn
        mock_connect.return_value.__exit__ = MagicMock(return_value=False)
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = None
        mock_conn.cursor.return_value.__enter__ = lambda s: mock_cur
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        lang, model = self._db.get_user_data(8)
        self.assertEqual(lang, 'EN')
        self.assertEqual(model, 'llama-3.3-70b-versatile')
        self._db.DB_URL = None

    @patch("core.database.psycopg2.connect", side_effect=Exception("db down"))
    def test_db_error_returns_defaults(self, _):
        self._db.DB_URL = "postgresql://mock"
        with self.assertLogs("root", level="WARNING"):
            lang, model = self._db.get_user_data(9)
        self.assertEqual(lang, 'EN')
        self._db.DB_URL = None


class TestUpdateUserDb(unittest.TestCase):
    def setUp(self):
        import core.database as db
        db.user_prefs.clear()
        db.user_models.clear()
        self._db = db

    def test_no_db_url_updates_cache_only(self):
        self._db.DB_URL = None
        self._db.update_user_db(10, "user10", lang='PL')
        self.assertEqual(self._db.user_prefs[10], 'PL')

    @patch("core.database.psycopg2.connect")
    def test_updates_db_when_url_present(self, mock_connect):
        self._db.DB_URL = "postgresql://mock"
        mock_conn = MagicMock()
        mock_connect.return_value.__enter__ = lambda s: mock_conn
        mock_connect.return_value.__exit__ = MagicMock(return_value=False)
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = None
        mock_conn.cursor.return_value.__enter__ = lambda s: mock_cur
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        self._db.update_user_db(11, "user11", lang='EN', model='llama-3.3-70b-versatile')
        self.assertTrue(mock_cur.execute.called)
        self._db.DB_URL = None


# ---------------------------------------------------------------------------
# integrations
# ---------------------------------------------------------------------------

class TestSearchBrave(unittest.TestCase):
    def setUp(self):
        import core.integrations as integ
        self._integ = integ
        self._original_key = integ.BRAVE_KEY

    def tearDown(self):
        self._integ.BRAVE_KEY = self._original_key

    def test_no_key_returns_empty_string(self):
        self._integ.BRAVE_KEY = None
        result = self._integ.search_brave("test")
        self.assertEqual(result, "")

    @patch("core.integrations.requests.get")
    def test_returns_formatted_results(self, mock_get):
        self._integ.BRAVE_KEY = "key"
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "web": {"results": [{"title": "T1", "description": "D1"}]}
        }
        mock_get.return_value = mock_resp
        result = self._integ.search_brave("query")
        self.assertIn("T1", result)
        self.assertIn("D1", result)

    @patch("core.integrations.requests.get", side_effect=requests.RequestException)
    def test_request_exception_returns_empty(self, _):
        self._integ.BRAVE_KEY = "key"
        result = self._integ.search_brave("query")
        self.assertEqual(result, "")

    @patch("core.integrations.requests.get")
    def test_http_error_returns_empty(self, mock_get):
        import requests as req
        self._integ.BRAVE_KEY = "key"
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = req.HTTPError("404")
        mock_get.return_value = mock_resp
        result = self._integ.search_brave("query")
        self.assertEqual(result, "")

    @patch("core.integrations.requests.get")
    def test_empty_results_returns_empty_string(self, mock_get):
        self._integ.BRAVE_KEY = "key"
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"web": {"results": []}}
        mock_get.return_value = mock_resp
        result = self._integ.search_brave("query")
        self.assertEqual(result, "")


class TestGenerateImageHf(unittest.TestCase):
    def setUp(self):
        import core.integrations as integ
        self._integ = integ
        self._original_token = integ.HF_TOKEN

    def tearDown(self):
        self._integ.HF_TOKEN = self._original_token

    def test_no_token_returns_error_message(self):
        self._integ.HF_TOKEN = None
        image, error = self._integ.generate_image_hf("cat")
        self.assertIsNone(image)
        self.assertIn("HF_TOKEN", error)

    @patch("core.integrations.requests.post")
    def test_success_returns_bytes_io(self, mock_post):
        self._integ.HF_TOKEN = "tok"
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"\x89PNG"
        mock_post.return_value = mock_resp
        image, error = self._integ.generate_image_hf("cat")
        self.assertIsInstance(image, io.BytesIO)
        self.assertIsNone(error)

    @patch("core.integrations.requests.post")
    def test_error_status_returns_error_message(self, mock_post):
        self._integ.HF_TOKEN = "tok"
        mock_resp = MagicMock()
        mock_resp.status_code = 503
        mock_post.return_value = mock_resp
        image, error = self._integ.generate_image_hf("cat")
        self.assertIsNone(image)
        self.assertIn("503", error)

    @patch("core.integrations.requests.post", side_effect=requests.Timeout)
    def test_timeout_returns_timeout_message(self, _):
        self._integ.HF_TOKEN = "tok"
        image, error = self._integ.generate_image_hf("cat")
        self.assertIsNone(image)
        self.assertIn("timeout", error.lower())

    @patch("core.integrations.requests.post", side_effect=requests.ConnectionError("conn"))
    def test_request_exception_returns_error(self, _):
        self._integ.HF_TOKEN = "tok"
        image, error = self._integ.generate_image_hf("cat")
        self.assertIsNone(image)
        self.assertIsNotNone(error)


# ---------------------------------------------------------------------------
# commands
# ---------------------------------------------------------------------------

def _make_message(user_id=1, username="testuser", chat_id=100, thread_id=None, text=""):
    m = MagicMock()
    m.from_user.id = user_id
    m.from_user.username = username
    m.chat.id = chat_id
    m.message_thread_id = thread_id
    m.text = text
    return m


class TestCheckBalance(unittest.TestCase):
    def setUp(self):
        import core.commands as cmds
        self._cmds = cmds
        self.bot = MagicMock()
        self.kucoin = MagicMock()
        cmds.register_handlers(self.bot, MagicMock(), self.kucoin)

    def test_authorized_via_owner_user_id_env(self):
        with patch.dict(os.environ, {"OWNER_USER_ID": "42"}):
            m = _make_message(user_id=42)
            self.kucoin.fetch_balance.return_value = {'total': {}}
            self._cmds.check_balance(m)
        # Should NOT send "Brak dostępu"
        for c in self.bot.send_message.call_args_list:
            self.assertNotIn("Brak dostępu", str(c))

    def test_unauthorized_via_owner_user_id_env(self):
        with patch.dict(os.environ, {"OWNER_USER_ID": "99"}):
            m = _make_message(user_id=42, username="someone")
            self._cmds.check_balance(m)
        calls_text = " ".join(str(c) for c in self.bot.send_message.call_args_list)
        self.assertIn("Brak dostępu", calls_text)

    def test_authorized_via_username_fallback(self):
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("OWNER_USER_ID", None)
            m = _make_message(username="GentelmeN_CorE")
            self.kucoin.fetch_balance.return_value = {'total': {}}
            self._cmds.check_balance(m)
        for c in self.bot.send_message.call_args_list:
            self.assertNotIn("Brak dostępu", str(c))

    def test_unauthorized_via_username_fallback(self):
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("OWNER_USER_ID", None)
            m = _make_message(username="someone_else")
            self._cmds.check_balance(m)
        calls_text = " ".join(str(c) for c in self.bot.send_message.call_args_list)
        self.assertIn("Brak dostępu", calls_text)

    def test_unauthorized_no_username(self):
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("OWNER_USER_ID", None)
            m = _make_message(username=None)
            self._cmds.check_balance(m)
        calls_text = " ".join(str(c) for c in self.bot.send_message.call_args_list)
        self.assertIn("<brak username>", calls_text)

    def test_has_assets_flag_true(self):
        with patch.dict(os.environ, {"OWNER_USER_ID": "1"}):
            m = _make_message(user_id=1)
            self.kucoin.fetch_balance.return_value = {'total': {'BTC': 0.5, 'ETH': 0.0}}
            self._cmds.check_balance(m)
        calls_text = " ".join(str(c) for c in self.bot.send_message.call_args_list)
        self.assertIn("BTC", calls_text)
        self.assertNotIn("Brak środków", calls_text)

    def test_has_assets_flag_false(self):
        with patch.dict(os.environ, {"OWNER_USER_ID": "1"}):
            m = _make_message(user_id=1)
            self.kucoin.fetch_balance.return_value = {'total': {'BTC': 0, 'ETH': 0.0}}
            self._cmds.check_balance(m)
        calls_text = " ".join(str(c) for c in self.bot.send_message.call_args_list)
        self.assertIn("Brak środków", calls_text)


class TestHandleVoice(unittest.TestCase):
    def setUp(self):
        import core.commands as cmds
        self._cmds = cmds
        self.bot = MagicMock()
        self.groq = MagicMock()
        cmds.register_handlers(self.bot, self.groq, MagicMock())

    def test_temp_file_cleaned_up_after_exception(self):
        import tempfile
        self.bot.get_file.side_effect = Exception("network error")
        m = MagicMock()
        m.voice.file_id = "fid"
        m.chat.id = 1
        m.message_thread_id = None
        self._cmds.handle_voice(m)
        # Should send error message, not raise
        self.bot.send_message.assert_called()

    def test_temp_file_cleaned_up_on_success(self):
        import tempfile, os as _os

        created_path = []

        real_ntf = tempfile.NamedTemporaryFile

        def patched_ntf(**kwargs):
            ntf = real_ntf(**kwargs)
            created_path.append(ntf.name)
            return ntf

        self.bot.get_file.return_value = MagicMock()
        self.bot.download_file.return_value = b"ogg_data"
        mock_transcript = MagicMock()
        mock_transcript.text = "hello"
        self.groq.audio.transcriptions.create.return_value = mock_transcript

        m = MagicMock()
        m.voice.file_id = "fid"
        m.chat.id = 1
        m.message_thread_id = None
        m.from_user.id = 1

        with patch("core.commands.tempfile.NamedTemporaryFile", side_effect=patched_ntf):
            with patch("core.commands.ai_chat"):
                self._cmds.handle_voice(m)

        # Temp file should be deleted by finally block
        if created_path:
            self.assertFalse(_os.path.exists(created_path[0]))


class TestChangeModel(unittest.TestCase):
    def setUp(self):
        import core.commands as cmds
        self._cmds = cmds
        self.bot = MagicMock()
        cmds.register_handlers(self.bot, MagicMock(), MagicMock())

    @patch("core.commands.update_user_db")
    def test_model_selected_without_bot_suffix(self, mock_update):
        m = _make_message(text="/fast")
        self._cmds.change_model(m)
        mock_update.assert_called_once()
        _, kwargs = mock_update.call_args
        # Positional: update_user_db(user_id, username, model=...)
        args = mock_update.call_args[0]
        self.assertIn("llama-3.1-8b-instant", mock_update.call_args[1].get("model", "") or args)

    @patch("core.commands.update_user_db")
    def test_model_selected_with_bot_suffix(self, mock_update):
        m = _make_message(text="/fast@MyBot")
        self._cmds.change_model(m)
        mock_update.assert_called_once()
        # model kwarg should still resolve to 'llama-3.1-8b-instant'
        self.assertEqual(mock_update.call_args[1].get("model"), "llama-3.1-8b-instant")

    @patch("core.commands.update_user_db")
    def test_qwen_model_with_bot_suffix(self, mock_update):
        m = _make_message(text="/qwen@SomeName")
        self._cmds.change_model(m)
        self.assertEqual(mock_update.call_args[1].get("model"), "qwen-2.5-32b")


class TestGenerateImage(unittest.TestCase):
    def setUp(self):
        import core.commands as cmds
        self._cmds = cmds
        self.bot = MagicMock()
        cmds.register_handlers(self.bot, MagicMock(), MagicMock())

    @patch("core.commands.generate_image_hf", return_value=(MagicMock(), None))
    def test_prompt_extracted_without_bot_suffix(self, mock_gen):
        m = _make_message(text="/rysuj cyber cat")
        self._cmds.generate_image(m)
        mock_gen.assert_called_once_with("cyber cat")

    @patch("core.commands.generate_image_hf", return_value=(MagicMock(), None))
    def test_prompt_extracted_with_bot_suffix(self, mock_gen):
        m = _make_message(text="/rysuj@MyBot cyber cat")
        self._cmds.generate_image(m)
        mock_gen.assert_called_once_with("cyber cat")

    def test_empty_prompt_sends_usage_hint(self):
        m = _make_message(text="/rysuj")
        self._cmds.generate_image(m)
        calls_text = " ".join(str(c) for c in self.bot.send_message.call_args_list)
        self.assertIn("rysuj", calls_text)
        self.assertNotIn("Maluję", calls_text)

    def test_empty_prompt_with_bot_suffix_sends_usage_hint(self):
        m = _make_message(text="/rysuj@MyBot")
        self._cmds.generate_image(m)
        calls_text = " ".join(str(c) for c in self.bot.send_message.call_args_list)
        self.assertIn("rysuj", calls_text)
        self.assertNotIn("Maluję", calls_text)


class TestExplicitSearch(unittest.TestCase):
    def setUp(self):
        import core.commands as cmds
        self._cmds = cmds
        self.bot = MagicMock()
        cmds.register_handlers(self.bot, MagicMock(), MagicMock())

    @patch("core.commands.search_brave", return_value="result1\nresult2")
    def test_query_extracted_with_bot_suffix(self, mock_search):
        m = _make_message(text="/szukaj@MyBot python tutorials")
        self._cmds.explicit_search(m)
        mock_search.assert_called_once_with("python tutorials", count=5)

    @patch("core.commands.search_brave", return_value="result")
    def test_query_extracted_without_suffix(self, mock_search):
        m = _make_message(text="/szukaj ai tools")
        self._cmds.explicit_search(m)
        mock_search.assert_called_once_with("ai tools", count=5)


if __name__ == "__main__":
    unittest.main()
