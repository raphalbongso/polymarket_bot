"""Tests for bot.paper_trader module."""
import time
import unittest

from bot.paper_trader import PaperTrader, PaperOrder
from strategies.base import Signal


def _make_signal(token_id="tok1", side="BUY", price=0.50, confidence=0.6):
    return Signal(
        strategy_name="test",
        market_condition_id="cond1",
        token_id=token_id,
        side=side,
        confidence=confidence,
        raw_edge=0.05,
        suggested_price=price,
        max_size=50.0,
    )


def _make_orderbook(bids=None, asks=None):
    return {
        "bids": bids or [],
        "asks": asks or [],
        "timestamp": time.time(),
    }


class TestPaperTrader(unittest.TestCase):

    def test_buy_at_ask_fills_immediately(self):
        """A BUY at or above the best ask fills immediately."""
        pt = PaperTrader(balance=1000.0, slippage_bps=0)
        ob = _make_orderbook(asks=[(0.50, 100.0)])
        signal = _make_signal(side="BUY", price=0.50)
        fill = pt.execute(signal, size_usd=25.0, orderbook=ob)

        self.assertEqual(fill.status, "filled")
        self.assertGreater(fill.filled_qty, 0)
        self.assertAlmostEqual(fill.avg_fill_price, 0.50, places=4)

    def test_sell_at_bid_fills_immediately(self):
        """A SELL at or below the best bid fills immediately (with existing position)."""
        pt = PaperTrader(balance=1000.0, slippage_bps=0)
        # First buy to create a position
        ob = _make_orderbook(asks=[(0.50, 200.0)])
        pt.execute(_make_signal(side="BUY", price=0.50), size_usd=50.0, orderbook=ob)

        # Now sell at bid
        ob_sell = _make_orderbook(bids=[(0.55, 200.0)])
        signal = _make_signal(side="SELL", price=0.55)
        fill = pt.execute(signal, size_usd=50.0, orderbook=ob_sell)

        self.assertEqual(fill.status, "filled")
        self.assertGreater(fill.filled_qty, 0)

    def test_buy_below_ask_creates_resting_order(self):
        """A BUY below the best ask creates a resting order."""
        pt = PaperTrader(balance=1000.0, slippage_bps=0)
        ob = _make_orderbook(asks=[(0.60, 100.0)])  # Ask at 0.60
        signal = _make_signal(side="BUY", price=0.50)  # Bid at 0.50
        fill = pt.execute(signal, size_usd=25.0, orderbook=ob)

        self.assertEqual(fill.status, "resting")
        self.assertEqual(fill.filled_qty, 0)
        self.assertEqual(len(pt.resting_orders), 1)

    def test_resting_order_fills_when_market_moves(self):
        """A resting BUY order fills when asks move down to its price."""
        pt = PaperTrader(balance=1000.0, slippage_bps=0)
        ob1 = _make_orderbook(asks=[(0.60, 100.0)])  # Ask too high
        signal = _make_signal(side="BUY", price=0.50)
        pt.execute(signal, size_usd=25.0, orderbook=ob1)
        self.assertEqual(len(pt.resting_orders), 1)

        # Market moves down — asks now at 0.50
        ob2 = _make_orderbook(asks=[(0.50, 100.0)])
        fills = pt.check_resting_orders({"tok1": ob2})

        self.assertEqual(len(fills), 1)
        self.assertGreater(fills[0].filled_qty, 0)
        self.assertEqual(len(pt.resting_orders), 0)

    def test_buy_creates_position(self):
        """A filled BUY creates a position with correct entry."""
        pt = PaperTrader(balance=1000.0, slippage_bps=0)
        ob = _make_orderbook(asks=[(0.50, 200.0)])
        pt.execute(_make_signal(side="BUY", price=0.50), size_usd=50.0, orderbook=ob)

        positions = pt.positions
        self.assertIn("tok1", positions)
        self.assertAlmostEqual(positions["tok1"].quantity, 100.0, places=2)
        self.assertAlmostEqual(positions["tok1"].avg_entry_price, 0.50, places=4)

    def test_sell_reduces_position(self):
        """A filled SELL reduces position quantity."""
        pt = PaperTrader(balance=1000.0, slippage_bps=0)
        ob = _make_orderbook(asks=[(0.50, 200.0)])
        pt.execute(_make_signal(side="BUY", price=0.50), size_usd=50.0, orderbook=ob)

        ob_sell = _make_orderbook(bids=[(0.50, 200.0)])
        pt.execute(_make_signal(side="SELL", price=0.50), size_usd=25.0, orderbook=ob_sell)

        positions = pt.positions
        self.assertAlmostEqual(positions["tok1"].quantity, 50.0, places=2)

    def test_realized_pnl_on_profitable_sell(self):
        """Selling at a higher price yields positive realized PnL."""
        pt = PaperTrader(balance=1000.0, slippage_bps=0)
        ob_buy = _make_orderbook(asks=[(0.50, 200.0)])
        pt.execute(_make_signal(side="BUY", price=0.50), size_usd=50.0, orderbook=ob_buy)

        ob_sell = _make_orderbook(bids=[(0.60, 200.0)])
        fill = pt.execute(_make_signal(side="SELL", price=0.60), size_usd=60.0, orderbook=ob_sell)

        self.assertGreater(fill.realized_pnl, 0)
        self.assertAlmostEqual(fill.realized_pnl, 100.0 * 0.10, places=2)  # 100 qty * $0.10 profit

    def test_realized_pnl_on_losing_sell(self):
        """Selling at a lower price yields negative realized PnL."""
        pt = PaperTrader(balance=1000.0, slippage_bps=0)
        ob_buy = _make_orderbook(asks=[(0.50, 200.0)])
        pt.execute(_make_signal(side="BUY", price=0.50), size_usd=50.0, orderbook=ob_buy)

        ob_sell = _make_orderbook(bids=[(0.40, 200.0)])
        fill = pt.execute(_make_signal(side="SELL", price=0.40), size_usd=40.0, orderbook=ob_sell)

        self.assertLess(fill.realized_pnl, 0)

    def test_balance_decreases_on_buy(self):
        """Balance should decrease by the cost of a BUY fill."""
        pt = PaperTrader(balance=1000.0, slippage_bps=0)
        ob = _make_orderbook(asks=[(0.50, 200.0)])
        pt.execute(_make_signal(side="BUY", price=0.50), size_usd=50.0, orderbook=ob)

        self.assertAlmostEqual(pt.balance, 950.0, places=2)

    def test_balance_increases_on_sell(self):
        """Balance should increase by the proceeds of a SELL fill."""
        pt = PaperTrader(balance=1000.0, slippage_bps=0)
        ob_buy = _make_orderbook(asks=[(0.50, 200.0)])
        pt.execute(_make_signal(side="BUY", price=0.50), size_usd=50.0, orderbook=ob_buy)
        # balance is now 950

        ob_sell = _make_orderbook(bids=[(0.60, 200.0)])
        pt.execute(_make_signal(side="SELL", price=0.60), size_usd=60.0, orderbook=ob_sell)
        # Sold 100 qty at 0.60 = $60 credited
        self.assertAlmostEqual(pt.balance, 1010.0, places=2)

    def test_expired_orders_are_removed(self):
        """Resting orders past TTL are expired and removed."""
        pt = PaperTrader(balance=1000.0, slippage_bps=0, order_ttl=0.0)  # 0s TTL
        ob = _make_orderbook(asks=[(0.60, 100.0)])
        pt.execute(_make_signal(side="BUY", price=0.50), size_usd=25.0, orderbook=ob)
        self.assertEqual(len(pt.resting_orders), 1)

        # Check after TTL has passed
        time.sleep(0.01)
        pt.check_resting_orders({"tok1": ob})
        self.assertEqual(len(pt.resting_orders), 0)

    def test_large_order_partially_fills(self):
        """An order larger than available liquidity partially fills."""
        pt = PaperTrader(balance=10000.0, slippage_bps=0)
        ob = _make_orderbook(asks=[(0.50, 10.0)])  # Only 10 shares available
        signal = _make_signal(side="BUY", price=0.50)
        fill = pt.execute(signal, size_usd=500.0, orderbook=ob)  # Wants 1000 shares

        self.assertEqual(fill.status, "partial")
        self.assertAlmostEqual(fill.filled_qty, 10.0, places=2)
        # The rest should be resting
        self.assertEqual(len(pt.resting_orders), 1)

    def test_buy_slippage_increases_fill_price(self):
        """Slippage on a BUY should increase the average fill price."""
        pt_no_slip = PaperTrader(balance=1000.0, slippage_bps=0)
        pt_with_slip = PaperTrader(balance=1000.0, slippage_bps=50.0)  # 50bps

        ob = _make_orderbook(asks=[(0.50, 200.0)])
        signal = _make_signal(side="BUY", price=0.50)

        fill_no = pt_no_slip.execute(signal, size_usd=50.0, orderbook=ob)
        fill_yes = pt_with_slip.execute(signal, size_usd=50.0, orderbook=ob)

        self.assertGreater(fill_yes.avg_fill_price, fill_no.avg_fill_price)

    def test_sell_slippage_decreases_fill_price(self):
        """Slippage on a SELL should decrease the average fill price."""
        for slippage in [0, 50.0]:
            pt = PaperTrader(balance=1000.0, slippage_bps=slippage)
            ob_buy = _make_orderbook(asks=[(0.50, 200.0)])
            pt.execute(_make_signal(side="BUY", price=0.50), size_usd=50.0, orderbook=ob_buy)

        # Now test sell with and without slippage
        pt_no = PaperTrader(balance=1000.0, slippage_bps=0)
        pt_yes = PaperTrader(balance=1000.0, slippage_bps=50.0)
        for pt in [pt_no, pt_yes]:
            ob_buy = _make_orderbook(asks=[(0.50, 200.0)])
            pt.execute(_make_signal(side="BUY", price=0.50), size_usd=50.0, orderbook=ob_buy)

        ob_sell = _make_orderbook(bids=[(0.55, 200.0)])
        fill_no = pt_no.execute(_make_signal(side="SELL", price=0.55), size_usd=55.0, orderbook=ob_sell)
        fill_yes = pt_yes.execute(_make_signal(side="SELL", price=0.55), size_usd=55.0, orderbook=ob_sell)

        self.assertLess(fill_yes.avg_fill_price, fill_no.avg_fill_price)


if __name__ == "__main__":
    unittest.main()
