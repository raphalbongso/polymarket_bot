"""Fetch active markets from the Polymarket Gamma API."""
import json
import time

import requests

from config.settings import Settings
from monitoring.logger import get_logger

logger = get_logger("market_fetcher")


class MarketFetcher:
    """Fetch and cache active Polymarket binary markets."""

    def __init__(self, settings: Settings):
        self._gamma_url = settings.gamma_url
        self._session = requests.Session()
        self._markets_cache = []
        self._last_fetch = 0.0
        self._cache_ttl = 300.0  # 5 minutes

    def get_active_markets(self):
        """Return list of active binary markets.

        Each market dict contains:
        - condition_id, question, tokens, outcome_prices, volume, slug
        """
        now = time.time()
        if self._markets_cache and (now - self._last_fetch) < self._cache_ttl:
            return self._markets_cache

        try:
            resp = self._session.get(
                f"{self._gamma_url}/markets",
                params={"active": "true", "closed": "false", "limit": 100},
                timeout=15,
            )
            resp.raise_for_status()
            raw_markets = resp.json()

            markets = []
            for m in raw_markets:
                tokens_raw = m.get("clobTokenIds", "[]")
                if isinstance(tokens_raw, str):
                    tokens_raw = json.loads(tokens_raw)

                prices_raw = m.get("outcomePrices", "[]")
                if isinstance(prices_raw, str):
                    prices_raw = json.loads(prices_raw)

                # Only include binary markets (exactly 2 tokens)
                if len(tokens_raw) != 2:
                    continue

                markets.append({
                    "condition_id": m.get("conditionId", ""),
                    "question": m.get("question", ""),
                    "tokens": tokens_raw,
                    "outcome_prices": [float(p) for p in prices_raw] if prices_raw else [0.5, 0.5],
                    "volume": float(m.get("volume", 0)),
                    "liquidity": float(m.get("liquidity", 0)),
                    "slug": m.get("slug", ""),
                })

            self._markets_cache = markets
            self._last_fetch = now
            logger.info(f"Fetched {len(markets)} active markets")
            return markets

        except Exception as e:
            logger.warning(f"Failed to fetch markets: {e}")
            return self._markets_cache  # Return stale cache on error

    def get_market_by_condition_id(self, condition_id):
        """Lookup a single market by condition_id."""
        for m in self.get_active_markets():
            if m["condition_id"] == condition_id:
                return m
        return None

    def get_token_ids_for_market(self, condition_id):
        """Return (yes_token_id, no_token_id) for a binary market."""
        market = self.get_market_by_condition_id(condition_id)
        if market and len(market["tokens"]) == 2:
            return market["tokens"][0], market["tokens"][1]
        return None, None

    def refresh(self):
        """Force cache refresh on next call."""
        self._last_fetch = 0.0
