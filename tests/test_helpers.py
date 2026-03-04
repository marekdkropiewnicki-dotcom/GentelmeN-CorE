import unittest
from unittest.mock import MagicMock, patch

from core.helpers import MAX_HISTORY, inteligentna_odpowiedz, user_history


class TestMaxHistory(unittest.TestCase):
    def test_max_history_value(self):
        self.assertEqual(MAX_HISTORY, 6)


class TestUserHistoryDict(unittest.TestCase):
    def test_user_history_is_dict(self):
        self.assertIsInstance(user_history, dict)


class TestInteligentnaOdpowiedz(unittest.TestCase):
    def test_sends_with_thread_id(self):
        mock_bot = MagicMock()
        inteligentna_odpowiedz(mock_bot, chat_id=100, text="hello", thread_id=42)
        mock_bot.send_message.assert_called_once_with(100, "hello", message_thread_id=42)

    def test_sends_without_thread_id(self):
        mock_bot = MagicMock()
        inteligentna_odpowiedz(mock_bot, chat_id=100, text="hello", thread_id=None)
        mock_bot.send_message.assert_called_once_with(100, "hello")

    def test_sends_without_thread_id_zero(self):
        mock_bot = MagicMock()
        inteligentna_odpowiedz(mock_bot, chat_id=200, text="world", thread_id=0)
        mock_bot.send_message.assert_called_once_with(200, "world")


if __name__ == '__main__':
    unittest.main()
