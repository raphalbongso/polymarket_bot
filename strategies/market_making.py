"""Market making strategy — earn bid-ask spread with inventory management."""
from config.settings import Settings
from strategies.base import BaseStrategy, Signal


class MarketMakingStrategy(BaseStrategy):
    """Quote both sides of the book with inventory-aware skew."""

    def __init__(self, settings: Settings):
        super().__init__(settings, name="market_making")
        self._min_spread = 0.02
        self._inventory = {}  # token_id -> net position
        self._max_inventory = 100.0
        self._skew_factor = 0.5

    def evaluate(self, market, orderbook, price_history):
        signals = []
        tokens = market.get("tokens", [])
        if len(tokens) != 2:
            return signals

        yes_token = tokens[0]
        book = orderbook.get(yes_token, {})
        bids = book.get("bids", [])
        asks = book.get("asks", [])

        if not bids or not asks:
            return signals

        best_bid = bids[0][0]
        best_ask = asks[0][0]
        current_spread = best_ask - best_bid

        if current_spread < self._min_spread:
            return signals

        midpoint = (best_bid + best_ask) / 2
        half_spread = max(current_spread / 2, self._min_spread / 2)

        # Widen spread with volatility
        vol = price_history.get_volatility(yes_token, window=20)
        if vol is not None and vol > 0:
            half_spread *= (1 + vol * 10)

        # Inventory skew
        inventory = self._inventory.get(yes_token, 0.0)
        skew = self._skew_factor * (inventory / self._max_inventory) * half_spread

        bid_price = round(midpoint - half_spread + skew, 4)
        ask_price = round(midpoint + half_spread + skew, 4)

        # Clamp to valid price range
        bid_price = max(0.01, min(0.99, bid_price))
        ask_price = max(0.01, min(0.99, ask_price))

        confidence = min(0.8, current_spread / 0.05)

        # BUY side (if not over-long)
        if inventory < self._max_inventory:
            signals.append(Signal(
                strategy_name=self.name,
                market_condition_id=market["condition_id"],
                token_id=yes_token,
                side="BUY",
                confidence=confidence,
                raw_edge=half_spread,
                suggested_price=bid_price,
                max_size=self._settings.max_position_size_usd,
                metadata={"type": "market_making", "inventory": inventory},
            ))

        # SELL side (if not over-short)
        if inventory > -self._max_inventory:
            signals.append(Signal(
                strategy_name=self.name,
                market_condition_id=market["condition_id"],
                token_id=yes_token,
                side="SELL",
                confidence=confidence,
                raw_edge=half_spread,
                suggested_price=ask_price,
                max_size=self._settings.max_position_size_usd,
                metadata={"type": "market_making", "inventory": inventory},
            ))

        return signals

    def update_inventory(self, token_id, delta):
        """Update inventory tracking after a fill."""
        self._inventory[token_id] = self._inventory.get(token_id, 0.0) + delta

    def get_required_data(self):
        return {"orderbook", "price_history"}
