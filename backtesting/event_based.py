"""Event-based backtester — bar-by-bar simulation for realistic results."""
import numpy as np
import pandas as pd


class EventBasedBacktester:
    """Simulate trading bar-by-bar with explicit cost modeling."""

    def __init__(
        self,
        prices: pd.Series,
        initial_capital: float = 1000.0,
        fixed_cost: float = 0.007,
        prop_cost: float = 0.001,
    ):
        self._prices = prices.copy()
        self._initial_capital = initial_capital
        self._fixed_cost = fixed_cost
        self._prop_cost = prop_cost

    def run(self, signals: pd.Series) -> pd.DataFrame:
        """Run the backtest with given signals (-1, 0, +1).

        Returns DataFrame with columns: price, signal, position, equity.
        """
        prices = self._prices.values
        sigs = signals.reindex(self._prices.index).fillna(0).astype(int).values
        n = len(prices)

        equity = np.zeros(n)
        positions = np.zeros(n)
        cash = self._initial_capital
        holdings = 0.0  # number of units held
        current_pos = 0

        for i in range(n):
            price = prices[i]
            target_pos = sigs[i]

            # Execute trade if position changes
            if target_pos != current_pos:
                # Close current position
                if current_pos != 0:
                    cash += holdings * price
                    trade_value = abs(holdings * price)
                    cash -= self._fixed_cost + trade_value * self._prop_cost
                    holdings = 0.0

                # Open new position
                if target_pos != 0:
                    trade_value = cash * 0.95  # keep 5% reserve
                    if trade_value > 0:
                        cost = self._fixed_cost + trade_value * self._prop_cost
                        invest = trade_value - cost
                        units = invest / price
                        holdings = units * target_pos
                        if target_pos > 0:
                            cash -= invest      # long: spend cash to buy
                        else:
                            cash += invest      # short: receive cash from selling

                current_pos = target_pos

            # Mark to market
            positions[i] = current_pos
            equity[i] = cash + holdings * price

        return pd.DataFrame({
            "price": prices,
            "signal": sigs,
            "position": positions,
            "equity": equity,
        }, index=self._prices.index)

    def summary(self, result: pd.DataFrame) -> dict:
        equity = result["equity"]
        final = round(equity.iloc[-1], 2)
        total_return = round((final / self._initial_capital - 1) * 100, 2)

        # Trade count
        n_trades = int(result["position"].diff().fillna(0).abs().gt(0).sum())

        # Max drawdown
        peak = equity.cummax()
        drawdown = (equity - peak) / peak
        max_dd = round(drawdown.min() * 100, 2)

        return {
            "initial_capital": self._initial_capital,
            "final_equity": final,
            "total_return_pct": total_return,
            "n_trades": n_trades,
            "max_drawdown_pct": max_dd,
        }
