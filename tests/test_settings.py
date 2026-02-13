"""Tests for config.settings module."""
import dataclasses
import os
import unittest
from unittest.mock import patch

from config.settings import Settings, load_settings


class TestSettings(unittest.TestCase):

    def test_load_settings_defaults(self):
        """Settings loads with sensible defaults when env vars are minimal."""
        with patch.dict(os.environ, {}, clear=True):
            settings = load_settings()
            self.assertIsInstance(settings, Settings)
            self.assertEqual(settings.chain_id, 137)
            self.assertEqual(settings.kelly_fraction, 0.25)

    def test_dry_run_defaults_true(self):
        """DRY_RUN is True when not set in environment."""
        with patch.dict(os.environ, {}, clear=True):
            settings = load_settings()
            self.assertTrue(settings.dry_run)

    def test_settings_immutable(self):
        """Assigning to a frozen dataclass attribute raises FrozenInstanceError."""
        settings = Settings()
        with self.assertRaises(dataclasses.FrozenInstanceError):
            settings.dry_run = False

    def test_whale_wallets_parsed_from_csv(self):
        """WHALE_WALLETS CSV is parsed into a tuple."""
        with patch.dict(os.environ, {"WHALE_WALLETS": "0xabc,0xdef,0x123"}, clear=True):
            settings = load_settings()
            self.assertEqual(settings.whale_wallets, ("0xabc", "0xdef", "0x123"))

    def test_settings_with_missing_optional_keys(self):
        """Missing NEWS_API_KEY and OPENAI_API_KEY default to empty string."""
        with patch.dict(os.environ, {}, clear=True):
            settings = load_settings()
            self.assertEqual(settings.news_api_key, "")
            self.assertEqual(settings.openai_api_key, "")


if __name__ == "__main__":
    unittest.main()
