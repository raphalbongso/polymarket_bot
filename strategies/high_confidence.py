"""High-confidence strategy — BTC 5-min markets, 97%+ threshold, $6 fixed."""
from config.settings import Settings
from monitoring.logger import get_logger
from strategies.base import BaseStrategy, Signal

logger = get_logger("strategy.high_confidence")

FIXED_BET_USD = 10.0


class HighConfidenceStrategy(BaseStrategy):
    """Trade BTC 5-min markets.

    Rules:
        - YES > 97¢ → BUY YES for $6
        - NO  > 97¢ → BUY NO  for $6
        - Neither    → NO_TRADE
        - Redeem every 4th trade
    """

    def __init__(self, settings: Settings):
        super().__init__(settings, name="high_confidence")
        self._threshold = settings.high_confidence_threshold
        self._traded_markets = set()
        self.trade_count = 0

    def evaluate(self, market, orderbook, price_history):
        tokens = market.get("tokens", [])
        if len(tokens) != 2:
            return []

        cid = market["condition_id"]
        if cid in self._traded_markets:
            return []

        for token_id in tokens:
            book = orderbook.get(token_id, {})
            bids = book.get("bids", [])
            asks = book.get("asks", [])

            if not bids or not asks:
                continue

            best_bid = bids[0][0]
            best_ask = asks[0][0]

            # Only buy when both bid AND ask are >= threshold
            if best_bid < self._threshold:
                continue

            if best_ask < self._threshold:
                logger.info(
                    f"Skipped: bid {best_bid:.3f} >= threshold but "
                    f"ask {best_ask:.3f} < {self._threshold}"
                )
                continue

            if best_ask >= 0.995:
                continue

            self._traded_markets.add(cid)
            self.trade_count += 1
            buy_price = best_ask

            logger.info(
                f"Trade #{self.trade_count}: BUY @ {buy_price:.2f} "
                f"(bid {best_bid:.2f}) ${FIXED_BET_USD:.2f} "
                f"on {market.get('slug', '?')}"
            )

            return [Signal(
                strategy_name=self.name,
                market_condition_id=cid,
                token_id=token_id,
                side="BUY",
                confidence=min(0.995, best_bid + 0.01),
                raw_edge=1.0 - buy_price,
                suggested_price=buy_price,
                max_size=FIXED_BET_USD,
                metadata={
                    "type": "high_confidence",
                    "market_price": best_bid,
                    "fixed_size_usd": FIXED_BET_USD,
                },
                order_type="market",
            )]

        return []

    def should_redeem(self):
        """True every 4th trade."""
        return self.trade_count > 0 and self.trade_count % 4 == 0

    def get_required_data(self):
        return {"orderbook"}
