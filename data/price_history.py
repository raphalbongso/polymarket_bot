"""Track price history for tokens using bounded deques."""
import math
import time
from collections import deque

from config.settings import Settings

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


class PriceHistory:
    """Bounded price history per token with SMA and volatility calculations."""

    def __init__(self, settings: Settings):
        self._history = {}  # token_id -> deque of (timestamp, price)
        self._maxlen = settings.price_history_maxlen

    def record(self, token_id, price, timestamp=None):
        """Append a price observation."""
        if token_id not in self._history:
            self._history[token_id] = deque(maxlen=self._maxlen)
        ts = timestamp if timestamp is not None else time.time()
        self._history[token_id].append((ts, price))

    def get_prices(self, token_id):
        """Return list of prices (no timestamps) for a token."""
        if token_id not in self._history:
            return []
        return [p for _, p in self._history[token_id]]

    def get_latest(self, token_id):
        """Return most recent price, or None."""
        if token_id in self._history and self._history[token_id]:
            return self._history[token_id][-1][1]
        return None

    def get_moving_average(self, token_id, window=20):
        """Simple moving average over last `window` observations."""
        prices = self.get_prices(token_id)
        if len(prices) < window:
            return None
        subset = prices[-window:]
        return sum(subset) / len(subset)

    def get_volatility(self, token_id, window=20):
        """Standard deviation of log returns over last `window` observations."""
        prices = self.get_prices(token_id)
        if len(prices) < window + 1:
            return None

        subset = prices[-(window + 1):]
        log_returns = []
        for i in range(1, len(subset)):
            if subset[i - 1] > 0 and subset[i] > 0:
                log_returns.append(math.log(subset[i] / subset[i - 1]))

        if len(log_returns) < 2:
            return None

        if HAS_NUMPY:
            return float(np.std(log_returns, ddof=1))

        # Fallback: manual std dev
        mean = sum(log_returns) / len(log_returns)
        variance = sum((r - mean) ** 2 for r in log_returns) / (len(log_returns) - 1)
        return math.sqrt(variance)
