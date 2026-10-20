# Tests

These are not run by `run_backtest.py`. Run them yourself:

| Command | What it does |
|---|---|
| `python tests/strategy_tests/run_strategy_tests.py` | Comparison table (one setting changed at a time from the baseline) plus integrity checks. Writes `outputs/strategy_tests/` |
| `python tests/factor_tests/run_factor_tests.py` | Factor tests (IC, quintile spreads, stability). To be added; in-sample data only |
