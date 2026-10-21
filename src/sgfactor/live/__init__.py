"""Live / execution framework: weekly target weights -> daily share-and-cash account.

The engine (engine.py, metrics.py, risk.py, dividends.py) is fangling's Backtest-Framework-Top4
(commit 4faa7f2), ported unchanged. run.py connects it to this project's data and targets.

Rules (config/execution.yaml): board lots of 100, 1% cash reserve, fills capped at 10% of the
day's volume and of lagged 20-day ADV, orders live 5 sessions, commission 5 bp (min SGD 5) +
4 bp market fees + 10 bp slippage, T+2 settlement, source cash dividends paid ex-date + 14 days.
Trades at the daily close (proxy); this is a simulation, not a tick-level fill model.
"""
from .run import run_execution

__all__ = ["run_execution"]
