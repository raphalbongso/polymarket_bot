"""Paper trading engine — simulates order execution against real orderbook data."""
import time
import uuid
from dataclasses import dataclass, field

from monitoring.logger import get_logger

logger = get_logger("paper_trader")


@dataclass
class PaperOrder:
    order_id: str
    token_id: str
    side: str          # "BUY" or "SELL"
    price: float
    quantity: float
    status: str = "open"       # "open", "filled", "partial", "expired", "rejected"
    filled_quantity: float = 0.0
    avg_fill_price: float = 0.0
    created_at: float = field(default_factory=time.time)
    ttl_seconds: float = 300.0


@dataclass
class FillResult:
    status: str              # "filled", "partial", "resting", "rejected"
    filled_qty: float
    avg_fill_price: float
    slippage_bps: float
    realized_pnl: float = 0.0
    order_id: str = ""


@dataclass
class Position:
    token_id: str
    quantity: float = 0.0
    avg_entry_price: float = 0.0
    cost_basis: float = 0.0
    realized_pnl: float = 0.0


class PaperTrader:
    """Simulates order execution against real Polymarket orderbook data."""

    def __init__(self, balance: float, slippage_bps: float = 5.0, order_ttl: float = 300.0):
        self._balance = balance
        self._initial_balance = balance
        self._slippage_bps = slippage_bps
        self._order_ttl = order_ttl

        self._positions: dict[str, Position] = {}    # token_id -> Position
        self._resting_orders: list[PaperOrder] = []
        self._filled_orders: list[PaperOrder] = []
        self._total_realized_pnl = 0.0

    @property
    def balance(self) -> float:
        return self._balance

    @property
    def positions(self) -> dict[str, Position]:
        return dict(self._positions)

    @property
    def resting_orders(self) -> list[PaperOrder]:
        return list(self._resting_orders)

    def execute(self, signal, size_usd: float, orderbook: dict) -> FillResult:
        """Try to execute a signal. Fills immediately if marketable, else rests."""
        quantity = size_usd / signal.suggested_price if signal.suggested_price > 0 else 0.0
        if quantity <= 0:
            return FillResult(status="rejected", filled_qty=0, avg_fill_price=0,
                              slippage_bps=0)

        order = PaperOrder(
            order_id=str(uuid.uuid4())[:8],
            token_id=signal.token_id,
            side=signal.side,
            price=signal.suggested_price,
            quantity=quantity,
            ttl_seconds=self._order_ttl,
        )

        # Check if order is marketable (can fill immediately)
        fill = self._try_fill(order, orderbook)

        if fill.status == "rejected":
            return fill

        if fill.filled_qty > 0:
            order.filled_quantity = fill.filled_qty
            order.avg_fill_price = fill.avg_fill_price

        if fill.status == "filled":
            order.status = "filled"
            self._filled_orders.append(order)
            logger.info(
                f"[PAPER] {order.side} {fill.filled_qty:.4f} @ {fill.avg_fill_price:.4f} "
                f"(slippage: {fill.slippage_bps:.1f}bps) | Balance: ${self._balance:.2f}"
            )
        else:
            # Resting order (not marketable or partial)
            remaining = order.quantity - order.filled_quantity
            if remaining > 0:
                order.status = "partial" if order.filled_quantity > 0 else "open"
                self._resting_orders.append(order)
                logger.info(
                    f"[PAPER] Resting {order.side} order: {remaining:.4f} @ {order.price:.4f} "
                    f"(TTL: {self._order_ttl}s)"
                )

        return fill

    def check_resting_orders(self, orderbooks: dict) -> list[FillResult]:
        """Check all resting orders against current orderbooks. Called each tick."""
        fills = []
        still_resting = []
        now = time.time()

        for order in self._resting_orders:
            # Check expiry
            if now - order.created_at > order.ttl_seconds:
                order.status = "expired"
                logger.info(f"[PAPER] Order {order.order_id} expired")
                continue

            # Try to fill against current orderbook
            ob = orderbooks.get(order.token_id)
            if ob is None:
                still_resting.append(order)
                continue

            remaining_qty = order.quantity - order.filled_quantity
            remaining_order = PaperOrder(
                order_id=order.order_id,
                token_id=order.token_id,
                side=order.side,
                price=order.price,
                quantity=remaining_qty,
                created_at=order.created_at,
                ttl_seconds=order.ttl_seconds,
            )
            fill = self._try_fill(remaining_order, ob)

            if fill.filled_qty > 0:
                # Update running average fill price
                prev_filled = order.filled_quantity
                prev_cost = prev_filled * order.avg_fill_price
                new_cost = fill.filled_qty * fill.avg_fill_price
                order.filled_quantity += fill.filled_qty
                order.avg_fill_price = (
                    (prev_cost + new_cost) / order.filled_quantity
                    if order.filled_quantity > 0 else 0
                )
                fills.append(fill)

                logger.info(
                    f"[PAPER] Resting order {order.order_id} filled {fill.filled_qty:.4f} "
                    f"@ {fill.avg_fill_price:.4f}"
                )

            if order.filled_quantity >= order.quantity:
                order.status = "filled"
                self._filled_orders.append(order)
            else:
                still_resting.append(order)

        self._resting_orders = still_resting
        return fills

    def _try_fill(self, order: PaperOrder, orderbook: dict) -> FillResult:
        """Walk the orderbook to simulate a fill. Applies slippage."""
        if order.side == "BUY":
            levels = orderbook.get("asks", [])
            # For a BUY, we consume ask levels at or below our price
            marketable = [(p, s) for p, s in levels if p <= order.price]
        else:
            levels = orderbook.get("bids", [])
            # For a SELL, we consume bid levels at or above our price
            marketable = [(p, s) for p, s in levels if p >= order.price]

        if not marketable:
            return FillResult(status="resting", filled_qty=0, avg_fill_price=0,
                              slippage_bps=0, order_id=order.order_id)

        # Walk levels to fill
        remaining = order.quantity
        total_cost = 0.0
        filled_qty = 0.0

        for level_price, level_size in marketable:
            if remaining <= 0:
                break
            fill_at_level = min(remaining, level_size)
            total_cost += fill_at_level * level_price
            filled_qty += fill_at_level
            remaining -= fill_at_level

        if filled_qty <= 0:
            return FillResult(status="resting", filled_qty=0, avg_fill_price=0,
                              slippage_bps=0, order_id=order.order_id)

        avg_price = total_cost / filled_qty

        # Apply slippage
        slippage_mult = self._slippage_bps / 10000.0
        if order.side == "BUY":
            avg_price *= (1 + slippage_mult)
        else:
            avg_price *= (1 - slippage_mult)

        actual_slippage_bps = abs(avg_price - order.price) / order.price * 10000

        # Check balance for buys
        cost = filled_qty * avg_price
        if order.side == "BUY" and cost > self._balance:
            # Reduce to what we can afford
            filled_qty = self._balance / avg_price
            cost = filled_qty * avg_price
            if filled_qty <= 0:
                return FillResult(status="rejected", filled_qty=0, avg_fill_price=0,
                                  slippage_bps=0, order_id=order.order_id)

        # Update balance and position
        realized_pnl = self._update_position(
            order.token_id, order.side, filled_qty, avg_price
        )

        status = "filled" if remaining <= 0 else "partial"
        return FillResult(
            status=status,
            filled_qty=filled_qty,
            avg_fill_price=avg_price,
            slippage_bps=actual_slippage_bps,
            realized_pnl=realized_pnl,
            order_id=order.order_id,
        )

    def _update_position(self, token_id: str, side: str, qty: float, price: float) -> float:
        """Update position with weighted-average entry. Returns realized PnL."""
        if token_id not in self._positions:
            self._positions[token_id] = Position(token_id=token_id)

        pos = self._positions[token_id]
        realized_pnl = 0.0

        if side == "BUY":
            # Deduct from balance
            cost = qty * price
            self._balance -= cost

            # Increase position (weighted average entry)
            total_qty = pos.quantity + qty
            if total_qty > 0:
                pos.avg_entry_price = (
                    (pos.quantity * pos.avg_entry_price + qty * price) / total_qty
                )
            pos.quantity = total_qty
            pos.cost_basis = pos.quantity * pos.avg_entry_price

        elif side == "SELL":
            if pos.quantity > 0:
                # Selling existing position — realize PnL
                sell_qty = min(qty, pos.quantity)
                realized_pnl = sell_qty * (price - pos.avg_entry_price)
                pos.realized_pnl += realized_pnl
                self._total_realized_pnl += realized_pnl

                pos.quantity -= sell_qty
                pos.cost_basis = pos.quantity * pos.avg_entry_price

                # Credit balance
                self._balance += sell_qty * price
            else:
                # Short selling (simple: just credit balance, negative position)
                self._balance += qty * price
                total_qty = pos.quantity - qty
                pos.avg_entry_price = price
                pos.quantity = total_qty
                pos.cost_basis = abs(pos.quantity) * pos.avg_entry_price

        return realized_pnl

    def get_unrealized_pnl(self, orderbook_tracker) -> float:
        """Calculate unrealized PnL using current midpoints."""
        unrealized = 0.0
        for token_id, pos in self._positions.items():
            if pos.quantity == 0:
                continue
            mid = orderbook_tracker.get_midpoint(token_id)
            if mid is not None:
                unrealized += pos.quantity * (mid - pos.avg_entry_price)
        return unrealized

    def get_position_summary(self) -> dict:
        """Return a summary of paper trading state."""
        open_positions = {
            tid: {
                "quantity": p.quantity,
                "avg_entry": round(p.avg_entry_price, 4),
                "realized_pnl": round(p.realized_pnl, 4),
            }
            for tid, p in self._positions.items()
            if p.quantity != 0
        }

        return {
            "balance": round(self._balance, 2),
            "initial_balance": self._initial_balance,
            "total_realized_pnl": round(self._total_realized_pnl, 4),
            "open_positions": len(open_positions),
            "resting_orders": len(self._resting_orders),
            "filled_orders": len(self._filled_orders),
            "positions": open_positions,
        }

    def get_final_report(self) -> str:
        """Generate a final report string for shutdown."""
        summary = self.get_position_summary()
        lines = [
            "=== PAPER TRADING FINAL REPORT ===",
            f"  Initial balance:    ${summary['initial_balance']:.2f}",
            f"  Final balance:      ${summary['balance']:.2f}",
            f"  Realized PnL:       ${summary['total_realized_pnl']:.4f}",
            f"  Open positions:     {summary['open_positions']}",
            f"  Total fills:        {summary['filled_orders']}",
            f"  Resting orders:     {summary['resting_orders']}",
        ]
        for tid, pdata in summary["positions"].items():
            lines.append(
                f"    {tid[:16]}... qty={pdata['quantity']:.4f} "
                f"entry={pdata['avg_entry']:.4f} rpnl=${pdata['realized_pnl']:.4f}"
            )
        lines.append("=" * 35)
        return "\n".join(lines)
