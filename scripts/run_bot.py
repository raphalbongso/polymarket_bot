"""Start the Polymarket trading bot.

Usage:
    python scripts/run_bot.py
    python -m scripts.run_bot

DRY_RUN=true by default. Set DRY_RUN=false in .env to enable live trading.
"""
import signal
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import load_settings
from monitoring.logger import setup_logger
from bot.orchestrator import Orchestrator


def main():
    settings = load_settings()
    setup_logger(level=settings.log_level)

    mode_labels = {
        "dry_run": "DRY RUN (log only, no trades)",
        "paper": "PAPER TRADING (simulated fills against live data)",
        "live": "LIVE TRADING",
        "selenium": "SELENIUM TRADING (browser-based execution)",
    }
    mode_label = mode_labels.get(settings.trading_mode, settings.trading_mode)

    print("=" * 60)
    print("  POLYMARKET TRADING BOT")
    print(f"  Mode: {mode_label}")
    if settings.trading_mode == "paper":
        print(f"  Paper balance: ${settings.paper_balance:.2f}")
        print(f"  Slippage: {settings.paper_slippage_bps} bps")
        print(f"  Order TTL: {settings.paper_order_ttl_seconds}s")
    print(f"  Log level: {settings.log_level}")
    print("=" * 60)

    if settings.trading_mode == "live":
        print("\n  WARNING: LIVE TRADING MODE ENABLED")
        print("  Real orders will be placed on Polymarket.\n")

    orchestrator = Orchestrator(settings)

    def shutdown_handler(signum, frame):
        print("\nShutdown signal received...")
        orchestrator.stop()

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    try:
        orchestrator.start()
    except KeyboardInterrupt:
        orchestrator.stop()


if __name__ == "__main__":
    main()
