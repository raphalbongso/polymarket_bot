"""Tests for data.whale_tracker module."""
import time
import unittest
from unittest.mock import patch, MagicMock

from config.settings import Settings
from data.whale_tracker import WhaleTracker


class TestWhaleTracker(unittest.TestCase):

    def _make_tracker(self):
        settings = Settings(whale_wallets=("0xwhale1", "0xwhale2"))
        return WhaleTracker(settings)

    @patch("data.whale_tracker.requests.Session")
    def test_fetch_wallet_activity(self, MockSession):
        """Parses mocked Data API response into trade list."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = [
            {"id": "t1", "side": "BUY", "size": "5000", "price": "0.60"},
            {"id": "t2", "side": "SELL", "size": "2000", "price": "0.55"},
        ]
        mock_resp.raise_for_status = MagicMock()
        MockSession.return_value.get.return_value = mock_resp

        tracker = self._make_tracker()
        trades = tracker.fetch_wallet_activity("0xwhale1")
        self.assertEqual(len(trades), 2)

    @patch("data.whale_tracker.requests.Session")
    def test_deduplication(self, MockSession):
        """Same trade is not returned twice by check_all_wallets."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = [
            {"id": "t1", "side": "BUY", "size": "5000", "price": "0.60"},
        ]
        mock_resp.raise_for_status = MagicMock()
        MockSession.return_value.get.return_value = mock_resp

        tracker = self._make_tracker()
        first = tracker.check_all_wallets()
        second = tracker.check_all_wallets()

        self.assertGreater(len(first), 0)
        # Second call should not return the same trade again
        # (t1 already seen for both wallets)
        self.assertEqual(len(second), 0)

    def test_whale_signals_filter_by_size(self):
        """Only trades above min_trade_size generate signals."""
        tracker = self._make_tracker()

        # Manually inject trades
        from collections import deque
        tracker._recent_trades["0xwhale1"] = deque(maxlen=500)
        tracker._recent_trades["0xwhale1"].append({
            "size": "500",  # Below $1000 threshold
            "side": "BUY",
            "conditionId": "cond1",
            "tokenId": "tok1",
            "price": "0.5",
            "_fetched_at": time.time(),
        })
        tracker._recent_trades["0xwhale1"].append({
            "size": "5000",  # Above threshold
            "side": "BUY",
            "conditionId": "cond2",
            "tokenId": "tok2",
            "price": "0.6",
            "_fetched_at": time.time(),
        })

        signals = tracker.get_whale_signals()
        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0]["market_condition_id"], "cond2")


if __name__ == "__main__":
    unittest.main()
