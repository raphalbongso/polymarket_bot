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

    def test_trading_mode_defaults_to_dry_run(self):
        """Without TRADING_MODE or DRY_RUN, trading_mode is 'dry_run'."""
        with patch.dict(os.environ, {}, clear=True):
            settings = load_settings()
            self.assertEqual(settings.trading_mode, "dry_run")
            self.assertTrue(settings.dry_run)

    def test_trading_mode_paper(self):
        """TRADING_MODE=paper sets paper mode and dry_run=True."""
        with patch.dict(os.environ, {"TRADING_MODE": "paper"}, clear=True):
            settings = load_settings()
            self.assertEqual(settings.trading_mode, "paper")
            self.assertTrue(settings.dry_run)

    def test_trading_mode_live(self):
        """TRADING_MODE=live sets live mode and dry_run=False."""
        with patch.dict(os.environ, {"TRADING_MODE": "live"}, clear=True):
            settings = load_settings()
            self.assertEqual(settings.trading_mode, "live")
            self.assertFalse(settings.dry_run)

    def test_trading_mode_invalid_raises(self):
        """Invalid TRADING_MODE raises ValueError."""
        with patch.dict(os.environ, {"TRADING_MODE": "yolo"}, clear=True):
            with self.assertRaises(ValueError):
                load_settings()

    def test_dry_run_backward_compat(self):
        """DRY_RUN=false without TRADING_MODE sets trading_mode='live'."""
        with patch.dict(os.environ, {"DRY_RUN": "false"}, clear=True):
            settings = load_settings()
            self.assertEqual(settings.trading_mode, "live")
            self.assertFalse(settings.dry_run)

    def test_paper_settings_loaded(self):
        """Paper trading settings are loaded from environment."""
        env = {
            "TRADING_MODE": "paper",
            "PAPER_BALANCE": "5000.0",
            "PAPER_SLIPPAGE_BPS": "10.0",
            "PAPER_ORDER_TTL_SECONDS": "600",
        }
        with patch.dict(os.environ, env, clear=True):
            settings = load_settings()
            self.assertEqual(settings.paper_balance, 5000.0)
            self.assertEqual(settings.paper_slippage_bps, 10.0)
            self.assertEqual(settings.paper_order_ttl_seconds, 600.0)


if __name__ == "__main__":
    unittest.main()
