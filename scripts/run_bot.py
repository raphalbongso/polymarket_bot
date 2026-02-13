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

    print("=" * 60)
    print("  POLYMARKET TRADING BOT")
    print(f"  Mode: {'DRY RUN (no real trades)' if settings.dry_run else 'LIVE TRADING'}")
    print(f"  Log level: {settings.log_level}")
    print("=" * 60)

    if not settings.dry_run:
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
