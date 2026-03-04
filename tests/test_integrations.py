import io
import unittest
from unittest.mock import MagicMock, patch

import core.integrations as integrations


class TestSearchBrave(unittest.TestCase):
    def test_returns_empty_string_without_key(self):
        with patch.object(integrations, 'BRAVE_KEY', None):
            result = integrations.search_brave("bitcoin")
        self.assertEqual(result, "")

    def test_returns_formatted_results(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'web': {
                'results': [
                    {'title': 'BTC News', 'description': 'Bitcoin is up'},
                    {'title': 'Crypto', 'description': 'Market rally'},
                ]
            }
        }
        with patch.object(integrations, 'BRAVE_KEY', 'fake-key'), \
             patch('requests.get', return_value=mock_response):
            result = integrations.search_brave("bitcoin")
        self.assertIn("BTC News", result)
        self.assertIn("Bitcoin is up", result)

    def test_returns_empty_on_exception(self):
        with patch.object(integrations, 'BRAVE_KEY', 'fake-key'), \
             patch('requests.get', side_effect=Exception("network error")):
            result = integrations.search_brave("query")
        self.assertEqual(result, "")


class TestGenerateImageHf(unittest.TestCase):
    def test_returns_error_without_token(self):
        with patch.object(integrations, 'HF_TOKEN', None):
            image_bytes, error = integrations.generate_image_hf("a cat")
        self.assertIsNone(image_bytes)
        self.assertIn("HF_TOKEN", error)

    def test_returns_image_bytes_on_success(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'\x89PNG\r\n'
        with patch.object(integrations, 'HF_TOKEN', 'fake-token'), \
             patch('requests.post', return_value=mock_response):
            image_bytes, error = integrations.generate_image_hf("cyberpunk cat")
        self.assertIsNone(error)
        self.assertIsInstance(image_bytes, io.BytesIO)
        self.assertEqual(image_bytes.read(), b'\x89PNG\r\n')

    def test_returns_error_on_non_200_status(self):
        mock_response = MagicMock()
        mock_response.status_code = 503
        with patch.object(integrations, 'HF_TOKEN', 'fake-token'), \
             patch('requests.post', return_value=mock_response):
            image_bytes, error = integrations.generate_image_hf("cat")
        self.assertIsNone(image_bytes)
        self.assertIn("503", error)

    def test_returns_error_on_exception(self):
        with patch.object(integrations, 'HF_TOKEN', 'fake-token'), \
             patch('requests.post', side_effect=Exception("timeout")):
            image_bytes, error = integrations.generate_image_hf("cat")
        self.assertIsNone(image_bytes)
        self.assertIn("timeout", error)


class TestInitKucoin(unittest.TestCase):
    def test_returns_none_on_exception(self):
        with patch('ccxt.kucoin', side_effect=Exception("bad credentials")):
            result = integrations.init_kucoin()
        self.assertIsNone(result)

    def test_returns_kucoin_instance(self):
        mock_kucoin = MagicMock()
        with patch('ccxt.kucoin', return_value=mock_kucoin):
            result = integrations.init_kucoin()
        self.assertEqual(result, mock_kucoin)


if __name__ == '__main__':
    unittest.main()
