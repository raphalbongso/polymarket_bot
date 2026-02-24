"""
Test je strategie ZONDER echt geld.

Gebruik:
    python scripts/test_strategie.py

Dit genereert nep-marktdata en laat zien hoe je strategie
zou presteren. Pas de instellingen hieronder aan.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
from backtesting.vectorized import VectorizedBacktester
from backtesting.event_based import EventBasedBacktester

# ============================================================
# INSTELLINGEN — PAS DEZE AAN
# ============================================================

STARTKAPITAAL = 1000        # hoeveel $ je begint
AANTAL_UREN = 500           # hoeveel uur aan data simuleren
TRANSACTIEKOSTEN = 0.001    # spread + gas per trade
MOMENTUM_WINDOW = 20        # hoe ver terugkijken (in uren)
SMA_KORT = 10               # korte moving average
SMA_LANG = 30               # lange moving average

# ============================================================


def maak_nep_data(n_uren):
    """Simuleer een prediction market prijs (0.05 - 0.95)."""
    np.random.seed(42)
    datums = pd.date_range('2025-01-01', periods=n_uren, freq='h')
    prijs = 0.5 + np.cumsum(np.random.normal(0, 0.005, n_uren))
    prijs = np.clip(prijs, 0.05, 0.95)
    return pd.Series(prijs, index=datums)


def test_momentum(prijzen):
    """Test momentum strategie."""
    print('=' * 50)
    print(f'MOMENTUM STRATEGIE (window={MOMENTUM_WINDOW})')
    print('=' * 50)

    bt = VectorizedBacktester(prijzen, TRANSACTIEKOSTEN, STARTKAPITAAL)
    bt.run_momentum(window=MOMENTUM_WINDOW)
    resultaat = bt.summary()

    print(f'  Start:           ${STARTKAPITAAL}')
    print(f'  Eind:            ${resultaat["final_equity"]}')
    print(f'  Rendement:       {resultaat["total_return_strategy"]*100:.2f}%')
    print(f'  Sharpe Ratio:    {resultaat["sharpe_ratio"]}')
    print(f'  Max Drawdown:    {resultaat["max_drawdown_pct"]}%')
    print(f'  Aantal trades:   {resultaat["n_trades"]}')
    print()
    return resultaat


def test_sma(prijzen):
    """Test SMA crossover strategie."""
    print('=' * 50)
    print(f'SMA CROSSOVER (kort={SMA_KORT}, lang={SMA_LANG})')
    print('=' * 50)

    bt = VectorizedBacktester(prijzen, TRANSACTIEKOSTEN, STARTKAPITAAL)
    bt.run_sma_crossover(short=SMA_KORT, long=SMA_LANG)
    resultaat = bt.summary()

    print(f'  Start:           ${STARTKAPITAAL}')
    print(f'  Eind:            ${resultaat["final_equity"]}')
    print(f'  Rendement:       {resultaat["total_return_strategy"]*100:.2f}%')
    print(f'  Sharpe Ratio:    {resultaat["sharpe_ratio"]}')
    print(f'  Max Drawdown:    {resultaat["max_drawdown_pct"]}%')
    print(f'  Aantal trades:   {resultaat["n_trades"]}')
    print()
    return resultaat


def zoek_beste_momentum(prijzen):
    """Probeer alle windows en vind de beste."""
    print('=' * 50)
    print('OPTIMALISATIE: Beste momentum window zoeken...')
    print('=' * 50)

    bt = VectorizedBacktester(prijzen, TRANSACTIEKOSTEN, STARTKAPITAAL)
    windows = [5, 10, 15, 20, 30, 40, 50]
    beste_w, beste_r = bt.optimize_momentum(windows)

    print(f'  Beste window:    {beste_w} uur')
    print(f'  Rendement:       {beste_r["total_return_strategy"]*100:.2f}%')
    print(f'  Sharpe:          {beste_r["sharpe_ratio"]}')
    print()


def test_event_based(prijzen):
    """Nauwkeurige bar-by-bar test (langzamer, realistischer)."""
    print('=' * 50)
    print('EVENT-BASED BACKTEST (realistisch)')
    print('=' * 50)

    signalen = np.sign(
        prijzen.diff().rolling(MOMENTUM_WINDOW).mean()
    ).fillna(0).astype(int)

    bt = EventBasedBacktester(
        prijzen,
        initial_capital=STARTKAPITAAL,
        fixed_cost=0.007,     # gas per trade
        prop_cost=0.001,      # spread
    )
    resultaat = bt.run(signalen)
    samenvatting = bt.summary(resultaat)

    print(f'  Start:           ${samenvatting["initial_capital"]}')
    print(f'  Eind:            ${samenvatting["final_equity"]}')
    print(f'  Rendement:       {samenvatting["total_return_pct"]}%')
    print(f'  Aantal trades:   {samenvatting["n_trades"]}')
    print(f'  Max Drawdown:    {samenvatting["max_drawdown_pct"]}%')
    print()


if __name__ == '__main__':
    print()
    print('  POLYMARKET BOT — STRATEGIE TESTER')
    print('  Simuleert met nepdata, kost geen geld.')
    print()

    prijzen = maak_nep_data(AANTAL_UREN)
    print(f'  Data: {len(prijzen)} uur gesimuleerd')
    print(f'  Prijs range: {prijzen.min():.3f} - {prijzen.max():.3f}')
    print()

    test_momentum(prijzen)
    test_sma(prijzen)
    zoek_beste_momentum(prijzen)
    test_event_based(prijzen)

    print('Klaar! Pas de instellingen bovenaan aan en run opnieuw.')
