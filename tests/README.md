# Tests

These are not run by `run_backtest.py`. Run them yourself:

| Command | What it does |
|---|---|
| `python tests/strategy_tests/run_strategy_tests.py` | Strategy selection on 2016–2020 data only: 45 configurations (K 3/4/5 × weights EW / IV yearly / IV monthly / IV weekly / MV × top 20/25/30%, 3-year lookback). Prints the matrices, the ranking, the effect of each setting, cost and neighbour robustness, significance against the STI and the equal-weight universe, turnover and integrity checks. Takes about 4 minutes |
| `python tests/execution_tests/run_execution_tests.py` | Fangling's 30 synthetic tests of the execution engine (accounting, lots, fees, T+2, dividends, splits, delisting, no look-ahead), plus a check that the real-data run reproduces the frozen final run FINAL_100K_DIV14_V1 |
| `python tests/factor_tests/run_factor_tests.py` | Factor tests (IC, quintile spreads, stability). To be added; in-sample data only |
