"""Tests for data.market_fetcher module."""
import json
import unittest
from unittest.mock import patch, MagicMock

from config.settings import Settings
from data.market_fetcher import MarketFetcher


MOCK_GAMMA_RESPONSE = [
    {
        "conditionId": "0xabc123",
        "question": "Will Bitcoin reach $100k by end of 2025?",
        "clobTokenIds": json.dumps(["token_yes_1", "token_no_1"]),
        "outcomePrices": json.dumps(["0.65", "0.35"]),
        "volume": "50000",
        "liquidity": "12000",
        "slug": "bitcoin-100k-2025",
    },
    {
        "conditionId": "0xdef456",
        "question": "Will it rain tomorrow?",
        "clobTokenIds": json.dumps(["token_yes_2", "token_no_2"]),
        "outcomePrices": json.dumps(["0.30", "0.70"]),
        "volume": "1000",
        "liquidity": "500",
        "slug": "rain-tomorrow",
    },
]


class TestMarketFetcher(unittest.TestCase):

    def _make_fetcher(self):
        settings = Settings()
        return MarketFetcher(settings)

    @patch("data.market_fetcher.requests.Session")
    def test_get_active_markets(self, MockSession):
        """Returns parsed market list from mocked Gamma API response."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_GAMMA_RESPONSE
        mock_resp.raise_for_status = MagicMock()
        MockSession.return_value.get.return_value = mock_resp

        fetcher = self._make_fetcher()
        markets = fetcher.get_active_markets()

        self.assertEqual(len(markets), 2)
        self.assertEqual(markets[0]["condition_id"], "0xabc123")
        self.assertEqual(markets[0]["tokens"], ["token_yes_1", "token_no_1"])
        self.assertAlmostEqual(markets[0]["outcome_prices"][0], 0.65)

    @patch("data.market_fetcher.requests.Session")
    def test_caching(self, MockSession):
        """Second call within TTL returns cached data."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_GAMMA_RESPONSE
        mock_resp.raise_for_status = MagicMock()
        MockSession.return_value.get.return_value = mock_resp

        fetcher = self._make_fetcher()
        fetcher.get_active_markets()
        fetcher.get_active_markets()

        # Only one HTTP call despite two get_active_markets calls
        self.assertEqual(MockSession.return_value.get.call_count, 1)

    @patch("data.market_fetcher.requests.Session")
    def test_get_token_ids(self, MockSession):
        """Correctly extracts (yes_token_id, no_token_id)."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_GAMMA_RESPONSE
        mock_resp.raise_for_status = MagicMock()
        MockSession.return_value.get.return_value = mock_resp

        fetcher = self._make_fetcher()
        yes_id, no_id = fetcher.get_token_ids_for_market("0xabc123")
        self.assertEqual(yes_id, "token_yes_1")
        self.assertEqual(no_id, "token_no_1")

    @patch("data.market_fetcher.requests.Session")
    def test_handles_api_error_gracefully(self, MockSession):
        """Returns empty list on HTTP error."""
        MockSession.return_value.get.side_effect = Exception("Connection error")

        fetcher = self._make_fetcher()
        markets = fetcher.get_active_markets()
        self.assertEqual(markets, [])


if __name__ == "__main__":
    unittest.main()
