from strategies.base import BaseStrategy, Signal
from strategies.arbitrage import ArbitrageStrategy
from strategies.high_confidence import HighConfidenceStrategy
from strategies.market_making import MarketMakingStrategy
from strategies.news_driven import NewsDrivenStrategy
from strategies.whale_following import WhaleFollowingStrategy

__all__ = [
    "BaseStrategy", "Signal",
    "ArbitrageStrategy", "HighConfidenceStrategy", "MarketMakingStrategy",
    "NewsDrivenStrategy", "WhaleFollowingStrategy",
]
