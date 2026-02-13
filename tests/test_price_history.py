"""Tests for data.price_history module."""
import math
import unittest

from config.settings import Settings
from data.price_history import PriceHistory


class TestPriceHistory(unittest.TestCase):

    def _make_history(self, maxlen=1000):
        settings = Settings(price_history_maxlen=maxlen)
        return PriceHistory(settings)

    def test_record_and_retrieve(self):
        """Prices recorded can be retrieved in order."""
        ph = self._make_history()
        ph.record("t1", 0.50, timestamp=1.0)
        ph.record("t1", 0.55, timestamp=2.0)
        ph.record("t1", 0.60, timestamp=3.0)

        prices = ph.get_prices("t1")
        self.assertEqual(prices, [0.50, 0.55, 0.60])
        self.assertAlmostEqual(ph.get_latest("t1"), 0.60)

    def test_bounded_deque(self):
        """History does not exceed maxlen."""
        ph = self._make_history(maxlen=5)
        for i in range(20):
            ph.record("t1", 0.50 + i * 0.01, timestamp=float(i))

        prices = ph.get_prices("t1")
        self.assertEqual(len(prices), 5)

    def test_moving_average(self):
        """SMA calculated correctly over window."""
        ph = self._make_history()
        for i in range(10):
            ph.record("t1", float(i + 1), timestamp=float(i))

        # SMA of [6, 7, 8, 9, 10] = 8.0
        sma = ph.get_moving_average("t1", window=5)
        self.assertAlmostEqual(sma, 8.0)

    def test_volatility(self):
        """Volatility (std dev of log returns) is a positive number."""
        ph = self._make_history()
        prices = [1.0, 1.05, 0.98, 1.02, 1.10, 0.95, 1.08, 1.03, 0.99, 1.07, 1.01]
        for i, p in enumerate(prices):
            ph.record("t1", p, timestamp=float(i))

        vol = ph.get_volatility("t1", window=10)
        self.assertIsNotNone(vol)
        self.assertGreater(vol, 0)

        # Manually verify: compute log returns and std
        log_returns = [math.log(prices[i] / prices[i - 1]) for i in range(1, len(prices))]
        mean = sum(log_returns) / len(log_returns)
        variance = sum((r - mean) ** 2 for r in log_returns) / (len(log_returns) - 1)
        expected_vol = math.sqrt(variance)
        self.assertAlmostEqual(vol, expected_vol, places=6)


if __name__ == "__main__":
    unittest.main()
