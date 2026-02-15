"""Abstract base class for all trading strategies."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from config.settings import Settings


@dataclass
class Signal:
    """A trading signal emitted by a strategy."""
    strategy_name: str
    market_condition_id: str
    token_id: str
    side: str              # "BUY" or "SELL"
    confidence: float      # 0.0 to 1.0
    raw_edge: float        # Expected edge (e.g., 0.03 = 3%)
    suggested_price: float
    max_size: float        # Maximum position in USD
    metadata: dict = field(default_factory=dict)
    order_type: str = "limit"  # "limit" or "market"


class BaseStrategy(ABC):
    """Abstract base class — strategies emit Signals, never place orders."""

    def __init__(self, settings: Settings, name: str):
        self._settings = settings
        self.name = name
        self._enabled = True

    @abstractmethod
    def evaluate(self, market, orderbook, price_history):
        """Evaluate a market and return zero or more Signals.

        Args:
            market: dict from MarketFetcher
            orderbook: dict with 'bids' and 'asks'
            price_history: PriceHistory instance

        Returns:
            list[Signal]
        """

    @abstractmethod
    def get_required_data(self):
        """Return set of data types needed: {'orderbook', 'price_history', 'whale_trades', 'news'}"""

    def enable(self):
        self._enabled = True

    def disable(self):
        self._enabled = False

    @property
    def is_enabled(self):
        return self._enabled
