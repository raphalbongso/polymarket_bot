"""Monitor large wallets for position changes via Polymarket Data API."""
import time
from collections import deque, OrderedDict

import requests

from config.settings import Settings
from monitoring.logger import get_logger

logger = get_logger("whale_tracker")


class WhaleTracker:
    """Track whale wallet activity and generate follow signals."""

    def __init__(self, settings: Settings):
        self._wallets = list(settings.whale_wallets)
        self._data_api_url = settings.data_api_url
        self._session = requests.Session()
        self._recent_trades = {}  # wallet -> deque of trades
        self._maxlen = settings.trade_history_maxlen
        self._seen_ids = OrderedDict()
        self._min_trade_size = 1000.0

    def fetch_wallet_activity(self, wallet):
        """Fetch recent trades for a wallet from the Data API."""
        try:
            resp = self._session.get(
                f"{self._data_api_url}/activity",
                params={"user": wallet, "limit": 50},
                timeout=15,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.warning(f"Failed to fetch activity for {wallet[:10]}...: {e}")
            return []

    def check_all_wallets(self):
        """Poll all whale wallets. Return NEW trades not seen before."""
        new_trades = []
        for wallet in self._wallets:
            if wallet not in self._recent_trades:
                self._recent_trades[wallet] = deque(maxlen=self._maxlen)

            trades = self.fetch_wallet_activity(wallet)
            for trade in trades:
                trade_id = trade.get("id") or trade.get("transactionHash", "")
                if trade_id and trade_id not in self._seen_ids:
                    self._seen_ids[trade_id] = None
                    trade["_wallet"] = wallet
                    trade["_fetched_at"] = time.time()
                    self._recent_trades[wallet].append(trade)
                    new_trades.append(trade)

        # Bound the seen dict (preserves insertion order)
        if len(self._seen_ids) > self._maxlen * 2:
            keys = list(self._seen_ids.keys())
            for k in keys[:-self._maxlen]:
                del self._seen_ids[k]

        return new_trades

    def get_whale_signals(self):
        """Analyze recent whale trades and return actionable signals."""
        signals = []
        now = time.time()

        for wallet, trades in self._recent_trades.items():
            for trade in trades:
                age = now - trade.get("_fetched_at", now)
                if age > 300:  # Older than 5 minutes
                    continue

                size = float(trade.get("size", 0))
                if size < self._min_trade_size:
                    continue

                confidence = min(0.6, size / 10000.0)

                signals.append({
                    "wallet": wallet,
                    "market_condition_id": trade.get("conditionId", ""),
                    "token_id": trade.get("tokenId", ""),
                    "side": trade.get("side", "BUY"),
                    "size": size,
                    "price": float(trade.get("price", 0)),
                    "confidence": confidence,
                    "timestamp": trade.get("_fetched_at", now),
                })

        return signals

    def add_wallet(self, wallet):
        """Add a wallet to track."""
        if wallet not in self._wallets:
            self._wallets.append(wallet)
            self._recent_trades[wallet] = deque(maxlen=self._maxlen)

    def remove_wallet(self, wallet):
        """Stop tracking a wallet."""
        if wallet in self._wallets:
            self._wallets.remove(wallet)
            self._recent_trades.pop(wallet, None)
