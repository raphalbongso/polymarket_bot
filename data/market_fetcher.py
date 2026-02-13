"""Fetch active markets from the Polymarket Gamma API."""
import json
import time
from datetime import datetime, timezone

import requests

from config.settings import Settings
from monitoring.logger import get_logger

logger = get_logger("market_fetcher")

# Interval in seconds for recurring time-based market slugs (e.g. btc-updown-15m)
_RECURRING_INTERVAL = 900  # 15 minutes
# How many recent windows to probe when searching for active markets
_PROBE_WINDOWS = 4


class MarketFetcher:
    """Fetch and cache active Polymarket binary markets."""

    def __init__(self, settings: Settings):
        self._gamma_url = settings.gamma_url
        self._session = requests.Session()
        self._markets_cache = []
        self._last_fetch = 0.0
        self._slug_prefixes = tuple(
            p.strip() for p in settings.market_slug_filter.split(",") if p.strip()
        )
        # Shorter cache when targeting recurring markets
        self._cache_ttl = 60.0 if self._slug_prefixes else 300.0

    def _parse_market(self, m):
        """Parse a raw Gamma API market dict into our internal format.

        Returns the parsed dict, or None if the market is not a valid binary market.
        """
        tokens_raw = m.get("clobTokenIds", "[]")
        if isinstance(tokens_raw, str):
            tokens_raw = json.loads(tokens_raw)

        prices_raw = m.get("outcomePrices", "[]")
        if isinstance(prices_raw, str):
            prices_raw = json.loads(prices_raw)

        # Only include binary markets (exactly 2 tokens)
        if len(tokens_raw) != 2:
            return None

        return {
            "condition_id": m.get("conditionId", ""),
            "question": m.get("question", ""),
            "tokens": tokens_raw,
            "outcome_prices": [float(p) for p in prices_raw] if prices_raw else [0.5, 0.5],
            "volume": float(m.get("volume", 0)),
            "liquidity": float(m.get("liquidity", 0)),
            "slug": m.get("slug", ""),
        }

    def _fetch_recurring_markets(self, prefix):
        """Fetch current active market(s) for a recurring time-based slug prefix.

        For prefixes like 'btc-updown-15m', probes recent 15-minute windows
        by computing timestamps and fetching by exact slug.
        """
        markets = []
        now = int(time.time())
        base_ts = (now // _RECURRING_INTERVAL) * _RECURRING_INTERVAL

        for i in range(_PROBE_WINDOWS):
            ts = base_ts - (i * _RECURRING_INTERVAL)
            slug = f"{prefix}-{ts}"
            try:
                resp = self._session.get(
                    f"{self._gamma_url}/markets",
                    params={"slug": slug},
                    timeout=10,
                )
                resp.raise_for_status()
                data = resp.json()
                if not data:
                    continue

                raw = data[0] if isinstance(data, list) else data
                if not raw.get("acceptingOrders", False):
                    continue

                # Skip markets whose end time has already passed
                end_date_str = raw.get("endDate", "")
                if end_date_str:
                    try:
                        end_dt = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
                        if end_dt < datetime.now(timezone.utc):
                            continue
                    except (ValueError, TypeError):
                        pass

                parsed = self._parse_market(raw)
                if parsed:
                    markets.append(parsed)
            except Exception:
                continue

        return markets

    def get_active_markets(self):
        """Return list of active binary markets.

        Each market dict contains:
        - condition_id, question, tokens, outcome_prices, volume, slug

        When slug_prefixes are configured, also probes for recurring
        time-based markets that don't appear in the default listing.
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
                parsed = self._parse_market(m)
                if parsed:
                    markets.append(parsed)

            # Probe for recurring time-based markets matching slug prefixes
            seen_slugs = {m["slug"] for m in markets}
            for prefix in self._slug_prefixes:
                for m in self._fetch_recurring_markets(prefix):
                    if m["slug"] not in seen_slugs:
                        markets.append(m)
                        seen_slugs.add(m["slug"])

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
