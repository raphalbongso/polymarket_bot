"""Immutable bot configuration loaded from environment variables."""
import os
from dataclasses import dataclass

from dotenv import load_dotenv

VALID_TRADING_MODES = ("dry_run", "paper", "live")


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
    signature_type: int = 0   # 0=EOA, 1=Magic, 2=Browser
    funder_address: str = ""

    # Market filter (comma-separated slug prefixes, empty = all markets)
    market_slug_filter: str = ""

    # Bot behavior
    trading_mode: str = "dry_run"  # "dry_run" | "paper" | "live"
    dry_run: bool = True           # True for dry_run and paper; False only for live
    log_level: str = "INFO"
    tick_interval_seconds: float = 10.0

    # Paper trading
    paper_balance: float = 1000.0
    paper_slippage_bps: float = 5.0
    paper_order_ttl_seconds: float = 300.0

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

    # High confidence strategy
    high_confidence_threshold: float = 0.95

    # Order management
    stale_order_seconds: float = 300.0

    # Whale following
    whale_wallets: tuple = ()


def load_settings() -> Settings:
    """Load settings from .env file and environment variables."""
    load_dotenv()

    whale_raw = os.getenv("WHALE_WALLETS", "")
    whale_wallets = tuple(w.strip() for w in whale_raw.split(",") if w.strip())

    # Determine trading mode: TRADING_MODE takes priority, fall back to DRY_RUN
    trading_mode_raw = os.getenv("TRADING_MODE", "")
    if trading_mode_raw:
        trading_mode = trading_mode_raw.lower().strip()
        if trading_mode not in VALID_TRADING_MODES:
            raise ValueError(
                f"Invalid TRADING_MODE '{trading_mode}'. Must be one of: {VALID_TRADING_MODES}"
            )
    else:
        # Backward compat: derive from DRY_RUN
        is_dry = os.getenv("DRY_RUN", "true").lower() in ("true", "1", "yes")
        trading_mode = "dry_run" if is_dry else "live"

    # dry_run is True for both dry_run and paper modes
    dry_run = trading_mode != "live"

    return Settings(
        private_key=os.getenv("POLYMARKET_PRIVATE_KEY", ""),
        api_key=os.getenv("POLYMARKET_API_KEY", ""),
        api_secret=os.getenv("POLYMARKET_API_SECRET", ""),
        passphrase=os.getenv("POLYMARKET_PASSPHRASE", ""),
        chain_id=int(os.getenv("CHAIN_ID", "137")),
        signature_type=int(os.getenv("SIGNATURE_TYPE", "0")),
        funder_address=os.getenv("FUNDER_ADDRESS", ""),
        market_slug_filter=os.getenv("MARKET_SLUG_FILTER", ""),
        trading_mode=trading_mode,
        dry_run=dry_run,
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        tick_interval_seconds=float(os.getenv("TICK_INTERVAL_SECONDS", "10.0")),
        paper_balance=float(os.getenv("PAPER_BALANCE", "1000.0")),
        paper_slippage_bps=float(os.getenv("PAPER_SLIPPAGE_BPS", "5.0")),
        paper_order_ttl_seconds=float(os.getenv("PAPER_ORDER_TTL_SECONDS", "300")),
        max_drawdown_pct=float(os.getenv("MAX_DRAWDOWN_PCT", "0.10")),
        daily_loss_limit_usd=float(os.getenv("DAILY_LOSS_LIMIT_USD", "100.0")),
        max_consecutive_losses=int(os.getenv("MAX_CONSECUTIVE_LOSSES", "5")),
        max_position_size_usd=float(os.getenv("MAX_POSITION_SIZE_USD", "50.0")),
        kelly_fraction=float(os.getenv("KELLY_FRACTION", "0.25")),
        max_kelly_fraction=float(os.getenv("MAX_KELLY_FRACTION", "0.50")),
        zmq_pub_port=int(os.getenv("ZMQ_PUB_PORT", "5555")),
        news_api_key=os.getenv("NEWS_API_KEY", ""),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        high_confidence_threshold=float(os.getenv("HIGH_CONFIDENCE_THRESHOLD", "0.95")),
        stale_order_seconds=float(os.getenv("STALE_ORDER_SECONDS", "300.0")),
        whale_wallets=whale_wallets,
    )
