"""Main orchestrator — ties all components together in the event loop."""
import time
from datetime import datetime, timezone

from config.settings import Settings
from config.client_factory import create_clob_client, fetch_usdc_balance

try:
    from py_clob_client.clob_types import OrderArgs, MarketOrderArgs, OrderType
    from py_clob_client.order_builder.constants import BUY, SELL
    HAS_ORDER_TYPES = True
except ImportError:
    HAS_ORDER_TYPES = False
from bot.paper_trader import PaperTrader
from data.market_fetcher import MarketFetcher
from data.orderbook_tracker import OrderbookTracker
from data.order_tracker import OrderTracker
from data.position_tracker import PositionTracker
from data.price_history import PriceHistory
from data.whale_tracker import WhaleTracker
from monitoring.logger import get_logger
from monitoring.zmq_publisher import ZMQPublisher
from risk.risk_manager import RiskManager
from strategies.arbitrage import ArbitrageStrategy
from strategies.high_confidence import HighConfidenceStrategy
from strategies.market_making import MarketMakingStrategy
from strategies.news_driven import NewsDrivenStrategy
from strategies.whale_following import WhaleFollowingStrategy

logger = get_logger("orchestrator")


class Orchestrator:
    """Main event loop — fetches data, evaluates strategies, executes trades."""

    def __init__(self, settings: Settings):
        self._settings = settings

        # Build dependency graph
        self._clob_client = create_clob_client(settings)
        self._market_fetcher = MarketFetcher(settings)
        self._orderbook_tracker = OrderbookTracker(self._clob_client, settings)
        self._price_history = PriceHistory(settings)
        self._whale_tracker = WhaleTracker(settings)
        self._risk_manager = RiskManager(settings)
        self._zmq_publisher = ZMQPublisher(settings.zmq_pub_port)

        # Order and position trackers
        self._order_tracker = OrderTracker(
            self._clob_client,
            stale_seconds=settings.stale_order_seconds,
        )
        self._position_tracker = PositionTracker(settings)

        # Paper trader (only for paper mode)
        self._paper_trader = None
        if settings.trading_mode == "paper":
            self._paper_trader = PaperTrader(
                balance=settings.paper_balance,
                slippage_bps=settings.paper_slippage_bps,
                order_ttl=settings.paper_order_ttl_seconds,
            )
            self._risk_manager.set_balance(settings.paper_balance)

        # Sync real balance for live mode
        if settings.trading_mode == "live" and self._clob_client:
            real_balance = fetch_usdc_balance(self._clob_client)
            if real_balance is not None:
                self._risk_manager.set_balance(real_balance)
                logger.info(f"Live USDC balance: ${real_balance:.2f}")
            else:
                logger.warning("Could not fetch live balance")

        # Parse slug filter prefixes
        self._slug_prefixes = tuple(
            p.strip() for p in settings.market_slug_filter.split(",") if p.strip()
        )

        self._strategies = []
        self._register_default_strategies()

        self._running = False
        self._tick_count = 0

    def _register_default_strategies(self):
        """Register the four default strategies with graceful degradation."""
        self._strategies.append(ArbitrageStrategy(self._settings))
        self._strategies.append(HighConfidenceStrategy(self._settings))
        self._strategies.append(MarketMakingStrategy(self._settings))

        try:
            self._strategies.append(NewsDrivenStrategy(self._settings))
        except Exception as e:
            logger.warning(f"News strategy unavailable: {e}")

        try:
            self._strategies.append(
                WhaleFollowingStrategy(self._settings, self._whale_tracker)
            )
        except Exception as e:
            logger.warning(f"Whale strategy unavailable: {e}")

    def _get_required_data_types(self):
        """Union of all enabled strategies' data requirements."""
        required = set()
        for s in self._strategies:
            if s.is_enabled:
                required.update(s.get_required_data())
        return required

    def _fetch_orderbooks(self, market):
        """Fetch orderbooks for all tokens in a market."""
        books = {}
        for token_id in market.get("tokens", []):
            books[token_id] = self._orderbook_tracker.fetch_orderbook(token_id)
        return books

    def _execute_signal(self, signal, size_usd, orderbook=None):
        """Execute a trading signal. Three-way branch: dry_run / paper / live."""
        trade_info = {
            "strategy": signal.strategy_name,
            "market": signal.market_condition_id,
            "token": signal.token_id[:16] + "...",
            "side": signal.side,
            "price": signal.suggested_price,
            "size_usd": round(size_usd, 2),
            "confidence": round(signal.confidence, 3),
            "mode": self._settings.trading_mode,
            "order_type": signal.order_type,
        }

        mode = self._settings.trading_mode

        # --- DRY RUN: log only ---
        if mode == "dry_run":
            logger.info(f"[DRY RUN] Would {signal.side} ${size_usd:.2f} at {signal.suggested_price:.4f}",
                        extra={"extra_data": trade_info})
            self._zmq_publisher.publish("trade", trade_info)
            return

        # --- PAPER TRADING: simulate against real orderbook ---
        if mode == "paper":
            ob = orderbook or {"bids": [], "asks": []}
            fill = self._paper_trader.execute(signal, size_usd, ob)
            trade_info["fill_status"] = fill.status
            trade_info["filled_qty"] = round(fill.filled_qty, 4)
            trade_info["avg_fill_price"] = round(fill.avg_fill_price, 4)
            trade_info["slippage_bps"] = round(fill.slippage_bps, 1)
            trade_info["realized_pnl"] = round(fill.realized_pnl, 4)
            self._zmq_publisher.publish("trade", trade_info)

            if fill.realized_pnl != 0:
                self._risk_manager.record_trade({
                    "pnl": fill.realized_pnl,
                    "side": signal.side,
                    "size": size_usd,
                    "price": fill.avg_fill_price,
                })
            return

        # --- LIVE TRADING ---
        if self._clob_client is None:
            logger.error("Cannot trade: CLOB client not available")
            return

        if not HAS_ORDER_TYPES:
            logger.error("Cannot trade: py_clob_client order types not available")
            return

        # Balance check before placing order
        balance = fetch_usdc_balance(self._clob_client)
        if balance is not None:
            self._risk_manager.set_balance(balance)
            if balance < size_usd:
                logger.warning(
                    f"Insufficient balance: ${balance:.2f} < ${size_usd:.2f}",
                    extra={"extra_data": trade_info},
                )
                return

        try:
            side = BUY if signal.side == "BUY" else SELL

            if signal.order_type == "market":
                # Fill-or-kill market order for immediate execution
                market_args = MarketOrderArgs(
                    token_id=signal.token_id,
                    amount=size_usd,
                    side=side,
                )
                signed_order = self._clob_client.create_market_order(market_args)
                result = self._clob_client.post_order(signed_order, OrderType.FOK)
            else:
                # Standard limit order (GTC)
                order_args = OrderArgs(
                    price=signal.suggested_price,
                    size=size_usd / signal.suggested_price,
                    side=side,
                    token_id=signal.token_id,
                )
                signed_order = self._clob_client.create_order(order_args)
                result = self._clob_client.post_order(signed_order)

            logger.info(f"Order placed: {result}", extra={"extra_data": trade_info})
            self._zmq_publisher.publish("trade", trade_info)

            self._risk_manager.record_trade({
                "pnl": 0.0,
                "side": signal.side,
                "size": size_usd,
                "price": signal.suggested_price,
            })

            if signal.strategy_name == "market_making":
                for s in self._strategies:
                    if hasattr(s, "update_inventory"):
                        delta = size_usd if signal.side == "BUY" else -size_usd
                        s.update_inventory(signal.token_id, delta)

        except Exception as e:
            logger.error(f"Order failed: {e}", extra={"extra_data": trade_info})

    def run(self):
        """Main event loop."""
        mode_info = f"mode={self._settings.trading_mode}"
        if self._settings.trading_mode == "paper":
            mode_info += (
                f" balance=${self._settings.paper_balance:.0f}"
                f" slippage={self._settings.paper_slippage_bps}bps"
            )
        filter_info = f" | Filter: {', '.join(self._slug_prefixes)}" if self._slug_prefixes else ""
        logger.info(
            f"Bot started | {mode_info} | "
            f"Strategies: {[s.name for s in self._strategies if s.is_enabled]} | "
            f"Tick interval: {self._settings.tick_interval_seconds}s{filter_info}"
        )

        self._running = True
        required_data = self._get_required_data_types()

        while self._running and not self._risk_manager.is_killed:
            try:
                self._tick(required_data)
            except Exception as e:
                logger.error(f"Tick error: {e}")

            self._tick_count += 1
            time.sleep(self._settings.tick_interval_seconds)

        reason = "kill switch" if self._risk_manager.is_killed else "stopped"
        logger.info(f"Bot stopped: {reason} after {self._tick_count} ticks")

    def _tick(self, required_data):
        """Execute one tick of the main loop."""
        # Refresh markets periodically (every 30 ticks)
        if self._tick_count % 30 == 0:
            self._market_fetcher.refresh()

        markets = self._market_fetcher.get_active_markets()

        # Apply slug filter if configured
        if self._slug_prefixes:
            markets = [
                m for m in markets
                if any(m["slug"].startswith(p) for p in self._slug_prefixes)
            ]
            if self._tick_count == 0:
                logger.info(
                    f"Slug filter active ({', '.join(self._slug_prefixes)}): "
                    f"{len(markets)} matching markets"
                )

        # Log remaining time for time-based markets
        now_utc = datetime.now(timezone.utc)
        for m in markets:
            end_dt = m.get("end_date")
            if end_dt:
                remaining = (end_dt - now_utc).total_seconds()
                mins, secs = divmod(int(max(0, remaining)), 60)
                if remaining <= 300:
                    logger.info(
                        f"[{m['slug']}] {mins}m{secs:02d}s left — LAST 5 MIN"
                    )
                elif self._tick_count % 6 == 0:  # log every ~60s otherwise
                    logger.info(
                        f"[{m['slug']}] {mins}m{secs:02d}s left"
                    )

        # Fetch whale data if needed
        if "whale_trades" in required_data:
            self._whale_tracker.check_all_wallets()

        orderbooks = {}
        for market in markets[:20]:  # Limit to top 20 markets
            if "orderbook" in required_data:
                orderbooks = self._fetch_orderbooks(market)

                # Record midpoints in price history
                for token_id in market.get("tokens", []):
                    mid = self._orderbook_tracker.get_midpoint(token_id)
                    if mid is not None:
                        self._price_history.record(token_id, mid)

            # Evaluate each strategy
            for strategy in self._strategies:
                if not strategy.is_enabled:
                    continue

                try:
                    signals = strategy.evaluate(
                        market, orderbooks, self._price_history
                    )
                except Exception as e:
                    logger.warning(f"Strategy {strategy.name} error: {e}")
                    continue

                for signal in signals:
                    self._zmq_publisher.publish("signal", {
                        "strategy": signal.strategy_name,
                        "market": signal.market_condition_id,
                        "side": signal.side,
                        "confidence": signal.confidence,
                    })

                    # Risk check and sizing
                    fixed = signal.metadata.get("fixed_size_usd")
                    if fixed:
                        if not self._risk_manager.pre_trade_check(signal):
                            continue
                        size = fixed
                    else:
                        size = self._risk_manager.calculate_position_size(signal)
                    if size > 0:
                        ob = orderbooks.get(signal.token_id)
                        self._execute_signal(signal, size, orderbook=ob)

        # Check resting paper orders each tick
        if self._paper_trader and orderbooks:
            self._paper_trader.check_resting_orders(orderbooks)

        # Track and cancel stale orders + refresh positions (live mode, every ~60s)
        if (self._settings.trading_mode == "live"
                and self._clob_client
                and self._tick_count % 6 == 0):
            self._order_tracker.fetch_open_orders()
            cancelled = self._order_tracker.cancel_stale_orders()
            if cancelled:
                logger.info(f"Cancelled {cancelled} stale orders")
            self._position_tracker.fetch_positions()

        # Heartbeat
        heartbeat = {
            "tick": self._tick_count,
            "timestamp": time.time(),
            "risk": self._risk_manager.get_risk_report(),
        }
        if self._paper_trader:
            heartbeat["paper"] = self._paper_trader.get_position_summary()
        if self._settings.trading_mode == "live":
            heartbeat["open_orders"] = self._order_tracker.get_summary()
            heartbeat["positions"] = self._position_tracker.get_summary()

        self._zmq_publisher.publish("heartbeat", heartbeat)

    def start(self):
        """Start the bot."""
        self.run()

    def stop(self):
        """Gracefully stop the bot."""
        self._running = False
        logger.info("Shutdown requested")

        # Cancel open orders if live
        if self._settings.trading_mode == "live" and self._clob_client:
            try:
                self._clob_client.cancel_all()
                logger.info("Cancelled all open orders")
            except Exception as e:
                logger.error(f"Failed to cancel orders: {e}")

        # Paper trading final report
        if self._paper_trader:
            logger.info(self._paper_trader.get_final_report())

        self._zmq_publisher.close()
        logger.info(f"Final risk report: {self._risk_manager.get_risk_report()}")

    def add_strategy(self, strategy):
        """Register an additional strategy at runtime."""
        self._strategies.append(strategy)
        logger.info(f"Added strategy: {strategy.name}")
