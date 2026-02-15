"""Tests for config.client_factory module."""
import unittest
from unittest.mock import patch, MagicMock

from config.settings import Settings


class TestClientFactory(unittest.TestCase):

    @patch("config.client_factory.HAS_CLOB", False)
    def test_returns_none_without_clob(self):
        """Returns None if py-clob-client is not installed."""
        from config.client_factory import create_clob_client
        settings = Settings(private_key="0xtest")
        result = create_clob_client(settings)
        self.assertIsNone(result)

    @patch("config.client_factory.HAS_CLOB", True)
    @patch("config.client_factory.ClobClient", create=True)
    def test_create_client_with_api_creds(self, MockClob):
        """When api_key/secret/passphrase are set, creds are passed to constructor."""
        from config.client_factory import create_clob_client
        mock_instance = MagicMock()
        MockClob.return_value = mock_instance

        settings = Settings(
            private_key="0xtest",
            api_key="key123",
            api_secret="secret123",
            passphrase="pass123",
        )
        client = create_clob_client(settings)
        self.assertIsNotNone(client)
        # Creds are now passed directly to constructor as ApiCreds object
        call_kwargs = MockClob.call_args[1]
        creds = call_kwargs["creds"]
        self.assertEqual(creds.api_key, "key123")
        self.assertEqual(creds.api_secret, "secret123")
        self.assertEqual(creds.api_passphrase, "pass123")
        # set_api_creds should NOT be called when explicit creds are provided
        mock_instance.set_api_creds.assert_not_called()

    @patch("config.client_factory.HAS_CLOB", True)
    @patch("config.client_factory.ClobClient", create=True)
    def test_create_client_derives_creds_when_missing(self, MockClob):
        """When api creds are empty, create_or_derive_api_creds is called."""
        from config.client_factory import create_clob_client
        mock_instance = MagicMock()
        mock_instance.create_or_derive_api_creds.return_value = {
            "apiKey": "derived", "secret": "derived", "passphrase": "derived"
        }
        MockClob.return_value = mock_instance

        settings = Settings(private_key="0xtest")
        client = create_clob_client(settings)
        self.assertIsNotNone(client)
        mock_instance.create_or_derive_api_creds.assert_called_once()


if __name__ == "__main__":
    unittest.main()
