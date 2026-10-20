# Live / execution framework (to be added)

This folder will hold the daily execution engine. The engine turns `target_weights.csv` into a
daily account and applies these rules:
- board lots
- minimum commission
- T+2 settlement
- liquidity (ADV) limits
- corporate actions

**Input.** The input is `outputs/<run>/target_weights.csv`, which `run_backtest.py` writes. Its columns are
`signal_date, execution_date, ticker, weight`.
