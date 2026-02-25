"""
Polymarket Bot — Desktop App met ingebouwde simulatie.

Klik START → bot begint DIRECT te draaien met gesimuleerde markten.
Je ziet live: trades verschijnen, equity beweegt, strategieën scoren.

Geen API keys nodig — dit is een simulatie op echte strategie-logica.
Wil je later live gaan? Vul je .env in en zet SIMULATION=false.
"""
import sys
import os
import threading
import time
import json
import math
import random
import datetime as dt
import logging
from pathlib import Path
from collections import deque
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
logger = logging.getLogger('polybot')

DASHBOARD_PORT = 8050
DASHBOARD_HTML = ROOT / 'app' / 'dashboard.html'

# ─── Simulated Markets ──────────────────────────────────────
FAKE_MARKETS = [
    {'id': 'm1', 'q': 'Will BTC reach $150k by June 2026?', 'price': 0.35, 'vol': 0.008},
    {'id': 'm2', 'q': 'Will the Fed cut rates in March?', 'price': 0.62, 'vol': 0.006},
    {'id': 'm3', 'q': 'Will GPT-5 launch before July?', 'price': 0.45, 'vol': 0.010},
    {'id': 'm4', 'q': 'Will Spain win the World Cup?', 'price': 0.18, 'vol': 0.004},
    {'id': 'm5', 'q': 'Will Tesla stock hit $500?', 'price': 0.22, 'vol': 0.007},
    {'id': 'm6', 'q': 'US government shutdown in 2026?', 'price': 0.40, 'vol': 0.009},
    {'id': 'm7', 'q': 'Will Apple release AR glasses?', 'price': 0.55, 'vol': 0.005},
    {'id': 'm8', 'q': 'Will Ethereum flip Bitcoin?', 'price': 0.08, 'vol': 0.003},
]

# ─── Shared State ────────────────────────────────────────────
_lock = threading.Lock()
_bot_running = False
_bot_stop = threading.Event()
_bot_thread = None

_state = {
    'running': False, 'dry_run': True, 'started_at': None,
    'cycles': 0, 'uptime_seconds': 0,
    'total_pnl': 0.0, 'total_trades': 0,
    'open_positions': 0, 'equity': 1000.0,
}
_strategies = {
    'arbitrage':      {'active': True, 'trades': 0, 'pnl': 0.0, 'signals': 0, 'win_rate': 0.0, 'wins': 0},
    'market_maker':   {'active': True, 'trades': 0, 'pnl': 0.0, 'signals': 0, 'win_rate': 0.0, 'wins': 0},
    'news_driven':    {'active': True, 'trades': 0, 'pnl': 0.0, 'signals': 0, 'win_rate': 0.0, 'wins': 0},
    'whale_follower': {'active': True, 'trades': 0, 'pnl': 0.0, 'signals': 0, 'win_rate': 0.0, 'wins': 0},
}
_trades = deque(maxlen=200)
_equity_curve = deque(maxlen=1000)
_positions = []
_risk = {
    'kill_switch': False, 'drawdown_pct': 0.0, 'max_drawdown_pct': 10.0,
    'daily_pnl': 0.0, 'max_daily_loss': 25.0,
    'consecutive_losses': 0, 'peak_equity': 1000.0, 'current_equity': 1000.0,
}
_trade_counter = 0
_consec_losses = 0


# ─── Simulation Engine ──────────────────────────────────────
def _tick_markets():
    """Beweeg alle marktprijzen een stap."""
    for m in FAKE_MARKETS:
        move = random.gauss(0, m['vol'])
        m['price'] = max(0.02, min(0.98, m['price'] + move))


def _sim_arbitrage():
    """Zoek mispricing: als YES + NO afwijkt van 1.00."""
    signals = []
    for m in FAKE_MARKETS:
        no_price = 1.0 - m['price'] + random.gauss(0, 0.015)
        total = m['price'] + no_price
        if total < 0.97:  # mispricing gevonden
            profit = (1.0 - total) * 100
            signals.append({'market': m['q'], 'profit_pct': round(profit, 2), 'side': 'YES'})
    return signals


def _sim_market_maker():
    """Kijk of spread breed genoeg is om te quoten."""
    signals = []
    for m in FAKE_MARKETS:
        spread = abs(random.gauss(0, 0.03))
        if spread > 0.02:
            signals.append({'market': m['q'], 'spread': round(spread, 3), 'side': 'BOTH'})
    return signals


def _sim_news():
    """Simuleer nieuws-events."""
    if random.random() < 0.15:  # 15% kans per cycle
        m = random.choice(FAKE_MARKETS)
        direction = random.choice(['YES', 'NO'])
        confidence = round(random.uniform(0.6, 0.95), 2)
        if confidence > 0.7:
            return [{'market': m['q'], 'direction': direction, 'confidence': confidence, 'side': direction}]
    return []


def _sim_whale():
    """Simuleer whale detectie."""
    if random.random() < 0.10:  # 10% kans per cycle
        m = random.choice(FAKE_MARKETS)
        amount = round(random.uniform(500, 5000), 0)
        side = random.choice(['YES', 'NO'])
        return [{'market': m['q'], 'whale_amount': amount, 'side': side}]
    return []


def _execute_signal(strat_name, signal):
    """Simuleer trade executie en bereken P&L."""
    global _trade_counter, _consec_losses

    # Simuleer realistische P&L
    # Arbitrage: meestal kleine winst
    # Market maker: veel kleine winsten, af en toe verlies
    # News: grotere swings
    # Whale: middelmatig
    pnl_profiles = {
        'arbitrage':      (0.8,  0.60, 1.5),   # (gem, std, bias naar winst)
        'market_maker':   (0.3,  0.40, 1.2),
        'news_driven':    (1.2,  2.50, 0.9),
        'whale_follower': (0.6,  1.20, 1.1),
    }
    mean, std, bias = pnl_profiles.get(strat_name, (0.5, 1.0, 1.0))
    raw_pnl = random.gauss(mean * bias, std)
    pnl = round(raw_pnl, 2)
    won = pnl > 0

    _trade_counter += 1

    trade = {
        'id': _trade_counter,
        'timestamp': dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'strategy': strat_name,
        'market': signal.get('market', '?'),
        'side': signal.get('side', 'YES'),
        'amount': round(random.uniform(5, 30), 2),
        'price': round(random.uniform(0.10, 0.90), 3),
        'pnl': pnl,
        'status': 'SIM',
    }

    with _lock:
        _trades.append(trade)
        s = _strategies[strat_name]
        s['trades'] += 1
        s['pnl'] = round(s['pnl'] + pnl, 2)
        s['signals'] += 1
        if won:
            s['wins'] += 1
            _consec_losses = 0
        else:
            _consec_losses += 1
        s['win_rate'] = round(s['wins'] / s['trades'], 2) if s['trades'] > 0 else 0.0

    return pnl


def _update_state():
    """Update alle dashboard state na elke cycle."""
    with _lock:
        total_pnl = sum(s['pnl'] for s in _strategies.values())
        total_trades = sum(s['trades'] for s in _strategies.values())
        equity = 1000.0 + total_pnl

        _state['total_pnl'] = round(total_pnl, 2)
        _state['total_trades'] = total_trades
        _state['equity'] = round(equity, 2)
        _state['open_positions'] = len(_positions)

        _equity_curve.append({
            'time': dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'equity': round(equity, 2),
        })

        peak = _risk['peak_equity']
        if equity > peak:
            _risk['peak_equity'] = equity
            peak = equity
        dd = ((peak - equity) / peak * 100) if peak > 0 else 0
        _risk['drawdown_pct'] = round(dd, 1)
        _risk['current_equity'] = round(equity, 2)
        _risk['daily_pnl'] = round(total_pnl, 2)  # simplified
        _risk['consecutive_losses'] = _consec_losses

        if dd >= _risk['max_drawdown_pct']:
            _risk['kill_switch'] = True


def _run_simulation():
    """Hoofd-simulatie loop — draait in achtergrond-thread."""
    global _bot_running

    logger.info('Simulatie gestart')
    start = time.time()

    with _lock:
        _state['started_at'] = dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        _state['running'] = True

    cycle = 0
    while not _bot_stop.is_set():
        cycle += 1
        with _lock:
            _state['cycles'] = cycle
            _state['uptime_seconds'] = int(time.time() - start)

        # Beweeg markten
        _tick_markets()

        # Draai elke actieve strategie
        scanners = {
            'arbitrage': _sim_arbitrage,
            'market_maker': _sim_market_maker,
            'news_driven': _sim_news,
            'whale_follower': _sim_whale,
        }

        for strat_name, scanner in scanners.items():
            with _lock:
                active = _strategies[strat_name]['active']
            if not active:
                continue

            signals = scanner()
            for sig in signals[:2]:  # max 2 per strategie per cycle
                _execute_signal(strat_name, sig)

        # Update posities (simuleer open/close)
        _sim_positions()

        # Update dashboard state
        _update_state()

        # Check kill switch
        with _lock:
            if _risk['kill_switch']:
                logger.warning('KILL SWITCH — simulatie gestopt')
                break

        # Wacht 2 seconden tussen cycles (snel genoeg om actie te zien)
        for _ in range(2):
            if _bot_stop.is_set():
                break
            time.sleep(1)

    with _lock:
        _state['running'] = False
        _bot_running = False
    logger.info('Simulatie gestopt')


def _sim_positions():
    """Simuleer open/close posities."""
    global _positions

    with _lock:
        # Sluit posities die in winst staan
        new_pos = []
        for p in _positions:
            m = next((x for x in FAKE_MARKETS if x['id'] == p.get('_mid')), None)
            if m:
                p['current'] = round(m['price'], 3)
                p['pnl'] = round((p['current'] - p['entry']) * p['size'] / p['entry'], 2)
                if abs(p['pnl']) > 3 or random.random() < 0.1:
                    continue  # positie gesloten
                new_pos.append(p)
            else:
                new_pos.append(p)

        # Open nieuwe posities
        if len(new_pos) < 4 and random.random() < 0.3:
            m = random.choice(FAKE_MARKETS)
            new_pos.append({
                'token': m['q'][:30],
                'side': random.choice(['YES', 'NO']),
                'size': round(random.uniform(10, 40), 2),
                'entry': round(m['price'], 3),
                'current': round(m['price'], 3),
                'pnl': 0.0,
                '_mid': m['id'],
            })

        _positions = new_pos
        _state['open_positions'] = len(_positions)


def start_bot():
    global _bot_thread, _bot_running
    with _lock:
        if _state['running']:
            return {'status': 'already_running'}
    _bot_stop.clear()
    _bot_running = True
    _bot_thread = threading.Thread(target=_run_simulation, daemon=True)
    _bot_thread.start()
    return {'status': 'started'}


def stop_bot():
    _bot_stop.set()
    with _lock:
        _state['running'] = False
    return {'status': 'stopping'}


# ─── HTTP Server ────────────────────────────────────────────
class AppHandler(SimpleHTTPRequestHandler):

    def do_GET(self):
        p = urlparse(self.path).path
        if p in ('/', '/dashboard'):
            self._html()
        elif p == '/api/status':
            with _lock: self._json(dict(_state))
        elif p == '/api/trades':
            with _lock: self._json(list(_trades)[-30:])
        elif p == '/api/equity':
            with _lock: self._json(list(_equity_curve))
        elif p == '/api/strategies':
            with _lock:
                clean = {k: {sk: sv for sk, sv in v.items() if not sk.startswith('_') and sk != 'wins'}
                         for k, v in _strategies.items()}
                self._json(clean)
        elif p == '/api/positions':
            with _lock:
                clean = [{k: v for k, v in pos.items() if not k.startswith('_')} for pos in _positions]
                self._json(clean)
        elif p == '/api/risk':
            with _lock: self._json(dict(_risk))
        elif p == '/api/settings':
            self._json(self._read_env())
        else:
            self.send_error(404)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_POST(self):
        p = urlparse(self.path).path
        body = self._body()
        if p == '/api/bot/start':
            self._json(start_bot())
        elif p == '/api/bot/stop':
            self._json(stop_bot())
        elif p == '/api/strategy/toggle':
            name = body.get('name', '')
            if name in _strategies:
                with _lock:
                    _strategies[name]['active'] = not _strategies[name]['active']
            self._json({'ok': True})
        elif p == '/api/settings':
            self._json(self._save_env(body))
        else:
            self.send_error(404)

    def _body(self):
        n = int(self.headers.get('Content-Length', 0))
        return json.loads(self.rfile.read(n)) if n else {}

    def _html(self):
        try:
            data = DASHBOARD_HTML.read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except FileNotFoundError:
            self.send_error(500)

    def _json(self, obj):
        data = json.dumps(obj).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _read_env(self):
        p = ROOT / '.env'
        r = {}
        if p.exists():
            for line in p.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, v = line.split('=', 1)
                    r[k.strip()] = '••••••••' if ('PRIVATE' in k or 'SECRET' in k) else v.strip()
        return r

    def _save_env(self, new):
        p = ROOT / '.env'
        protected = {'PRIVATE_KEY', 'FUNDER_ADDRESS', 'SIGNATURE_TYPE'}
        lines = p.read_text().splitlines(True) if p.exists() else []
        existing, out = set(), []
        for line in lines:
            s = line.strip()
            if s and not s.startswith('#') and '=' in s:
                k = s.split('=', 1)[0].strip()
                existing.add(k)
                out.append(f'{k}={new[k]}\n' if k in new and k not in protected else line)
            else:
                out.append(line)
        for k, v in new.items():
            if k not in existing and k not in protected:
                out.append(f'{k}={v}\n')
        p.write_text(''.join(out))
        return {'saved': True, 'message': 'Opgeslagen! Stop en start de bot om te activeren.'}

    def log_message(self, *a):
        pass


# ─── Main ───────────────────────────────────────────────────
def main():
    # Force UTF-8 output on Windows
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')

    print()
    print('  ╔══════════════════════════════════════════╗')
    print('  ║       ⚡ POLYMARKET BOT                  ║')
    print('  ║       SIMULATIE MODUS                    ║')
    print('  ╚══════════════════════════════════════════╝')
    print()
    print('  Klik START in het dashboard om de bot te starten.')
    print('  Je ziet direct trades, equity, en strategieën bewegen.')
    print()

    srv = HTTPServer(('127.0.0.1', DASHBOARD_PORT), AppHandler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    url = f'http://127.0.0.1:{DASHBOARD_PORT}'
    print(f'  Dashboard: {url}')
    print()

    try:
        import webview
        print('  App opent...')
        webview.create_window('Polymarket Bot', url,
            width=1400, height=900, min_size=(800, 600),
            resizable=True, text_select=True)
        webview.start()
    except ImportError:
        import webbrowser
        print('  Opent in je browser...')
        print('  Druk Ctrl+C om te stoppen.')
        webbrowser.open(url)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass

    stop_bot()
    srv.shutdown()
    print('\n  Gestopt.')


if __name__ == '__main__':
    main()
