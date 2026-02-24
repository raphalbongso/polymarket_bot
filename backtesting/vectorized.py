"""Vectorized backtester — fast strategy evaluation using numpy/pandas."""
import numpy as np
import pandas as pd


class VectorizedBacktester:
    """Evaluate strategies on historical price data without loops."""

    def __init__(self, prices: pd.Series, tc: float = 0.001, capital: float = 1000.0):
        self._prices = prices.copy()
        self._tc = tc
        self._capital = capital
        self._returns = prices.pct_change().fillna(0)
        self._position = None
        self._strategy_returns = None

    def run_momentum(self, window: int = 20):
        """Long when recent returns are positive, flat/short otherwise."""
        momentum = self._returns.rolling(window).mean()
        self._position = np.sign(momentum).fillna(0)
        self._apply_strategy()

    def run_sma_crossover(self, short: int = 10, long: int = 30):
        """Long when short SMA > long SMA, short otherwise."""
        sma_short = self._prices.rolling(short).mean()
        sma_long = self._prices.rolling(long).mean()
        self._position = pd.Series(
            np.where(sma_short > sma_long, 1, -1),
            index=self._prices.index,
        )
        # No position until both SMAs have values
        self._position.iloc[:long] = 0
        self._apply_strategy()

    def optimize_momentum(self, windows: list):
        """Try multiple momentum windows and return the best."""
        best_window = None
        best_result = None
        best_return = -np.inf

        for w in windows:
            self.run_momentum(window=w)
            result = self.summary()
            if result["total_return_strategy"] > best_return:
                best_return = result["total_return_strategy"]
                best_window = w
                best_result = result

        # Restore best
        self.run_momentum(window=best_window)
        return best_window, best_result

    def _apply_strategy(self):
        """Compute strategy returns accounting for transaction costs."""
        trades = self._position.diff().fillna(0).abs()
        costs = trades * self._tc
        self._strategy_returns = self._position.shift(1).fillna(0) * self._returns - costs

    def summary(self) -> dict:
        if self._strategy_returns is None:
            return {}

        equity = self._capital * (1 + self._strategy_returns).cumprod()
        final = round(equity.iloc[-1], 2)
        total_return = round((final / self._capital) - 1, 4)

        # Sharpe ratio (annualized for hourly data)
        mean_r = self._strategy_returns.mean()
        std_r = self._strategy_returns.std()
        sharpe = round(mean_r / std_r * np.sqrt(8760), 2) if std_r > 0 else 0.0

        # Max drawdown
        peak = equity.cummax()
        drawdown = (equity - peak) / peak
        max_dd = round(drawdown.min() * 100, 2)

        # Trade count
        n_trades = int(self._position.diff().fillna(0).abs().gt(0).sum())

        return {
            "final_equity": final,
            "total_return_strategy": total_return,
            "sharpe_ratio": sharpe,
            "max_drawdown_pct": max_dd,
            "n_trades": n_trades,
        }
