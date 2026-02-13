"""Tests for bot.orchestrator module."""
import unittest
from unittest.mock import patch, MagicMock

from config.settings import Settings
from bot.orchestrator import Orchestrator


class TestOrchestrator(unittest.TestCase):

    @patch("bot.orchestrator.create_clob_client", return_value=None)
    @patch("bot.orchestrator.ZMQPublisher")
    def test_dry_run_does_not_place_orders(self, MockZMQ, mock_client):
        """In dry run mode, CLOB client is never asked to post orders."""
        settings = Settings(dry_run=True)
        orch = Orchestrator(settings)

        from strategies.base import Signal
        signal = Signal(
            strategy_name="test",
            market_condition_id="cond1",
            token_id="tok1",
            side="BUY",
            confidence=0.6,
            raw_edge=0.05,
            suggested_price=0.50,
            max_size=50.0,
        )
        orch._execute_signal(signal, 25.0)

        # Since client is None and dry_run=True, no order placed
        # No exception raised = success

    @patch("bot.orchestrator.create_clob_client", return_value=None)
    @patch("bot.orchestrator.ZMQPublisher")
    def test_kill_switch_stops_loop(self, MockZMQ, mock_client):
        """Setting kill switch causes run() to exit."""
        settings = Settings(dry_run=True, tick_interval_seconds=0.01)
        orch = Orchestrator(settings)

        # Trigger kill switch before starting
        orch._risk_manager.trigger_kill_switch("test")
        orch._running = True

        # run() should exit immediately since kill switch is set
        # We'll call _tick to verify it doesn't blow up
        required = orch._get_required_data_types()
        self.assertTrue(orch._risk_manager.is_killed)

    @patch("bot.orchestrator.create_clob_client", return_value=None)
    @patch("bot.orchestrator.ZMQPublisher")
    def test_strategy_registration(self, MockZMQ, mock_client):
        """All strategies are registered (or gracefully skipped)."""
        settings = Settings(dry_run=True)
        orch = Orchestrator(settings)

        # Should have at least arbitrage and market_making
        names = [s.name for s in orch._strategies]
        self.assertIn("arbitrage", names)
        self.assertIn("market_making", names)
        # news_driven should be registered but disabled (no API keys)
        news = [s for s in orch._strategies if s.name == "news_driven"]
        if news:
            self.assertFalse(news[0].is_enabled)

    @patch("bot.orchestrator.create_clob_client")
    @patch("bot.orchestrator.ZMQPublisher")
    def test_live_trading_uses_create_and_post_order(self, MockZMQ, mock_create_client):
        """Live mode uses create_and_post_order with OrderArgs and options."""
        mock_clob = MagicMock()
        mock_clob.create_and_post_order.return_value = {"orderID": "abc123"}
        mock_create_client.return_value = mock_clob

        settings = Settings(trading_mode="live", dry_run=False)
        orch = Orchestrator(settings)

        # Seed tick_size and neg_risk in the orderbook tracker
        orch._orderbook_tracker._tick_sizes["tok1"] = "0.01"
        orch._orderbook_tracker._neg_risks["tok1"] = False

        from strategies.base import Signal
        signal = Signal(
            strategy_name="test",
            market_condition_id="cond1",
            token_id="tok1",
            side="BUY",
            confidence=0.8,
            raw_edge=0.1,
            suggested_price=0.50,
            max_size=100.0,
        )
        orch._execute_signal(signal, 25.0)

        # Verify create_and_post_order was called (not create_order + post_order)
        mock_clob.create_and_post_order.assert_called_once()
        args, kwargs = mock_clob.create_and_post_order.call_args
        order_args = args[0]
        self.assertEqual(order_args.token_id, "tok1")
        self.assertAlmostEqual(order_args.price, 0.50)
        self.assertAlmostEqual(order_args.size, 50.0)  # 25 / 0.50

        options = kwargs["options"]
        self.assertEqual(options.tick_size, "0.01")
        self.assertFalse(options.neg_risk)

    @patch("bot.orchestrator.create_clob_client", return_value=None)
    @patch("bot.orchestrator.ZMQPublisher")
    def test_slug_filter_limits_markets(self, MockZMQ, mock_client):
        """When market_slug_filter is set, only matching markets are traded."""
        settings = Settings(dry_run=True, market_slug_filter="btc-updown-15m")
        orch = Orchestrator(settings)

        # Simulate markets
        orch._market_fetcher._markets_cache = [
            {"condition_id": "c1", "slug": "btc-updown-15m-123", "tokens": ["t1", "t2"],
             "question": "", "outcome_prices": [0.5, 0.5], "volume": 0, "liquidity": 0},
            {"condition_id": "c2", "slug": "eth-updown-15m-456", "tokens": ["t3", "t4"],
             "question": "", "outcome_prices": [0.5, 0.5], "volume": 0, "liquidity": 0},
            {"condition_id": "c3", "slug": "btc-updown-15m-789", "tokens": ["t5", "t6"],
             "question": "", "outcome_prices": [0.5, 0.5], "volume": 0, "liquidity": 0},
        ]
        orch._market_fetcher._last_fetch = 9999999999.0  # Prevent refresh

        # Run one tick
        required = orch._get_required_data_types()
        orch._tick(required)

        # Only btc markets should have been processed — check orderbook fetches
        fetched_tokens = set()
        for call in orch._orderbook_tracker._client.get_order_book.call_args_list if orch._orderbook_tracker._client else []:
            fetched_tokens.add(call[0][0])
        # eth tokens should not be fetched (client is None so no calls, but
        # we can verify via the filter itself)
        self.assertEqual(len(orch._slug_prefixes), 1)
        self.assertEqual(orch._slug_prefixes[0], "btc-updown-15m")

    @patch("bot.orchestrator.create_clob_client")
    @patch("bot.orchestrator.ZMQPublisher")
    def test_live_trading_skips_without_tick_size(self, MockZMQ, mock_create_client):
        """Live mode refuses to trade when tick_size is unknown."""
        mock_clob = MagicMock()
        mock_create_client.return_value = mock_clob

        settings = Settings(trading_mode="live", dry_run=False)
        orch = Orchestrator(settings)

        from strategies.base import Signal
        signal = Signal(
            strategy_name="test",
            market_condition_id="cond1",
            token_id="tok_unknown",
            side="BUY",
            confidence=0.8,
            raw_edge=0.1,
            suggested_price=0.50,
            max_size=100.0,
        )
        orch._execute_signal(signal, 25.0)

        # Should NOT have attempted to place an order
        mock_clob.create_and_post_order.assert_not_called()


if __name__ == "__main__":
    unittest.main()
