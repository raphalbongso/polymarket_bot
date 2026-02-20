"""High-confidence strategy — buy outcomes trading at 97%+ expecting resolution at 1.00."""
from config.settings import Settings
from monitoring.logger import get_logger
from strategies.base import BaseStrategy, Signal

logger = get_logger("strategy.high_confidence")

FIXED_BET_USD = 6.0


class HighConfidenceStrategy(BaseStrategy):
    """Buy outcomes when the market is 97%+ one-sided, betting on resolution at 1.00.

    Fixed $6 bet per trade. No compounding.
    """

    def __init__(self, settings: Settings):
        super().__init__(settings, name="high_confidence")
        self._threshold = settings.high_confidence_threshold
        self._traded_markets = set()

    def evaluate(self, market, orderbook, price_history):
        signals = []
        tokens = market.get("tokens", [])
        if len(tokens) != 2:
            return signals

        cid = market["condition_id"]
        if cid in self._traded_markets:
            return signals

        for token_id in tokens:
            book = orderbook.get(token_id, {})
            bids = book.get("bids", [])
            asks = book.get("asks", [])

            if not bids or not asks:
                continue

            best_bid = bids[0][0]
            best_ask = asks[0][0]

            if best_bid < self._threshold:
                continue

            if best_ask >= 0.995:
                continue

            buy_price = best_ask
            confidence = min(0.995, best_bid + 0.01)
            edge = 1.0 - buy_price

            self._traded_markets.add(cid)

            logger.info(
                f"Signal: BUY @ {buy_price:.4f}, bet ${FIXED_BET_USD:.2f}"
            )

            signals.append(Signal(
                strategy_name=self.name,
                market_condition_id=cid,
                token_id=token_id,
                side="BUY",
                confidence=confidence,
                raw_edge=edge,
                suggested_price=buy_price,
                max_size=FIXED_BET_USD,
                metadata={
                    "type": "high_confidence",
                    "market_price": best_bid,
                    "fixed_size_usd": FIXED_BET_USD,
                },
                order_type="market",
            ))
            break

        return signals

    def get_required_data(self):
        return {"orderbook"}
