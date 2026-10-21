# Tests

These are not run by `run_backtest.py`. Run them yourself:

| Command | What it does |
|---|---|
| `python tests/run_all_tests.py` | Runs the three stages below in research order: factor tests (2011–15), then strategy selection (2016–20), then the execution engine. Prints a PASS/FAIL summary. Use `--skip factor` to leave a stage out. Takes about 4 minutes |
| `python tests/strategy_tests/run_strategy_tests.py` | Strategy selection on 2016–2020 data only. It runs 24 configurations: K 3/4 × weights EW / IV yearly / IV monthly / IV weekly × top 20/25/30%, with a 3-year lookback. It prints the matrices, the ranking, the effect of each setting, cost and neighbour robustness, significance against the STI and the equal-weight universe, turnover and integrity checks. Nothing after 2020 is shown. Takes about 2 minutes |
| `python tests/execution_tests/run_execution_tests.py` | Fangling's 30 synthetic tests of the execution engine (accounting, lots, fees, T+2, dividends, splits, delisting, no look-ahead), plus a check that the real-data run reproduces the frozen final run FINAL_100K_DIV14_V1 |
| `python tests/factor_tests/run_factor_tests.py` | Single-factor tests for 2011–2015, from Ganjunhui's branch `research/sg-single-factor-independent`. Covers Rank IC and ICIR, long-short, quintiles, Top-20 excess return, HAC tests, yearly robustness, factor correlations and composites, plus 21 figures. It also checks that the branch's frozen results are reproduced exactly (27 / 27 files). See `tests/factor_tests/README.md`. Takes about 1–2 minutes |
