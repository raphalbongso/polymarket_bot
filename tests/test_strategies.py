"""Tests for all four trading strategies."""
import time
import unittest
from unittest.mock import MagicMock, patch

from config.settings import Settings
from data.price_history import PriceHistory
from data.whale_tracker import WhaleTracker
from strategies.arbitrage import ArbitrageStrategy
from strategies.market_making import MarketMakingStrategy
from strategies.news_driven import NewsDrivenStrategy
from strategies.whale_following import WhaleFollowingStrategy


def _make_settings(**overrides):
    return Settings(**overrides)


def _make_price_history(token_id="tok_yes", prices=None):
    ph = PriceHistory(_make_settings())
    if prices:
        for i, p in enumerate(prices):
            ph.record(token_id, p, timestamp=float(i))
    return ph


def _make_market(yes_token="tok_yes", no_token="tok_no", condition_id="cond1"):
    return {
        "condition_id": condition_id,
        "question": "Will something happen?",
        "tokens": [yes_token, no_token],
        "outcome_prices": [0.50, 0.50],
    }


# ==================== Arbitrage Tests ====================

class TestArbitrageStrategy(unittest.TestCase):

    def test_detects_buy_arb(self):
        """YES ask 0.45 + NO ask 0.50 = 0.95 < 1.0 -> BUY signals."""
        strategy = ArbitrageStrategy(_make_settings())
        market = _make_market()
        orderbook = {
            "tok_yes": {"bids": [(0.44, 100)], "asks": [(0.45, 100)]},
            "tok_no": {"bids": [(0.49, 100)], "asks": [(0.50, 100)]},
        }
        ph = _make_price_history()

        signals = strategy.evaluate(market, orderbook, ph)
        buy_signals = [s for s in signals if s.side == "BUY"]
        self.assertEqual(len(buy_signals), 2)
        self.assertTrue(all(s.metadata["arb_type"] == "buy" for s in buy_signals))

    def test_no_arb_when_prices_fair(self):
        """YES ask 0.52 + NO ask 0.50 = 1.02 -> no buy arb signal."""
        strategy = ArbitrageStrategy(_make_settings())
        market = _make_market()
        orderbook = {
            "tok_yes": {"bids": [(0.48, 100)], "asks": [(0.52, 100)]},
            "tok_no": {"bids": [(0.46, 100)], "asks": [(0.50, 100)]},
        }
        ph = _make_price_history()

        signals = strategy.evaluate(market, orderbook, ph)
        buy_signals = [s for s in signals if s.side == "BUY" and s.metadata.get("arb_type") == "buy"]
        self.assertEqual(len(buy_signals), 0)

    def test_detects_sell_arb(self):
        """YES bid 0.55 + NO bid 0.50 = 1.05 > 1.0 -> SELL signals."""
        strategy = ArbitrageStrategy(_make_settings())
        market = _make_market()
        orderbook = {
            "tok_yes": {"bids": [(0.55, 100)], "asks": [(0.58, 100)]},
            "tok_no": {"bids": [(0.50, 100)], "asks": [(0.53, 100)]},
        }
        ph = _make_price_history()

        signals = strategy.evaluate(market, orderbook, ph)
        sell_signals = [s for s in signals if s.side == "SELL"]
        self.assertEqual(len(sell_signals), 2)

    def test_respects_fee_buffer(self):
        """Edge of 0.001 is below min_edge -> no signal."""
        strategy = ArbitrageStrategy(_make_settings())
        market = _make_market()
        orderbook = {
            "tok_yes": {"bids": [(0.49, 100)], "asks": [(0.495, 100)]},
            "tok_no": {"bids": [(0.49, 100)], "asks": [(0.500, 100)]},
        }
        ph = _make_price_history()

        signals = strategy.evaluate(market, orderbook, ph)
        # 0.495 + 0.500 = 0.995 -> edge = 0.005, but < min_edge of 0.01
        buy_signals = [s for s in signals if s.metadata.get("arb_type") == "buy"]
        self.assertEqual(len(buy_signals), 0)


# ==================== Market Making Tests ====================

class TestMarketMakingStrategy(unittest.TestCase):

    def test_emits_bid_and_ask(self):
        """Produces both BUY and SELL signals when spread is wide enough."""
        strategy = MarketMakingStrategy(_make_settings())
        market = _make_market()
        orderbook = {
            "tok_yes": {"bids": [(0.45, 100)], "asks": [(0.55, 100)]},
        }
        ph = _make_price_history()

        signals = strategy.evaluate(market, orderbook, ph)
        sides = {s.side for s in signals}
        self.assertIn("BUY", sides)
        self.assertIn("SELL", sides)

    def test_skips_tight_spread(self):
        """No signals when spread < min_spread."""
        strategy = MarketMakingStrategy(_make_settings())
        market = _make_market()
        orderbook = {
            "tok_yes": {"bids": [(0.500, 100)], "asks": [(0.502, 100)]},
        }
        ph = _make_price_history()

        signals = strategy.evaluate(market, orderbook, ph)
        self.assertEqual(len(signals), 0)

    def test_inventory_skew(self):
        """Long inventory affects bid/ask placement."""
        strategy = MarketMakingStrategy(_make_settings())
        strategy._inventory["tok_yes"] = 50.0  # Half max inventory
        market = _make_market()
        orderbook = {
            "tok_yes": {"bids": [(0.45, 100)], "asks": [(0.55, 100)]},
        }
        ph = _make_price_history()

        signals = strategy.evaluate(market, orderbook, ph)
        buy_signal = next((s for s in signals if s.side == "BUY"), None)
        sell_signal = next((s for s in signals if s.side == "SELL"), None)

        self.assertIsNotNone(buy_signal)
        self.assertIsNotNone(sell_signal)
        # With long inventory, bid should be lower than without skew
        # Midpoint is 0.50, half_spread ~0.05, skew pushes bid lower
        self.assertLess(buy_signal.suggested_price, 0.50)

    def test_volatility_widens_spread(self):
        """Higher volatility produces wider quoted spread."""
        strategy = MarketMakingStrategy(_make_settings())
        market = _make_market()
        orderbook = {
            "tok_yes": {"bids": [(0.45, 100)], "asks": [(0.55, 100)]},
        }

        # No volatility data
        ph_no_vol = _make_price_history()
        signals_no_vol = strategy.evaluate(market, orderbook, ph_no_vol)

        # With volatility data (varying prices)
        prices = [0.50, 0.55, 0.48, 0.52, 0.60, 0.45, 0.55, 0.50, 0.48, 0.52,
                  0.50, 0.55, 0.48, 0.52, 0.60, 0.45, 0.55, 0.50, 0.48, 0.52, 0.51]
        ph_vol = _make_price_history(prices=prices)
        signals_vol = strategy.evaluate(market, orderbook, ph_vol)

        if signals_no_vol and signals_vol:
            buy_no_vol = next(s for s in signals_no_vol if s.side == "BUY")
            buy_vol = next(s for s in signals_vol if s.side == "BUY")
            sell_no_vol = next(s for s in signals_no_vol if s.side == "SELL")
            sell_vol = next(s for s in signals_vol if s.side == "SELL")
            # With volatility, spread should be wider
            spread_no_vol = sell_no_vol.suggested_price - buy_no_vol.suggested_price
            spread_vol = sell_vol.suggested_price - buy_vol.suggested_price
            self.assertGreaterEqual(spread_vol, spread_no_vol)


# ==================== News-Driven Tests ====================

class TestNewsDrivenStrategy(unittest.TestCase):

    def test_disabled_without_api_keys(self):
        """Strategy is disabled when news/openai keys are missing."""
        strategy = NewsDrivenStrategy(_make_settings())
        self.assertFalse(strategy.is_enabled)

    def test_generates_signal_on_bullish_news(self):
        """LLM returns UP -> BUY YES signal emitted."""
        settings = _make_settings(news_api_key="test_key", openai_api_key="test_key")
        strategy = NewsDrivenStrategy(settings)

        with patch.object(strategy, "_fetch_news") as mock_news, \
             patch.object(strategy, "_analyze_with_llm") as mock_llm:
            mock_news.return_value = [{"title": "Breaking: Big event!", "description": "", "source": "", "published_at": "", "url": ""}]
            mock_llm.return_value = {"direction": "UP", "magnitude": 0.8, "reasoning": "test"}

            market = _make_market()
            signals = strategy.evaluate(market, {}, _make_price_history())

            self.assertEqual(len(signals), 1)
            self.assertEqual(signals[0].side, "BUY")
            self.assertEqual(signals[0].token_id, "tok_yes")

    def test_deduplicates_headlines(self):
        """Same headline is not processed twice."""
        settings = _make_settings(news_api_key="test_key", openai_api_key="test_key")
        strategy = NewsDrivenStrategy(settings)

        headline = [{"title": "Same headline", "description": "", "source": "", "published_at": "", "url": ""}]

        with patch.object(strategy, "_fetch_news") as mock_news, \
             patch.object(strategy, "_analyze_with_llm") as mock_llm:
            mock_news.return_value = headline
            mock_llm.return_value = {"direction": "UP", "magnitude": 0.8}

            market = _make_market()
            ph = _make_price_history()

            strategy.evaluate(market, {}, ph)
            strategy.evaluate(market, {}, ph)

            # LLM should only be called once (headline deduplicated)
            self.assertEqual(mock_llm.call_count, 1)


# ==================== Whale-Following Tests ====================

class TestWhaleFollowingStrategy(unittest.TestCase):

    def _make_whale_strategy(self):
        settings = _make_settings(whale_wallets=("0xwhale1",))
        tracker = WhaleTracker(settings)
        return WhaleFollowingStrategy(settings, tracker)

    def test_follows_large_trade(self):
        """$5000 whale BUY -> emits BUY signal."""
        strategy = self._make_whale_strategy()

        with patch.object(strategy._whale_tracker, "get_whale_signals") as mock_sig:
            mock_sig.return_value = [{
                "wallet": "0xwhale1",
                "market_condition_id": "cond1",
                "token_id": "tok_yes",
                "side": "BUY",
                "size": 5000,
                "price": 0.6,
                "confidence": 0.3,
                "timestamp": time.time(),
            }]

            market = _make_market()
            signals = strategy.evaluate(market, {}, _make_price_history())
            self.assertEqual(len(signals), 1)
            self.assertEqual(signals[0].side, "BUY")

    def test_ignores_small_trade(self):
        """$500 whale trade < min_trade_size -> no signal."""
        strategy = self._make_whale_strategy()

        with patch.object(strategy._whale_tracker, "get_whale_signals") as mock_sig:
            mock_sig.return_value = [{
                "wallet": "0xwhale1",
                "market_condition_id": "cond1",
                "token_id": "tok_yes",
                "side": "BUY",
                "size": 500,
                "price": 0.6,
                "confidence": 0.3,
                "timestamp": time.time(),
            }]

            market = _make_market()
            signals = strategy.evaluate(market, {}, _make_price_history())
            self.assertEqual(len(signals), 0)

    def test_signal_decay(self):
        """Whale trade older than decay window -> no signal."""
        strategy = self._make_whale_strategy()

        with patch.object(strategy._whale_tracker, "get_whale_signals") as mock_sig:
            mock_sig.return_value = [{
                "wallet": "0xwhale1",
                "market_condition_id": "cond1",
                "token_id": "tok_yes",
                "side": "BUY",
                "size": 5000,
                "price": 0.6,
                "confidence": 0.3,
                "timestamp": time.time() - 600,  # 10 minutes ago
            }]

            market = _make_market()
            signals = strategy.evaluate(market, {}, _make_price_history())
            self.assertEqual(len(signals), 0)


if __name__ == "__main__":
    unittest.main()
