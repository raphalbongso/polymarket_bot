"""
Dashboard HTTP server — serves the web UI and a JSON API fed by ZMQ.

Endpoints:
    GET  /              → HTML dashboard
    GET  /api/status    → bot running state, equity, uptime
    GET  /api/equity    → equity curve data points
    GET  /api/strategies→ strategy stats (name, active, trades, pnl, win_rate)
    GET  /api/positions → open positions list
    GET  /api/risk      → risk monitor data
    GET  /api/trades    → recent trade feed
    GET  /api/settings  → current .env settings
    POST /api/settings  → save settings to .env
    POST /api/bot/start → (placeholder)
    POST /api/bot/stop  → (placeholder)
    POST /api/strategy/toggle → toggle strategy on/off
"""
import json
import os
import subprocess
import signal
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler
from pathlib import Path

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from monitoring.zmq_subscriber import ZMQSubscriber

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"
PYTHON_EXE = PROJECT_ROOT / "venv" / "Scripts" / "python.exe"
BOT_SCRIPT = PROJECT_ROOT / "scripts" / "run_bot.py"

# ── Bot Process Management ────────────────────────────────────────────────────
_bot_process = None
_bot_lock = threading.Lock()


def _start_bot():
    """Start run_bot.py als subprocess."""
    global _bot_process
    with _bot_lock:
        if _bot_process and _bot_process.poll() is None:
            return {"status": "already_running"}

        python = str(PYTHON_EXE) if PYTHON_EXE.exists() else sys.executable
        log_file = PROJECT_ROOT / "bot_output.log"
        log_fh = open(log_file, "w", encoding="utf-8", errors="replace")
        _bot_process = subprocess.Popen(
            [python, "-u", str(BOT_SCRIPT)],
            cwd=str(PROJECT_ROOT),
            stdout=log_fh,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
        )
        return {"status": "started", "pid": _bot_process.pid}


def _stop_bot():
    """Stop het bot subprocess."""
    global _bot_process
    with _bot_lock:
        if not _bot_process or _bot_process.poll() is not None:
            _bot_process = None
            return {"status": "not_running"}

        try:
            _bot_process.terminate()
            _bot_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _bot_process.kill()
        pid = _bot_process.pid
        _bot_process = None
        return {"status": "stopped", "pid": pid}


def _bot_is_running():
    """Check of het bot process draait."""
    with _bot_lock:
        return _bot_process is not None and _bot_process.poll() is None

# ── Shared state (written by ZMQ thread, read by HTTP thread) ────────────────

_state_lock = threading.Lock()
_uptime_start = time.time()
_state = {
    "connected": False,
    "running": True,
    "tick": 0,
    "risk": {},
    "paper": {},
    "open_orders": {},
    "positions": {},
    "recent_trades": [],
    "recent_signals": [],
    "strategies": {},
    "equity_history": [],
}

MAX_EVENTS = 200
MAX_EQUITY_POINTS = 500

# Known strategies with defaults
_default_strategies = {
    "high_confidence": {"active": True, "trades": 0, "pnl": 0.0, "wins": 0},
    "arbitrage":       {"active": False, "trades": 0, "pnl": 0.0, "wins": 0},
    "market_making":   {"active": False, "trades": 0, "pnl": 0.0, "wins": 0},
    "news_driven":     {"active": False, "trades": 0, "pnl": 0.0, "wins": 0},
    "whale_following":  {"active": False, "trades": 0, "pnl": 0.0, "wins": 0},
}
_state["strategies"] = {k: dict(v) for k, v in _default_strategies.items()}


def _zmq_listener():
    """Background thread: subscribe to all bot events via ZMQ."""
    sub = ZMQSubscriber(port=5555)
    if not sub.available:
        return

    with _state_lock:
        _state["connected"] = True

    while True:
        msg = sub.receive(timeout_ms=2000)
        if msg is None:
            continue

        topic, data = msg
        with _state_lock:
            if topic == "heartbeat":
                _state["tick"] = data.get("tick", 0)
                _state["risk"] = data.get("risk", {})
                _state["paper"] = data.get("paper", {})
                _state["open_orders"] = data.get("open_orders", {})
                _state["positions"] = data.get("positions", {})

                # Sync strategy active states from orchestrator
                bot_strategies = data.get("strategies", {})
                for name, info in bot_strategies.items():
                    if name not in _state["strategies"]:
                        _state["strategies"][name] = {"active": True, "trades": 0, "pnl": 0.0, "wins": 0}
                    _state["strategies"][name]["active"] = info.get("active", True)

                # Record equity point
                bal = data.get("risk", {}).get("current_balance", 0)
                if bal > 0:
                    _state["equity_history"].append({
                        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
                        "equity": bal,
                    })
                    if len(_state["equity_history"]) > MAX_EQUITY_POINTS:
                        _state["equity_history"] = _state["equity_history"][-MAX_EQUITY_POINTS:]

            elif topic == "trade":
                data["timestamp"] = time.strftime("%Y-%m-%d %H:%M:%S")
                _state["recent_trades"].append(data)
                if len(_state["recent_trades"]) > MAX_EVENTS:
                    _state["recent_trades"] = _state["recent_trades"][-MAX_EVENTS:]

                # Update strategy stats
                strat_name = data.get("strategy", "")
                if strat_name not in _state["strategies"]:
                    _state["strategies"][strat_name] = {"active": True, "trades": 0, "pnl": 0.0, "wins": 0}
                s = _state["strategies"][strat_name]
                s["trades"] = s.get("trades", 0) + 1
                pnl = data.get("realized_pnl", 0) or data.get("pnl", 0) or 0
                s["pnl"] = s.get("pnl", 0) + pnl
                if pnl > 0:
                    s["wins"] = s.get("wins", 0) + 1

            elif topic == "signal":
                data["timestamp"] = time.strftime("%Y-%m-%d %H:%M:%S")
                _state["recent_signals"].append(data)
                if len(_state["recent_signals"]) > MAX_EVENTS:
                    _state["recent_signals"] = _state["recent_signals"][-MAX_EVENTS:]


# Start ZMQ listener once on import
_zmq_thread = threading.Thread(target=_zmq_listener, daemon=True)
_zmq_thread.start()


# ── .env helpers ─────────────────────────────────────────────────────────────

# Settings keys exposed to the frontend, mapped to .env variable names
_SETTINGS_MAP = {
    "TRADE_AMOUNT_USDC": "MAX_POSITION_SIZE_USD",
    "MAX_POSITION_PER_MARKET": "MAX_POSITION_SIZE_USD",
    "MAX_TOTAL_EXPOSURE": "MAX_POSITION_SIZE_USD",
    "KELLY_FRACTION": "KELLY_FRACTION",
    "DRY_RUN": "DRY_RUN",
    "MAX_DRAWDOWN_PCT": "MAX_DRAWDOWN_PCT",
    "MAX_DAILY_LOSS_USDC": "DAILY_LOSS_LIMIT_USD",
    "MAX_OPEN_POSITIONS": "MAX_CONSECUTIVE_LOSSES",
    "MIN_MARKET_LIQUIDITY": "MIN_MARKET_LIQUIDITY",
    "ARB_MIN_PROFIT_PCT": "ARB_MIN_PROFIT_PCT",
    "ARB_SCAN_INTERVAL": "TICK_INTERVAL_SECONDS",
    "MM_SPREAD_MARGIN": "MM_SPREAD_MARGIN",
    "MM_ORDER_SIZE": "MM_ORDER_SIZE",
    "MM_MAX_INVENTORY": "MM_MAX_INVENTORY",
    "NEWS_CHECK_INTERVAL": "NEWS_CHECK_INTERVAL",
    "NEWS_CONFIDENCE_THRESHOLD": "HIGH_CONFIDENCE_THRESHOLD",
    "WHALE_MIN_TRADE_SIZE": "WHALE_MIN_TRADE_SIZE",
    "WHALE_COPY_RATIO": "WHALE_COPY_RATIO",
    "WHALE_WALLETS": "WHALE_WALLETS",
}

# Default values for settings the frontend expects
_SETTINGS_DEFAULTS = {
    "TRADE_AMOUNT_USDC": "50",
    "MAX_POSITION_PER_MARKET": "100",
    "MAX_TOTAL_EXPOSURE": "500",
    "KELLY_FRACTION": "0.25",
    "DRY_RUN": "true",
    "MAX_DRAWDOWN_PCT": "10",
    "MAX_DAILY_LOSS_USDC": "100",
    "MAX_OPEN_POSITIONS": "5",
    "MIN_MARKET_LIQUIDITY": "1000",
    "ARB_MIN_PROFIT_PCT": "1.0",
    "ARB_SCAN_INTERVAL": "10",
    "MM_SPREAD_MARGIN": "0.02",
    "MM_ORDER_SIZE": "25",
    "MM_MAX_INVENTORY": "200",
    "NEWS_CHECK_INTERVAL": "60",
    "NEWS_CONFIDENCE_THRESHOLD": "0.95",
    "WHALE_MIN_TRADE_SIZE": "500",
    "WHALE_COPY_RATIO": "0.10",
    "WHALE_WALLETS": "",
}


def _read_env():
    """Read .env file into a dict."""
    env = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


def _write_env(updates: dict):
    """Update .env values, preserving comments and order."""
    if not ENV_FILE.exists():
        return

    lines = ENV_FILE.read_text(encoding="utf-8").splitlines()
    updated_keys = set()
    new_lines = []

    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in updates:
                new_lines.append(f"{key}={updates[key]}")
                updated_keys.add(key)
                continue
        new_lines.append(line)

    # Append any new keys not found in existing file
    for key, val in updates.items():
        if key not in updated_keys:
            new_lines.append(f"{key}={val}")

    ENV_FILE.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def _get_settings_for_frontend():
    """Return settings dict with frontend keys."""
    env = _read_env()
    result = {}
    for fe_key, env_key in _SETTINGS_MAP.items():
        val = env.get(env_key, _SETTINGS_DEFAULTS.get(fe_key, ""))
        # Convert fractional drawdown to percentage for display
        if fe_key == "MAX_DRAWDOWN_PCT":
            try:
                f = float(val)
                if f < 1:
                    val = str(int(f * 100))
            except ValueError:
                pass
        result[fe_key] = val
    return result


def _save_settings_from_frontend(data: dict):
    """Map frontend keys back to .env keys and write."""
    updates = {}
    for fe_key, val in data.items():
        env_key = _SETTINGS_MAP.get(fe_key)
        if not env_key:
            continue
        # Convert percentage back to fraction for drawdown
        if fe_key == "MAX_DRAWDOWN_PCT":
            try:
                f = float(val)
                if f > 1:
                    val = str(f / 100)
            except ValueError:
                pass
        updates[env_key] = str(val)
    _write_env(updates)


# ── HTML Dashboard ───────────────────────────────────────────────────────────

_dashboard_html_path = PROJECT_ROOT / "app" / "dashboard.html"


def _get_dashboard_html():
    """Load dashboard HTML from file, or return fallback."""
    if _dashboard_html_path.exists():
        return _dashboard_html_path.read_text(encoding="utf-8")
    return "<html><body><h1>dashboard.html not found</h1></body></html>"


# ── HTTP Handler ─────────────────────────────────────────────────────────────

class DashboardHandler(BaseHTTPRequestHandler):
    """Serves the dashboard HTML and the JSON API."""

    def _send_json(self, data, status=200):
        payload = json.dumps(data)
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(payload.encode())

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length))

    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        if self.path == "/api/status":
            with _state_lock:
                risk = _state.get("risk", {})
                paper = _state.get("paper", {})
                live_pos = _state.get("positions", {})
                equity = risk.get("current_balance", 0) or paper.get("balance", 0)
                total_pnl = risk.get("daily_pnl", 0)
                # Count positions from paper or live mode
                open_pos = paper.get("open_positions", 0)
                if not open_pos and isinstance(live_pos, dict):
                    open_pos = live_pos.get("position_count", 0)
                total_trades = risk.get("total_trades", 0)
                tick = _state["tick"]
                running = _state["running"]
                connected = _state["connected"]

            uptime = int(time.time() - _uptime_start)
            dry_run = _read_env().get("DRY_RUN", "true").lower() in ("true", "1", "yes")
            mode = _read_env().get("TRADING_MODE", "dry_run")

            bot_alive = _bot_is_running()
            self._send_json({
                "running": bot_alive or (running and connected),
                "dry_run": mode in ("dry_run", "paper"),
                "mode": mode,
                "equity": equity,
                "total_pnl": total_pnl,
                "total_trades": total_trades,
                "open_positions": open_pos,
                "cycles": tick,
                "uptime_seconds": uptime,
            })

        elif self.path == "/api/equity":
            with _state_lock:
                data = list(_state["equity_history"])
            self._send_json(data)

        elif self.path == "/api/strategies":
            with _state_lock:
                strats = {}
                for name, s in _state["strategies"].items():
                    trades = s.get("trades", 0)
                    wins = s.get("wins", 0)
                    strats[name] = {
                        "active": s.get("active", False),
                        "trades": trades,
                        "pnl": round(s.get("pnl", 0), 4),
                        "win_rate": wins / trades if trades > 0 else 0.0,
                    }
            self._send_json(strats)

        elif self.path == "/api/positions":
            with _state_lock:
                paper = _state.get("paper", {})
                paper_positions = paper.get("positions", {})
                live_positions = _state.get("positions", {})

            result = []
            # Paper mode positions
            for tid, p in paper_positions.items():
                result.append({
                    "token": tid[:20] + "..." if len(tid) > 20 else tid,
                    "side": "YES",
                    "size": p.get("quantity", 0),
                    "entry": p.get("avg_entry", 0),
                    "current": p.get("avg_entry", 0),
                    "pnl": p.get("realized_pnl", 0),
                })
            # Live/selenium mode positions (from PositionTracker)
            if not result and isinstance(live_positions, dict):
                for p in live_positions.get("positions", []):
                    result.append({
                        "token": p.get("token", ""),
                        "side": "YES",
                        "size": p.get("size", 0),
                        "entry": p.get("avg_price", 0),
                        "current": p.get("avg_price", 0),
                        "pnl": 0.0,
                    })
            self._send_json(result)

        elif self.path == "/api/risk":
            with _state_lock:
                risk = dict(_state.get("risk", {}))
            env = _read_env()
            try:
                max_dd = float(env.get("MAX_DRAWDOWN_PCT", "0.10"))
                if max_dd < 1:
                    max_dd *= 100
            except ValueError:
                max_dd = 10
            try:
                max_daily = float(env.get("DAILY_LOSS_LIMIT_USD", "100"))
            except ValueError:
                max_daily = 100

            self._send_json({
                "drawdown_pct": round(risk.get("drawdown_pct", 0) * 100, 2),
                "max_drawdown_pct": max_dd,
                "daily_pnl": round(risk.get("daily_pnl", 0), 2),
                "max_daily_loss": max_daily,
                "consecutive_losses": risk.get("consecutive_losses", 0),
                "kill_switch": risk.get("is_killed", False),
                "peak_equity": round(risk.get("peak_balance", 0), 2),
            })

        elif self.path == "/api/trades":
            with _state_lock:
                trades = list(_state["recent_trades"])
            result = []
            for t in trades:
                # Prefer readable name: question > slug > condition_id
                market_name = (
                    t.get("market_question")
                    or t.get("market_slug")
                    or t.get("market", t.get("token", ""))
                )
                result.append({
                    "timestamp": t.get("timestamp", t.get("_ts", "")),
                    "strategy": t.get("strategy", ""),
                    "market": market_name[:40],
                    "side": t.get("side", ""),
                    "size": t.get("size_usd", 0),
                    "price": t.get("price", 0),
                    "pnl": t.get("realized_pnl", 0) or t.get("pnl", 0) or 0,
                })
            self._send_json(result)

        elif self.path == "/api/settings":
            self._send_json(_get_settings_for_frontend())

        elif self.path in ("/", "/index.html"):
            html = _get_dashboard_html()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html.encode())

        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == "/api/settings":
            data = self._read_body()
            _save_settings_from_frontend(data)
            self._send_json({"message": "Instellingen opgeslagen! Herstart de bot om te activeren."})

        elif self.path == "/api/bot/start":
            result = _start_bot()
            self._send_json(result)

        elif self.path == "/api/bot/stop":
            result = _stop_bot()
            self._send_json(result)

        elif self.path == "/api/strategy/toggle":
            data = self._read_body()
            name = data.get("name", "")
            with _state_lock:
                if name in _state["strategies"]:
                    _state["strategies"][name]["active"] = not _state["strategies"][name]["active"]
            self._send_json({"ok": True})

        else:
            self.send_error(404)

    def log_message(self, format, *args):
        """Suppress default request logging to keep console clean."""
        pass
