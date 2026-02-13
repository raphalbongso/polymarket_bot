"""News-driven AI strategy — react to breaking news faster than the market."""
import json
import time
from collections import deque

from config.settings import Settings
from monitoring.logger import get_logger
from strategies.base import BaseStrategy, Signal

logger = get_logger("news_driven")

try:
    import requests as _requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


class NewsDrivenStrategy(BaseStrategy):
    """Analyze news headlines with an LLM to generate trading signals."""

    def __init__(self, settings: Settings):
        super().__init__(settings, name="news_driven")
        self._news_api_key = settings.news_api_key
        self._openai_api_key = settings.openai_api_key
        self._available = bool(self._news_api_key and self._openai_api_key)
        self._recent_headlines = deque(maxlen=200)
        self._processed_headlines = set()
        self._last_cleanup = time.time()

        if not self._available:
            self.disable()
            logger.info("News strategy disabled: missing NEWS_API_KEY or OPENAI_API_KEY")

    def _fetch_news(self, keywords):
        """Fetch recent headlines from News API matching keywords."""
        if not self._available or not HAS_REQUESTS:
            return []

        try:
            query = " OR ".join(keywords[:5])
            resp = _requests.get(
                "https://newsapi.org/v2/everything",
                params={
                    "q": query,
                    "sortBy": "publishedAt",
                    "pageSize": 20,
                    "apiKey": self._news_api_key,
                },
                timeout=10,
            )
            resp.raise_for_status()
            articles = resp.json().get("articles", [])
            return [
                {
                    "title": a.get("title", ""),
                    "description": a.get("description", ""),
                    "source": a.get("source", {}).get("name", ""),
                    "published_at": a.get("publishedAt", ""),
                    "url": a.get("url", ""),
                }
                for a in articles
                if a.get("title")
            ]
        except Exception as e:
            logger.warning(f"News fetch failed: {e}")
            return []

    def _analyze_with_llm(self, headline, market_question):
        """Send headline + market question to OpenAI for analysis."""
        if not self._openai_api_key or not HAS_REQUESTS:
            return {"direction": "NEUTRAL", "magnitude": 0.0}

        try:
            resp = _requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._openai_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "gpt-4o-mini",
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "You analyze news headlines for prediction market impact. "
                                "Respond ONLY with JSON: "
                                '{"direction": "UP"|"DOWN"|"NEUTRAL", '
                                '"magnitude": 0.0-1.0, '
                                '"reasoning": "brief explanation"}'
                            ),
                        },
                        {
                            "role": "user",
                            "content": (
                                f'Headline: "{headline}"\n'
                                f'Market question: "{market_question}"\n'
                                "How does this headline affect the probability?"
                            ),
                        },
                    ],
                    "max_tokens": 150,
                    "temperature": 0.1,
                },
                timeout=15,
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            return json.loads(content)
        except Exception as e:
            logger.warning(f"LLM analysis failed: {e}")
            return {"direction": "NEUTRAL", "magnitude": 0.0}

    def evaluate(self, market, orderbook, price_history):
        signals = []
        if not self._available:
            return signals

        # Periodic cleanup of processed headlines (every 1 hour)
        now = time.time()
        if now - self._last_cleanup > 3600:
            self._processed_headlines.clear()
            self._last_cleanup = now

        question = market.get("question", "")
        if not question:
            return signals

        # Extract keywords from market question
        keywords = [w for w in question.split() if len(w) > 3][:5]
        if not keywords:
            return signals

        headlines = self._fetch_news(keywords)

        for headline_data in headlines:
            title = headline_data["title"]
            if title in self._processed_headlines:
                continue

            self._processed_headlines.add(title)
            self._recent_headlines.append(headline_data)

            analysis = self._analyze_with_llm(title, question)
            direction = analysis.get("direction", "NEUTRAL")
            magnitude = float(analysis.get("magnitude", 0.0))

            if direction == "NEUTRAL" or magnitude < 0.3:
                continue

            confidence = magnitude * 0.7  # Cap LLM confidence

            tokens = market.get("tokens", [])
            if len(tokens) != 2:
                continue

            if direction == "UP":
                token_id = tokens[0]  # YES token
                side = "BUY"
            else:
                token_id = tokens[1]  # NO token
                side = "BUY"

            signals.append(Signal(
                strategy_name=self.name,
                market_condition_id=market["condition_id"],
                token_id=token_id,
                side=side,
                confidence=confidence,
                raw_edge=magnitude * 0.1,
                suggested_price=market.get("outcome_prices", [0.5, 0.5])[
                    0 if direction == "UP" else 1
                ],
                max_size=self._settings.max_position_size_usd * 0.5,
                metadata={
                    "headline": title,
                    "direction": direction,
                    "magnitude": magnitude,
                    "reasoning": analysis.get("reasoning", ""),
                },
            ))

        return signals

    def get_required_data(self):
        return {"price_history"}
