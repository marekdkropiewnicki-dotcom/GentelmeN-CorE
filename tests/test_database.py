import unittest
from unittest.mock import MagicMock, patch, call

import core.database as db


class TestGetUserDataDefaults(unittest.TestCase):
    def setUp(self):
        db.user_prefs.clear()
        db.user_models.clear()

    def test_returns_defaults_when_no_db_and_no_cache(self):
        with patch.object(db, 'DB_URL', None):
            lang, model = db.get_user_data(999)
        self.assertEqual(lang, 'EN')
        self.assertEqual(model, 'llama-3.3-70b-versatile')

    def test_returns_cached_values(self):
        db.user_prefs[1] = 'PL'
        db.user_models[1] = 'qwen-2.5-32b'
        lang, model = db.get_user_data(1)
        self.assertEqual(lang, 'PL')
        self.assertEqual(model, 'qwen-2.5-32b')


class TestUpdateUserDb(unittest.TestCase):
    def setUp(self):
        db.user_prefs.clear()
        db.user_models.clear()

    def test_updates_cache_without_db(self):
        with patch.object(db, 'DB_URL', None):
            db.update_user_db(10, 'testuser', lang='PL', model='llama-3.1-8b-instant')
        self.assertEqual(db.user_prefs[10], 'PL')
        self.assertEqual(db.user_models[10], 'llama-3.1-8b-instant')

    def test_preserves_existing_lang_when_not_provided(self):
        db.user_prefs[20] = 'PL'
        db.user_models[20] = 'qwen-2.5-32b'
        with patch.object(db, 'DB_URL', None):
            db.update_user_db(20, 'user2', model='llama-3.1-8b-instant')
        self.assertEqual(db.user_prefs[20], 'PL')
        self.assertEqual(db.user_models[20], 'llama-3.1-8b-instant')

    def test_preserves_existing_model_when_not_provided(self):
        db.user_prefs[30] = 'EN'
        db.user_models[30] = 'llama-3.3-70b-versatile'
        with patch.object(db, 'DB_URL', None):
            db.update_user_db(30, 'user3', lang='PL')
        self.assertEqual(db.user_prefs[30], 'PL')
        self.assertEqual(db.user_models[30], 'llama-3.3-70b-versatile')


class TestInitDb(unittest.TestCase):
    def test_init_db_does_nothing_without_db_url(self):
        with patch.object(db, 'DB_URL', None):
            db.init_db()  # should not raise

    def test_init_db_calls_create_table(self):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        with patch.object(db, 'DB_URL', 'postgresql://fake'), \
             patch('psycopg2.connect', return_value=mock_conn):
            db.init_db()
        mock_cur.execute.assert_called_once()
        mock_conn.commit.assert_called_once()


if __name__ == '__main__':
    unittest.main()
