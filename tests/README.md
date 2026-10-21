# Tests

These are not run by `run_backtest.py`. Run them yourself:

| Command | What it does |
|---|---|
| `python tests/strategy_tests/run_strategy_tests.py` | Full grid of 90 configurations, with no baseline: K 2–6 × lookback 3/5y × weights EW/IV/MV × top 20/25/30%. Prints matrices per K for 2016–20, 2016–18, 2019–20, EVAL and LIVE, a ranking and the median effect of each setting, then runs integrity checks. Takes about 5–6 minutes. Writes to `outputs/strategy_tests/` |
| `python tests/execution_tests/run_execution_tests.py` | Fangling's 30 synthetic tests of the execution engine (accounting, lots, fees, T+2, dividends, splits, delisting, no look-ahead), plus a check that the real-data run reproduces the frozen final run FINAL_100K_DIV14_V1 |
| `python tests/factor_tests/run_factor_tests.py` | Factor tests (IC, quintile spreads, stability). To be added; in-sample data only |
