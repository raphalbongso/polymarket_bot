"""Whale-following strategy — copy trades from proven successful wallets."""
import time

from config.settings import Settings
from data.whale_tracker import WhaleTracker
from strategies.base import BaseStrategy, Signal


class WhaleFollowingStrategy(BaseStrategy):
    """Follow large wallet trades with size and decay filtering."""

    def __init__(self, settings: Settings, whale_tracker: WhaleTracker):
        super().__init__(settings, name="whale_following")
        self._whale_tracker = whale_tracker
        self._min_trade_size = 1000.0
        self._signal_decay_seconds = 300  # 5 minutes

    def evaluate(self, market, orderbook, price_history):
        signals = []
        condition_id = market.get("condition_id", "")
        now = time.time()

        whale_signals = self._whale_tracker.get_whale_signals()

        # Filter for this market
        relevant = [
            s for s in whale_signals
            if s.get("market_condition_id") == condition_id
        ]

        # Filter by age and size
        valid = []
        for ws in relevant:
            age = now - ws.get("timestamp", now)
            if age > self._signal_decay_seconds:
                continue
            if ws.get("size", 0) < self._min_trade_size:
                continue
            valid.append(ws)

        if not valid:
            return signals

        # Aggregate: if multiple whales agree, boost confidence
        buy_count = sum(1 for s in valid if s["side"] == "BUY")
        sell_count = sum(1 for s in valid if s["side"] == "SELL")

        for ws in valid:
            base_confidence = ws.get("confidence", 0.3)
            # Boost if multiple whales agree
            same_direction = buy_count if ws["side"] == "BUY" else sell_count
            confidence = min(0.6, base_confidence * (1 + 0.1 * (same_direction - 1)))

            tokens = market.get("tokens", [])
            token_id = ws.get("token_id", "")
            if not token_id and tokens:
                token_id = tokens[0] if ws["side"] == "BUY" else tokens[1]

            signals.append(Signal(
                strategy_name=self.name,
                market_condition_id=condition_id,
                token_id=token_id,
                side=ws["side"],
                confidence=confidence,
                raw_edge=0.02,  # Assumed edge from whale alpha
                suggested_price=ws.get("price", 0.5),
                max_size=self._settings.max_position_size_usd * 0.5,
                metadata={
                    "whale_wallet": ws.get("wallet", ""),
                    "whale_size": ws.get("size", 0),
                    "whales_agreeing": same_direction,
                },
            ))

        return signals

    def get_required_data(self):
        return {"whale_trades", "orderbook"}
