"""Central risk manager with kill switch and three kill triggers."""
import threading
import time
from collections import deque

from config.settings import Settings
from monitoring.logger import get_logger
from risk.kelly import position_size

logger = get_logger("risk_manager")


class RiskManager:
    """Manages risk with a one-way kill switch and three kill triggers."""

    def __init__(self, settings: Settings):
        self._settings = settings
        self._kill_switch = threading.Event()

        self._starting_balance = 0.0
        self._peak_balance = 0.0
        self._current_balance = 0.0
        self._daily_pnl = 0.0
        self._consecutive_losses = 0
        self._trade_log = deque(maxlen=1000)

    # --- Kill Switch ---

    @property
    def is_killed(self):
        return self._kill_switch.is_set()

    def trigger_kill_switch(self, reason):
        """Set the kill switch. ONE-WAY: cannot be unset without restart."""
        self._kill_switch.set()
        logger.critical(f"KILL SWITCH ACTIVATED: {reason}")

    # --- Balance Management ---

    def set_balance(self, balance):
        """Initialize or update the current balance."""
        self._current_balance = balance
        if self._starting_balance == 0:
            self._starting_balance = balance
        if balance > self._peak_balance:
            self._peak_balance = balance

    # --- Kill Trigger Checks ---

    def check_drawdown(self):
        """Check if drawdown exceeds max_drawdown_pct. Returns True if safe."""
        if self._peak_balance <= 0:
            return True

        drawdown = (self._peak_balance - self._current_balance) / self._peak_balance
        if drawdown >= self._settings.max_drawdown_pct:
            self.trigger_kill_switch(
                f"Max drawdown exceeded: {drawdown:.1%} >= {self._settings.max_drawdown_pct:.1%}"
            )
            return False
        return True

    def check_daily_loss(self):
        """Check if daily loss exceeds daily_loss_limit_usd. Returns True if safe."""
        if abs(self._daily_pnl) > 0 and self._daily_pnl <= -self._settings.daily_loss_limit_usd:
            self.trigger_kill_switch(
                f"Daily loss limit exceeded: ${abs(self._daily_pnl):.2f} >= ${self._settings.daily_loss_limit_usd:.2f}"
            )
            return False
        return True

    def check_consecutive_losses(self):
        """Check if consecutive losses exceed limit. Returns True if safe."""
        if self._consecutive_losses >= self._settings.max_consecutive_losses:
            self.trigger_kill_switch(
                f"Consecutive loss limit: {self._consecutive_losses} >= {self._settings.max_consecutive_losses}"
            )
            return False
        return True

    def pre_trade_check(self, signal):
        """Run ALL checks. Return True only if all pass."""
        if self.is_killed:
            return False

        if not self.check_drawdown():
            return False
        if not self.check_daily_loss():
            return False
        if not self.check_consecutive_losses():
            return False

        # Validate position size
        if signal.max_size > self._settings.max_position_size_usd:
            return False

        return True

    # --- Post-Trade Updates ---

    def record_trade(self, trade_result):
        """Record a trade outcome and update counters.

        trade_result: {'pnl': float, 'side': str, 'size': float, 'price': float}
        """
        trade_result["timestamp"] = time.time()
        self._trade_log.append(trade_result)

        pnl = trade_result.get("pnl", 0.0)
        self._daily_pnl += pnl
        self._current_balance += pnl

        if self._current_balance > self._peak_balance:
            self._peak_balance = self._current_balance

        if pnl < 0:
            self._consecutive_losses += 1
        else:
            self._consecutive_losses = 0

        # Re-check triggers after trade
        self.check_drawdown()
        self.check_daily_loss()
        self.check_consecutive_losses()

    def calculate_position_size(self, signal):
        """Use Kelly criterion to size the position."""
        if not self.pre_trade_check(signal):
            return 0.0

        if signal.suggested_price <= 0 or signal.suggested_price >= 1:
            return 0.0

        odds = (1.0 / signal.suggested_price) - 1.0
        win_prob = signal.confidence

        size = position_size(
            bankroll=self._current_balance,
            win_prob=win_prob,
            odds=odds,
            kelly_fraction=self._settings.kelly_fraction,
            max_kelly=self._settings.max_kelly_fraction,
            max_position_usd=self._settings.max_position_size_usd,
        )

        return size

    def reset_daily(self):
        """Reset daily counters. Does NOT reset kill switch."""
        self._daily_pnl = 0.0
        self._consecutive_losses = 0

    def get_risk_report(self):
        """Return current risk state as a dict."""
        return {
            "is_killed": self.is_killed,
            "current_balance": self._current_balance,
            "peak_balance": self._peak_balance,
            "drawdown_pct": (
                (self._peak_balance - self._current_balance) / self._peak_balance
                if self._peak_balance > 0 else 0.0
            ),
            "daily_pnl": self._daily_pnl,
            "consecutive_losses": self._consecutive_losses,
            "total_trades": len(self._trade_log),
        }
