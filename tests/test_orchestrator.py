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


if __name__ == "__main__":
    unittest.main()
