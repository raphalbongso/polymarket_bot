"""Track open orders on Polymarket CLOB and cancel stale ones."""
import time
from datetime import datetime, timezone

from monitoring.logger import get_logger

logger = get_logger("order_tracker")

try:
    from py_clob_client.clob_types import OpenOrderParams
    HAS_OPEN_ORDERS = True
except ImportError:
    HAS_OPEN_ORDERS = False


class OrderTracker:
    """Fetch open orders, track age, cancel stale ones."""

    def __init__(self, clob_client, stale_seconds: float = 300.0):
        self._client = clob_client
        self._stale_seconds = stale_seconds
        self._open_orders = []
        self._last_fetch = 0.0

    def fetch_open_orders(self) -> list:
        """Fetch all open orders from Polymarket CLOB."""
        if not HAS_OPEN_ORDERS or self._client is None:
            return []
        try:
            raw = self._client.get_orders(OpenOrderParams())
            self._open_orders = raw if isinstance(raw, list) else []
            self._last_fetch = time.time()
            return self._open_orders
        except Exception as e:
            logger.warning(f"Failed to fetch open orders: {e}")
            return self._open_orders

    def get_stale_orders(self) -> list:
        """Return orders older than stale_seconds."""
        now = time.time()
        stale = []
        for order in self._open_orders:
            created = order.get("createdAt") or order.get("timestamp", 0)
            if isinstance(created, str):
                try:
                    dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                    age = now - dt.timestamp()
                except (ValueError, TypeError):
                    age = 0
            else:
                age = now - float(created) if created else 0

            if age > self._stale_seconds:
                stale.append(order)
        return stale

    def cancel_order(self, order_id: str) -> bool:
        """Cancel a single order by ID."""
        if self._client is None:
            return False
        try:
            self._client.cancel(order_id)
            logger.info(f"Cancelled order {order_id}")
            return True
        except Exception as e:
            logger.warning(f"Failed to cancel order {order_id}: {e}")
            return False

    def cancel_stale_orders(self) -> int:
        """Cancel all stale orders. Returns number cancelled."""
        stale = self.get_stale_orders()
        cancelled = 0
        cancelled_ids = set()
        for order in stale:
            oid = order.get("id") or order.get("orderID", "")
            if oid and self.cancel_order(oid):
                cancelled += 1
                cancelled_ids.add(oid)
        if cancelled_ids:
            self._open_orders = [
                o for o in self._open_orders
                if (o.get("id") or o.get("orderID", "")) not in cancelled_ids
            ]
        return cancelled

    def get_summary(self) -> dict:
        """Return summary for heartbeat/monitoring."""
        return {
            "open_count": len(self._open_orders),
            "stale_count": len(self.get_stale_orders()),
            "last_fetch": self._last_fetch,
        }
