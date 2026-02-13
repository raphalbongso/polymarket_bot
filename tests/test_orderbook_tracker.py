"""Tests for data.orderbook_tracker module."""
import unittest
from collections import deque
from unittest.mock import MagicMock

from config.settings import Settings
from data.orderbook_tracker import OrderbookTracker


class TestOrderbookTracker(unittest.TestCase):

    def _make_tracker(self, mock_book=None):
        settings = Settings(orderbook_history_maxlen=10)
        mock_client = MagicMock()
        if mock_book is not None:
            mock_client.get_order_book.return_value = mock_book
        tracker = OrderbookTracker(mock_client, settings)
        return tracker

    def test_fetch_orderbook(self):
        """Correctly parses bids and asks from mocked client response."""
        tracker = self._make_tracker({
            "bids": [
                {"price": "0.45", "size": "100"},
                {"price": "0.44", "size": "50"},
            ],
            "asks": [
                {"price": "0.48", "size": "80"},
                {"price": "0.50", "size": "60"},
            ],
        })

        book = tracker.fetch_orderbook("token_abc")
        self.assertEqual(len(book["bids"]), 2)
        self.assertEqual(len(book["asks"]), 2)
        self.assertAlmostEqual(book["bids"][0][0], 0.45)
        self.assertAlmostEqual(book["asks"][0][0], 0.48)

    def test_best_bid_ask(self):
        """get_best_bid and get_best_ask return correct values."""
        tracker = self._make_tracker({
            "bids": [{"price": "0.45", "size": "100"}],
            "asks": [{"price": "0.48", "size": "80"}],
        })
        tracker.fetch_orderbook("token_abc")

        self.assertAlmostEqual(tracker.get_best_bid("token_abc"), 0.45)
        self.assertAlmostEqual(tracker.get_best_ask("token_abc"), 0.48)

    def test_spread_calculation(self):
        """Spread is best_ask - best_bid."""
        tracker = self._make_tracker({
            "bids": [{"price": "0.45", "size": "100"}],
            "asks": [{"price": "0.48", "size": "80"}],
        })
        tracker.fetch_orderbook("token_abc")

        spread = tracker.get_spread("token_abc")
        self.assertAlmostEqual(spread, 0.03)

    def test_history_bounded(self):
        """Deque does not grow beyond maxlen."""
        tracker = self._make_tracker({
            "bids": [{"price": "0.50", "size": "10"}],
            "asks": [{"price": "0.55", "size": "10"}],
        })

        for _ in range(20):
            tracker.fetch_orderbook("token_abc")

        history = tracker.get_history("token_abc")
        self.assertLessEqual(len(history), 10)


if __name__ == "__main__":
    unittest.main()
