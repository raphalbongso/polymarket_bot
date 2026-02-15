"""High-confidence strategy — buy outcomes trading at 98%+ expecting resolution at 1.00."""
from config.settings import Settings
from strategies.base import BaseStrategy, Signal


class HighConfidenceStrategy(BaseStrategy):
    """Buy outcomes when the market is 98%+ one-sided, betting on resolution at 1.00.

    In BTC 15-minute markets, when one side reaches 98%+ it almost always resolves
    that way. Uses a fixed $10 bet size per trade; profits compound in the balance.
    """

    FIXED_SIZE_USD = 10.0

    def __init__(self, settings: Settings):
        super().__init__(settings, name="high_confidence")
        self._threshold = settings.high_confidence_threshold
        self._traded_markets = set()  # condition_ids already traded (1 trade per market)

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

            # Only trigger when the market is 98%+ confident in this outcome
            if best_bid < self._threshold:
                continue

            # Don't buy if the ask is so high there's no edge left
            if best_ask >= 0.995:
                continue

            # Buy at the best ask to get filled immediately
            buy_price = best_ask
            confidence = min(0.995, best_bid + 0.01)
            edge = 1.0 - buy_price

            self._traded_markets.add(cid)

            signals.append(Signal(
                strategy_name=self.name,
                market_condition_id=cid,
                token_id=token_id,
                side="BUY",
                confidence=confidence,
                raw_edge=edge,
                suggested_price=buy_price,
                max_size=self.FIXED_SIZE_USD,
                metadata={
                    "type": "high_confidence",
                    "market_price": best_bid,
                    "fixed_size_usd": self.FIXED_SIZE_USD,
                },
                order_type="market",
            ))
            break  # only trade one side per market

        return signals

    def get_required_data(self):
        return {"orderbook"}
