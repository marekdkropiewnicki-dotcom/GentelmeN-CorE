import unittest
from unittest.mock import MagicMock, patch, call

import core.database as db
import core.helpers as helpers
from core.commands import register_handlers


def _make_message(user_id=1, username='testuser', chat_id=100,
                  text='/start', thread_id=None):
    """Build a minimal mock telebot Message."""
    m = MagicMock()
    m.from_user.id = user_id
    m.from_user.username = username
    m.chat.id = chat_id
    m.text = text
    m.message_thread_id = thread_id
    m.message_id = 42
    return m


class TestCommandHandlers(unittest.TestCase):
    def setUp(self):
        db.user_prefs.clear()
        db.user_models.clear()
        helpers.user_history.clear()
        self.bot = MagicMock()
        self.groq_client = MagicMock()
        self.kucoin = MagicMock()
        # Capture registered handlers by intercepting the decorator calls.
        self._handlers = {}
        original_handler = self.bot.message_handler

        def capture_handler(**kwargs):
            def decorator(fn):
                cmds = kwargs.get('commands', [])
                for c in cmds:
                    self._handlers[c] = fn
                content = kwargs.get('content_types', [])
                for ct in content:
                    self._handlers[ct] = fn
                func = kwargs.get('func')
                if func:
                    self._handlers['_catch_all'] = fn
                return fn
            return decorator

        self.bot.message_handler.side_effect = capture_handler
        register_handlers(self.bot, self.groq_client, self.kucoin)

    # ------------------------------------------------------------------
    # /start
    # ------------------------------------------------------------------
    def test_start_resets_history_and_sends_welcome(self):
        helpers.user_history[1] = [{"role": "user", "content": "old"}]
        m = _make_message(text='/start')
        self._handlers['start'](m)
        self.assertEqual(helpers.user_history[1], [])
        self.bot.send_message.assert_called_once()
        args = self.bot.send_message.call_args
        self.assertIn("Welcome", args[0][1])

    # ------------------------------------------------------------------
    # /en and /pl
    # ------------------------------------------------------------------
    def test_change_language_to_en(self):
        with patch.object(db, 'DB_URL', None):
            m = _make_message(text='/en')
            self._handlers['en'](m)
        self.assertEqual(db.user_prefs[1], 'EN')

    def test_change_language_to_pl(self):
        with patch.object(db, 'DB_URL', None):
            m = _make_message(text='/pl')
            self._handlers['pl'](m)
        self.assertEqual(db.user_prefs[1], 'PL')

    # ------------------------------------------------------------------
    # /llama, /fast, /qwen
    # ------------------------------------------------------------------
    def test_change_model_llama(self):
        with patch.object(db, 'DB_URL', None):
            m = _make_message(text='/llama')
            self._handlers['llama'](m)
        self.assertEqual(db.user_models[1], 'llama-3.3-70b-versatile')

    def test_change_model_fast(self):
        with patch.object(db, 'DB_URL', None):
            m = _make_message(text='/fast')
            self._handlers['fast'](m)
        self.assertEqual(db.user_models[1], 'llama-3.1-8b-instant')

    def test_change_model_qwen(self):
        with patch.object(db, 'DB_URL', None):
            m = _make_message(text='/qwen')
            self._handlers['qwen'](m)
        self.assertEqual(db.user_models[1], 'qwen-2.5-32b')

    # ------------------------------------------------------------------
    # /balance
    # ------------------------------------------------------------------
    def test_balance_denied_for_non_owner(self):
        m = _make_message(username='other_user', text='/balance')
        self._handlers['balance'](m)
        self.bot.send_message.assert_called_once()
        self.assertIn("Brak dostępu", self.bot.send_message.call_args[0][1])

    def test_balance_error_when_kucoin_none(self):
        m = _make_message(username='GentelmeN_CorE', text='/balance')
        handler = _get_registered_balance_handler(self.bot, self.groq_client, kucoin=None)
        handler(m)
        self.bot.send_message.assert_called()
        last_msg = self.bot.send_message.call_args[0][1]
        self.assertIn("Brak kluczy KuCoin", last_msg)

    # ------------------------------------------------------------------
    # /rysuj
    # ------------------------------------------------------------------
    def test_rysuj_empty_prompt(self):
        m = _make_message(text='/rysuj')
        self._handlers['rysuj'](m)
        self.bot.send_message.assert_called_once()
        self.assertIn("Co mam narysować", self.bot.send_message.call_args[0][1])

    def test_rysuj_sends_photo_on_success(self):
        import io as _io
        fake_image = _io.BytesIO(b'\x89PNG')
        m = _make_message(text='/rysuj cyberpunk cat')
        with patch('core.commands.generate_image_hf', return_value=(fake_image, None)):
            self._handlers['rysuj'](m)
        self.bot.send_photo.assert_called_once()

    def test_rysuj_sends_error_message_on_failure(self):
        m = _make_message(text='/rysuj cyberpunk cat')
        with patch('core.commands.generate_image_hf', return_value=(None, "❌ some error")):
            self._handlers['rysuj'](m)
        self.bot.send_message.assert_called()
        last_msg = self.bot.send_message.call_args[0][1]
        self.assertIn("some error", last_msg)

    # ------------------------------------------------------------------
    # ai_chat catch-all
    # ------------------------------------------------------------------
    def test_ai_chat_sends_reply(self):
        mock_completion = MagicMock()
        mock_completion.choices[0].message.content = "Hello there!"
        self.groq_client.chat.completions.create.return_value = mock_completion
        with patch.object(db, 'DB_URL', None):
            m = _make_message(text='hi')
            self._handlers['_catch_all'](m)
        self.bot.send_message.assert_called()
        last_msg = self.bot.send_message.call_args[0][1]
        self.assertEqual(last_msg, "Hello there!")

    def test_ai_chat_trims_history_to_max(self):
        mock_completion = MagicMock()
        mock_completion.choices[0].message.content = "reply"
        self.groq_client.chat.completions.create.return_value = mock_completion
        # Pre-fill history beyond MAX_HISTORY
        helpers.user_history[1] = [
            {"role": "user", "content": f"msg{i}"} for i in range(10)
        ]
        with patch.object(db, 'DB_URL', None):
            m = _make_message(text='another message')
            self._handlers['_catch_all'](m)
        self.assertLessEqual(len(helpers.user_history[1]), helpers.MAX_HISTORY)


def _get_registered_balance_handler(bot, groq_client, kucoin):
    """Re-register handlers with a different kucoin value and return /balance."""
    captured = {}
    original_side_effect = bot.message_handler.side_effect

    def capture_handler(**kwargs):
        def decorator(fn):
            for c in kwargs.get('commands', []):
                captured[c] = fn
            return fn
        return decorator

    bot.message_handler.side_effect = capture_handler
    register_handlers(bot, groq_client, kucoin)
    bot.message_handler.side_effect = original_side_effect
    return captured.get('balance')


if __name__ == '__main__':
    unittest.main()
