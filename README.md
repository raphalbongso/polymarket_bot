# Polymarket Trading Bot

Production-grade algorithmic trading bot for [Polymarket](https://polymarket.com) prediction markets implementing 4 strategies:

1. **Arbitrage** — Detect mispricings where YES + NO ≠ $1.00
2. **Market Making** — Earn the bid-ask spread with inventory management
3. **News-Driven AI** — React to breaking news faster than the market
4. **Whale-Following** — Copy trades from proven successful wallets

Built on concepts from *Python for Algorithmic Trading* (Yves Hilpisch, O'Reilly): Kelly Criterion, risk management, ML pipelines, ZeroMQ monitoring, vectorized backtesting.

## Quick Start

```bash
# 1. Clone and install
git clone https://github.com/raphalbongso/polymarket_bot.git
cd polymarket_bot
pip install -r requirements.txt

# 2. Configure
cp .env.template .env
# Edit .env with your Polygon wallet private key

# 3. Run tests (no API key needed)
python run_tests.py

# 4. Start bot (DRY RUN mode — no real trades)
python scripts/run_bot.py

# 5. Monitor remotely (separate terminal)
python scripts/run_monitor.py --host localhost --port 5555
```

## Architecture

```
config/          Settings (immutable), API client factory
data/            Market fetcher, orderbook tracker, price history, whale tracker
strategies/      Base class + 4 strategy implementations
risk/            Kelly criterion, risk manager with kill switch
monitoring/      Structured logging, ZeroMQ pub/sub
bot/             Main orchestrator
scripts/         Entry points
tests/           Full test suite (55 tests)
```

### How It Works

```
                    ┌─────────────┐
                    │  Gamma API  │  Market discovery
                    └──────┬──────┘
                           │
┌──────────────────────────▼──────────────────────────┐
│                    Orchestrator                       │
│                                                       │
│   ┌─────────┐  ┌─────────┐  ┌────────┐  ┌────────┐ │
│   │Arbitrage│  │Market   │  │News    │  │Whale   │ │
│   │Strategy │  │Making   │  │Driven  │  │Follow  │ │
│   └────┬────┘  └────┬────┘  └───┬────┘  └───┬────┘ │
│        └─────┬──────┴──────────┬┴────────────┘      │
│              │    Signals      │                      │
│        ┌─────▼─────┐    ┌─────▼─────┐               │
│        │Risk Manager│    │  Kelly    │               │
│        │Kill Switch │    │ Criterion │               │
│        └─────┬─────┘    └─────┬─────┘               │
│              └────────┬───────┘                       │
│                       │                               │
│              ┌────────▼────────┐                     │
│              │  Execute Signal │                     │
│              │  (DRY_RUN gate) │                     │
│              └────────┬────────┘                     │
└───────────────────────┼─────────────────────────────┘
                        │
               ┌────────▼────────┐
               │  Polymarket     │
               │  CLOB API       │
               └─────────────────┘
```

## Strategies

### Arbitrage
Exploits the mathematical certainty that YES + NO must equal $1.00 at resolution. When the sum of best asks is below $1.00, buy both sides for a guaranteed profit.

### Market Making
Quotes on both sides of the orderbook to earn the bid-ask spread. Uses inventory-aware skew to avoid accumulating a dangerous one-sided position, and widens spreads during high volatility.

### News-Driven AI
Fetches breaking news headlines and analyzes them with an LLM (OpenAI) to predict market impact. Requires `NEWS_API_KEY` and `OPENAI_API_KEY` in `.env` — gracefully disables itself if missing.

### Whale-Following
Monitors large wallets via the Polymarket Data API. Copies trades above $1,000 with a 5-minute decay window. Multiple whales trading the same direction boosts signal confidence.

## Risk Management

### Kelly Criterion Position Sizing
Three layers of protection:
- **Kelly formula**: `f* = (bp - q) / b` calculates the theoretically optimal bet fraction
- **Fractional Kelly** (default 25%): reduces variance by ~75% while capturing ~75% of growth
- **Absolute cap**: hard dollar limit per position (`MAX_POSITION_SIZE_USD`)

### One-Way Kill Switch
A `threading.Event` that, once triggered, **cannot be reset** without restarting the bot. Three independent triggers:

| Trigger | Default | What happens |
|---------|---------|-------------|
| Max drawdown | 10% | Kills if portfolio drops 10% from peak |
| Daily loss limit | $100 | Kills if daily losses exceed $100 |
| Consecutive losses | 5 | Kills after 5 losing trades in a row |

## Safety Features

- **DRY_RUN=true by default** — no real trades until explicitly enabled
- **Immutable settings** — frozen dataclass prevents accidental config mutation
- **Bounded memory** — all buffers use `deque(maxlen=N)`, safe for weeks of runtime
- **Graceful degradation** — missing `pyzmq`, `openai`, or `newsapi` won't crash the bot
- **Single execution chokepoint** — only `orchestrator._execute_signal()` can place orders

## Configuration

All settings are loaded from `.env` (see `.env.template`):

| Variable | Default | Description |
|----------|---------|-------------|
| `POLYMARKET_PRIVATE_KEY` | — | Your Polygon wallet private key |
| `DRY_RUN` | `true` | Set to `false` for live trading |
| `MAX_DRAWDOWN_PCT` | `0.10` | Kill switch at 10% drawdown |
| `DAILY_LOSS_LIMIT_USD` | `100.0` | Kill switch at $100 daily loss |
| `MAX_CONSECUTIVE_LOSSES` | `5` | Kill switch after 5 consecutive losses |
| `MAX_POSITION_SIZE_USD` | `50.0` | Hard cap per position |
| `KELLY_FRACTION` | `0.25` | Quarter-Kelly (conservative) |
| `NEWS_API_KEY` | — | Optional: enables news strategy |
| `OPENAI_API_KEY` | — | Optional: enables LLM analysis |
| `WHALE_WALLETS` | — | Optional: comma-separated wallet addresses |
| `ZMQ_PUB_PORT` | `5555` | ZeroMQ monitoring port |

## Monitoring

The bot publishes events via ZeroMQ on topics: `trade`, `signal`, `risk`, `heartbeat`, `kill`.

```bash
# Monitor all events
python scripts/run_monitor.py

# Monitor specific topics
python scripts/run_monitor.py --topics trade,risk,kill

# Monitor remote bot
python scripts/run_monitor.py --host 192.168.1.100 --port 5555
```

## Testing

```bash
python run_tests.py
```

55 tests cover all modules — settings, client factory, market fetcher, orderbook tracker, price history, whale tracker, all 4 strategies, Kelly criterion, risk manager, orchestrator, and ZMQ monitoring. All tests use mocks — no network access or API keys required.

## Warnings

1. **Not financial advice.** You can lose your entire investment.
2. **Start with DRY_RUN=true** and small amounts.
3. **Never commit `.env`** — your private key = your funds.
4. **Arbitrage is competitive** — professional bots with co-located servers dominate.
5. **Quarter-Kelly maximum** — full Kelly is too volatile for prediction markets.

## License

MIT
