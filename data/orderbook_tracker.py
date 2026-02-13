"""Track orderbook state for Polymarket markets."""
import time
from collections import deque

from config.settings import Settings
from monitoring.logger import get_logger

logger = get_logger("orderbook_tracker")


class OrderbookTracker:
    """Maintain local orderbook snapshots with bounded history."""

    def __init__(self, clob_client, settings: Settings):
        self._client = clob_client
        self._books = {}  # token_id -> deque of snapshots
        self._maxlen = settings.orderbook_history_maxlen

    def fetch_orderbook(self, token_id):
        """Fetch current orderbook for a token.

        Returns dict with 'bids' and 'asks' as lists of (price, size) tuples.
        """
        if token_id not in self._books:
            self._books[token_id] = deque(maxlen=self._maxlen)

        try:
            if self._client is None:
                return {"bids": [], "asks": [], "timestamp": time.time()}

            raw = self._client.get_order_book(token_id)

            # Handle both dict responses and typed OrderBookSummary objects
            raw_bids = raw.get("bids", []) if isinstance(raw, dict) else getattr(raw, "bids", [])
            raw_asks = raw.get("asks", []) if isinstance(raw, dict) else getattr(raw, "asks", [])

            def _parse_level(o):
                if isinstance(o, dict):
                    return (float(o.get("price", 0)), float(o.get("size", 0)))
                return (float(getattr(o, "price", 0)), float(getattr(o, "size", 0)))

            bids = [_parse_level(o) for o in raw_bids]
            asks = [_parse_level(o) for o in raw_asks]

            # Sort: bids descending, asks ascending
            bids.sort(key=lambda x: x[0], reverse=True)
            asks.sort(key=lambda x: x[0])

            snapshot = {
                "bids": bids,
                "asks": asks,
                "timestamp": time.time(),
            }
            self._books[token_id].append(snapshot)
            return snapshot

        except Exception as e:
            logger.warning(f"Failed to fetch orderbook for {token_id[:8]}...: {e}")
            return {"bids": [], "asks": [], "timestamp": time.time()}

    def get_best_bid(self, token_id):
        """Return highest bid price, or None if empty."""
        if token_id in self._books and self._books[token_id]:
            bids = self._books[token_id][-1]["bids"]
            return bids[0][0] if bids else None
        return None

    def get_best_ask(self, token_id):
        """Return lowest ask price, or None if empty."""
        if token_id in self._books and self._books[token_id]:
            asks = self._books[token_id][-1]["asks"]
            return asks[0][0] if asks else None
        return None

    def get_spread(self, token_id):
        """Return best_ask - best_bid, or None."""
        bid = self.get_best_bid(token_id)
        ask = self.get_best_ask(token_id)
        if bid is not None and ask is not None:
            return ask - bid
        return None

    def get_midpoint(self, token_id):
        """Return (best_bid + best_ask) / 2, or None."""
        bid = self.get_best_bid(token_id)
        ask = self.get_best_ask(token_id)
        if bid is not None and ask is not None:
            return (bid + ask) / 2
        return None

    def get_history(self, token_id):
        """Return the deque of historical snapshots."""
        return self._books.get(token_id, deque())
