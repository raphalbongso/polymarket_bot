"""Immutable bot configuration loaded from environment variables."""
import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    # Polymarket connection
    private_key: str = ""
    api_key: str = ""
    api_secret: str = ""
    passphrase: str = ""
    chain_id: int = 137
    clob_url: str = "https://clob.polymarket.com"
    gamma_url: str = "https://gamma-api.polymarket.com"
    data_api_url: str = "https://data-api.polymarket.com"
    ws_url: str = "wss://ws-subscriptions-clob.polymarket.com/ws/market"

    # Bot behavior
    dry_run: bool = True
    log_level: str = "INFO"
    tick_interval_seconds: float = 10.0

    # Risk parameters
    max_drawdown_pct: float = 0.10
    daily_loss_limit_usd: float = 100.0
    max_consecutive_losses: int = 5
    max_position_size_usd: float = 50.0
    kelly_fraction: float = 0.25
    max_kelly_fraction: float = 0.50

    # Monitoring
    zmq_pub_port: int = 5555

    # Data buffer sizes
    price_history_maxlen: int = 1000
    orderbook_history_maxlen: int = 100
    trade_history_maxlen: int = 500

    # News / AI (optional)
    news_api_key: str = ""
    openai_api_key: str = ""

    # Whale following
    whale_wallets: tuple = ()


def load_settings() -> Settings:
    """Load settings from .env file and environment variables."""
    load_dotenv()

    whale_raw = os.getenv("WHALE_WALLETS", "")
    whale_wallets = tuple(w.strip() for w in whale_raw.split(",") if w.strip())

    return Settings(
        private_key=os.getenv("POLYMARKET_PRIVATE_KEY", ""),
        api_key=os.getenv("POLYMARKET_API_KEY", ""),
        api_secret=os.getenv("POLYMARKET_API_SECRET", ""),
        passphrase=os.getenv("POLYMARKET_PASSPHRASE", ""),
        chain_id=int(os.getenv("CHAIN_ID", "137")),
        dry_run=os.getenv("DRY_RUN", "true").lower() in ("true", "1", "yes"),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        tick_interval_seconds=float(os.getenv("TICK_INTERVAL_SECONDS", "10.0")),
        max_drawdown_pct=float(os.getenv("MAX_DRAWDOWN_PCT", "0.10")),
        daily_loss_limit_usd=float(os.getenv("DAILY_LOSS_LIMIT_USD", "100.0")),
        max_consecutive_losses=int(os.getenv("MAX_CONSECUTIVE_LOSSES", "5")),
        max_position_size_usd=float(os.getenv("MAX_POSITION_SIZE_USD", "50.0")),
        kelly_fraction=float(os.getenv("KELLY_FRACTION", "0.25")),
        max_kelly_fraction=float(os.getenv("MAX_KELLY_FRACTION", "0.50")),
        zmq_pub_port=int(os.getenv("ZMQ_PUB_PORT", "5555")),
        news_api_key=os.getenv("NEWS_API_KEY", ""),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        whale_wallets=whale_wallets,
    )
