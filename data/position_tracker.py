"""Track live positions from Polymarket Data API."""
import time

import requests

from config.settings import Settings
from monitoring.logger import get_logger

logger = get_logger("position_tracker")


class PositionTracker:
    """Fetch and cache live positions from the Polymarket Data API."""

    def __init__(self, settings: Settings):
        self._data_api_url = settings.data_api_url
        self._wallet = settings.funder_address or ""
        self._session = requests.Session()
        self._positions = []
        self._last_fetch = 0.0
        self._cache_ttl = 30.0

    def fetch_positions(self) -> list:
        """Fetch current positions from Data API."""
        if not self._wallet:
            return []

        now = time.time()
        if self._positions and (now - self._last_fetch) < self._cache_ttl:
            return self._positions

        try:
            resp = self._session.get(
                f"{self._data_api_url}/positions",
                params={"user": self._wallet},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            self._positions = data if isinstance(data, list) else []
            self._last_fetch = now
            return self._positions
        except Exception as e:
            logger.warning(f"Failed to fetch positions: {e}")
            return self._positions

    def get_position_for_token(self, token_id: str):
        """Return position data for a specific token, or None."""
        for pos in self._positions:
            asset = pos.get("asset", "") or pos.get("tokenId", "")
            if asset == token_id:
                return pos
        return None

    def get_net_exposure(self) -> float:
        """Return total USD exposure across all positions."""
        total = 0.0
        for pos in self._positions:
            size = float(pos.get("size", 0))
            price = float(pos.get("avgPrice", 0) or pos.get("price", 0))
            total += abs(size * price)
        return total

    def get_summary(self) -> dict:
        """Return summary for heartbeat/monitoring."""
        return {
            "position_count": len(self._positions),
            "net_exposure_usd": round(self.get_net_exposure(), 2),
            "last_fetch": self._last_fetch,
            "positions": [
                {
                    "token": (p.get("asset") or p.get("tokenId", ""))[:16] + "...",
                    "size": float(p.get("size", 0)),
                    "avg_price": float(p.get("avgPrice", 0) or p.get("price", 0)),
                }
                for p in self._positions
            ],
        }
