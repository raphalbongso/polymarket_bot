"""Tests for risk.kelly and risk.risk_manager modules."""
import unittest

from config.settings import Settings
from risk.kelly import kelly_criterion, position_size
from risk.risk_manager import RiskManager
from strategies.base import Signal


def _make_signal(**overrides):
    defaults = {
        "strategy_name": "test",
        "market_condition_id": "cond1",
        "token_id": "tok1",
        "side": "BUY",
        "confidence": 0.6,
        "raw_edge": 0.05,
        "suggested_price": 0.50,
        "max_size": 50.0,
    }
    defaults.update(overrides)
    return Signal(**defaults)


# ==================== Kelly Criterion Tests ====================

class TestKellyCriterion(unittest.TestCase):

    def test_kelly_criterion_formula(self):
        """f* = (bp - q) / b for known inputs."""
        # p=0.6, b=1.0 (even odds): f* = (1*0.6 - 0.4)/1 = 0.2
        result = kelly_criterion(0.6, 1.0)
        self.assertAlmostEqual(result, 0.2)

    def test_no_bet_when_negative_edge(self):
        """Returns <= 0 when win_prob < breakeven."""
        # p=0.3, b=1.0: f* = (1*0.3 - 0.7)/1 = -0.4
        result = kelly_criterion(0.3, 1.0)
        self.assertLess(result, 0)

    def test_kelly_with_better_odds(self):
        """Higher odds with same probability give larger Kelly fraction."""
        f1 = kelly_criterion(0.5, 2.0)  # b=2, p=0.5: (2*0.5-0.5)/2 = 0.25
        f2 = kelly_criterion(0.5, 1.0)  # b=1, p=0.5: (1*0.5-0.5)/1 = 0.0
        self.assertGreater(f1, f2)

    def test_position_size_with_fractional_kelly(self):
        """Quarter Kelly reduces position proportionally."""
        # p=0.6, b=1.0, full kelly=0.2, quarter=0.05
        size = position_size(
            bankroll=1000, win_prob=0.6, odds=1.0,
            kelly_fraction=0.25, max_kelly=0.5, max_position_usd=100.0
        )
        self.assertAlmostEqual(size, 50.0)  # 1000 * 0.2 * 0.25 = 50

    def test_position_size_capped(self):
        """Never exceeds max_position_size_usd."""
        size = position_size(
            bankroll=100000, win_prob=0.8, odds=2.0,
            kelly_fraction=0.25, max_kelly=0.5, max_position_usd=50.0
        )
        self.assertLessEqual(size, 50.0)


# ==================== Risk Manager Tests ====================

class TestRiskManager(unittest.TestCase):

    def _make_manager(self, **overrides):
        settings = Settings(**overrides)
        rm = RiskManager(settings)
        rm.set_balance(1000.0)
        return rm

    def test_kill_switch_one_way(self):
        """Once triggered, is_killed stays True forever."""
        rm = self._make_manager()
        self.assertFalse(rm.is_killed)
        rm.trigger_kill_switch("test")
        self.assertTrue(rm.is_killed)
        # Cannot be unset
        self.assertTrue(rm.is_killed)

    def test_drawdown_triggers_kill(self):
        """Drawdown exceeding max_drawdown_pct triggers kill switch."""
        rm = self._make_manager(max_drawdown_pct=0.10)
        rm.set_balance(1000.0)  # peak = 1000
        rm._current_balance = 850.0  # 15% drawdown

        result = rm.check_drawdown()
        self.assertFalse(result)
        self.assertTrue(rm.is_killed)

    def test_daily_loss_triggers_kill(self):
        """Daily loss exceeding limit triggers kill switch."""
        rm = self._make_manager(daily_loss_limit_usd=100.0)
        rm._daily_pnl = -150.0

        result = rm.check_daily_loss()
        self.assertFalse(result)
        self.assertTrue(rm.is_killed)

    def test_consecutive_losses_trigger_kill(self):
        """Exceeding max consecutive losses triggers kill switch."""
        rm = self._make_manager(max_consecutive_losses=5)
        rm._consecutive_losses = 6

        result = rm.check_consecutive_losses()
        self.assertFalse(result)
        self.assertTrue(rm.is_killed)

    def test_pre_trade_check_blocks_after_kill(self):
        """pre_trade_check returns False after kill switch is set."""
        rm = self._make_manager()
        signal = _make_signal()

        self.assertTrue(rm.pre_trade_check(signal))

        rm.trigger_kill_switch("test")
        self.assertFalse(rm.pre_trade_check(signal))

    def test_record_trade_updates_counters(self):
        """record_trade updates PnL and consecutive loss counters."""
        rm = self._make_manager()

        rm.record_trade({"pnl": -10.0, "side": "BUY", "size": 50, "price": 0.5})
        self.assertEqual(rm._consecutive_losses, 1)
        self.assertAlmostEqual(rm._daily_pnl, -10.0)

        rm.record_trade({"pnl": 20.0, "side": "SELL", "size": 50, "price": 0.6})
        self.assertEqual(rm._consecutive_losses, 0)  # Reset on win
        self.assertAlmostEqual(rm._daily_pnl, 10.0)

    def test_reset_daily_preserves_kill(self):
        """reset_daily resets counters but NOT the kill switch."""
        rm = self._make_manager()
        rm._daily_pnl = -50.0
        rm._consecutive_losses = 3
        rm.trigger_kill_switch("test")

        rm.reset_daily()
        self.assertAlmostEqual(rm._daily_pnl, 0.0)
        self.assertEqual(rm._consecutive_losses, 0)
        self.assertTrue(rm.is_killed)  # Kill switch NOT reset

    def test_risk_report(self):
        """get_risk_report returns correct state dict."""
        rm = self._make_manager()
        report = rm.get_risk_report()

        self.assertIn("is_killed", report)
        self.assertIn("current_balance", report)
        self.assertIn("daily_pnl", report)
        self.assertFalse(report["is_killed"])


if __name__ == "__main__":
    unittest.main()
