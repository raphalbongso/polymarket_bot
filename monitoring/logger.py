"""Structured JSON logging for the trading bot."""
import json
import logging
import sys


class StructuredFormatter(logging.Formatter):
    """Format log records as single-line JSON."""

    def format(self, record):
        log_entry = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "module": record.module,
            "message": record.getMessage(),
        }
        if hasattr(record, "extra_data"):
            log_entry["extra"] = record.extra_data
        return json.dumps(log_entry)


def setup_logger(name="polymarket_bot", level="INFO"):
    """Create and configure the root logger with structured JSON output."""
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    if not logger.handlers:
        console = logging.StreamHandler(sys.stdout)
        console.setFormatter(StructuredFormatter())
        logger.addHandler(console)

    return logger


def get_logger(module_name):
    """Get a child logger for a specific module."""
    return logging.getLogger(f"polymarket_bot.{module_name}")
