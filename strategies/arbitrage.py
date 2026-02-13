"""Arbitrage strategy — detect YES + NO mispricings."""
from config.settings import Settings
from strategies.base import BaseStrategy, Signal


class ArbitrageStrategy(BaseStrategy):
    """Detect mispricings where YES + NO asks < $1.00 or bids > $1.00."""

    def __init__(self, settings: Settings):
        super().__init__(settings, name="arbitrage")
        self._min_edge = 0.01     # Minimum 1 cent edge
        self._fee_buffer = 0.002  # Account for potential fees

    def evaluate(self, market, orderbook, price_history):
        signals = []
        tokens = market.get("tokens", [])
        if len(tokens) != 2:
            return signals

        yes_token, no_token = tokens[0], tokens[1]

        # Get orderbooks for both tokens
        yes_book = orderbook.get(yes_token, {})
        no_book = orderbook.get(no_token, {})

        yes_asks = yes_book.get("asks", [])
        no_asks = no_book.get("asks", [])
        yes_bids = yes_book.get("bids", [])
        no_bids = no_book.get("bids", [])

        # --- Buy Arbitrage: YES ask + NO ask < 1.0 ---
        if yes_asks and no_asks:
            yes_ask_price = yes_asks[0][0]
            no_ask_price = no_asks[0][0]
            total_cost = yes_ask_price + no_ask_price

            if total_cost < (1.0 - self._fee_buffer):
                edge = 1.0 - total_cost
                if edge >= self._min_edge:
                    confidence = min(1.0, edge / 0.05)
                    max_size_per_side = self._settings.max_position_size_usd / 2

                    signals.append(Signal(
                        strategy_name=self.name,
                        market_condition_id=market["condition_id"],
                        token_id=yes_token,
                        side="BUY",
                        confidence=confidence,
                        raw_edge=edge,
                        suggested_price=yes_ask_price,
                        max_size=max_size_per_side,
                        metadata={"arb_type": "buy", "pair_token": no_token},
                    ))
                    signals.append(Signal(
                        strategy_name=self.name,
                        market_condition_id=market["condition_id"],
                        token_id=no_token,
                        side="BUY",
                        confidence=confidence,
                        raw_edge=edge,
                        suggested_price=no_ask_price,
                        max_size=max_size_per_side,
                        metadata={"arb_type": "buy", "pair_token": yes_token},
                    ))

        # --- Sell Arbitrage: YES bid + NO bid > 1.0 ---
        if yes_bids and no_bids:
            yes_bid_price = yes_bids[0][0]
            no_bid_price = no_bids[0][0]
            total_bid = yes_bid_price + no_bid_price

            if total_bid > (1.0 + self._fee_buffer):
                edge = total_bid - 1.0
                if edge >= self._min_edge:
                    confidence = min(1.0, edge / 0.05)
                    max_size_per_side = self._settings.max_position_size_usd / 2

                    signals.append(Signal(
                        strategy_name=self.name,
                        market_condition_id=market["condition_id"],
                        token_id=yes_token,
                        side="SELL",
                        confidence=confidence,
                        raw_edge=edge,
                        suggested_price=yes_bid_price,
                        max_size=max_size_per_side,
                        metadata={"arb_type": "sell", "pair_token": no_token},
                    ))
                    signals.append(Signal(
                        strategy_name=self.name,
                        market_condition_id=market["condition_id"],
                        token_id=no_token,
                        side="SELL",
                        confidence=confidence,
                        raw_edge=edge,
                        suggested_price=no_bid_price,
                        max_size=max_size_per_side,
                        metadata={"arb_type": "sell", "pair_token": yes_token},
                    ))

        return signals

    def get_required_data(self):
        return {"orderbook"}
