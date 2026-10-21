# Guide: running the project from scratch

This guide takes you from a fresh computer to every result in the project. For each step it shows
the command, the expected output and the conclusion to draw from it. The tests (steps 3–5) are
optional and run separately from the main program (step 2).

| Step | Command | Time | Answers |
|---|---|---|---|
| 1 | set up the environment | 2 min | – |
| 2 | `python run_backtest.py` | 30 s | how the frozen strategy performs (main result, course metrics) |
| 3 | `python tests/factor_tests/run_factor_tests.py` | 1–2 min | which style factors carry a premium (2011–15) |
| 4 | `python tests/strategy_tests/run_strategy_tests.py` | 2 min | why this configuration (2016–20) |
| 5 | `python tests/execution_tests/run_execution_tests.py` | 30 s | is the execution engine correct |
| all tests | `python tests/run_all_tests.py` | 4 min | steps 3–5 in order, with a PASS/FAIL summary |

## 1. Environment

**Requirements:**
- Python 3.10–3.13 (developed on 3.13).
- About 200 MB of disk space.
- No internet access is needed after `pip install`: all data are in `data/`.

**Get the code.** The repository is private.
- **GitHub Desktop:** File → Clone repository → `sg-adaptive-multifactor`.
- **Command line:** `git clone <repo url>`.
- **Without git:** unzip `sg-adaptive-multifactor.zip`.

**Create an environment and install the packages.** Run these in the project folder:

```bash
python -m venv .venv
# Windows (cmd / PowerShell):  .venv\Scripts\activate
# macOS / Linux:               source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt          # numpy, pandas, scipy, pyyaml, matplotlib
```

Conda works too: `conda create -n sgfactor python=3.12`, then `conda activate sgfactor`, then
`pip install -r requirements.txt`.

**PyCharm:**
1. Open the project folder.
2. Settings → Project → Python Interpreter → Add Interpreter → Virtualenv → New, base Python 3.10–3.13.
3. Open the Terminal tab (it activates the interpreter) and run `pip install -r requirements.txt`.
4. Run `run_backtest.py` with the green arrow, or type the commands below in the Terminal.

All commands are run from the project root folder (the one containing `run_backtest.py`).

| Error | Fix |
|---|---|
| `ModuleNotFoundError: No module named 'yaml'` (or `pandas`, …) | the environment is not active or the packages are not installed: activate it and rerun `pip install -r requirements.txt` |
| `FileNotFoundError: data/...` | you are not in the project root; `cd` into it |
| figures fail in the factor tests | run `python tests/factor_tests/run_factor_tests.py --no-plots`; all numbers are still produced |

## 2. Main program: the frozen strategy

```bash
python run_backtest.py
```

It runs the whole pipeline with the frozen configuration in `config/strategy.yaml`: **3 styles, inverse-volatility
weights re-estimated weekly, top 20%**.
1. **Part A.** Style scores, then weekly factor returns, the yearly choice of 3 styles, the weekly
   style weights, the composite score and the holdings. These give a weekly NAV net of 10 bp.
2. **Part B.** The same target weights are traded in a daily execution account, starting from
   SGD 100,000 in January 2021 and running to 2026-10-15. It models:
   - board lots;
   - minimum fees;
   - volume limits;
   - T+2 settlement;
   - dividends;
   - FX.

**Expected console output** (abridged):

```
SG_Adaptive_K3_IVweekly_Top20  (562 weeks 2016-01-08 .. 2026-10-09, cost 10 bp one-way)
period  series    ...  ann_return  ann_vol  sharpe  max_drawdown  calmar
   obs  strategy        0.2290      0.2270   1.0248   0.3518        0.6508
   obs  STI             0.0215      0.2046   0.2064   0.3206        0.0671
  eval  strategy        0.2453      0.1658   1.4088   0.1234        1.9886
  eval  STI             0.1728      0.1219   1.3703   0.1048        1.6493
Styles chosen each year:   2016 Momentum, Quality, Size ... 2026 Size, Momentum, Quality
LIVE window ... strategy -0.0619   STI -0.0466
Part B: daily execution account ...
  EVAL 2021-01-08 .. 2026-09-30: SGD 100,000 -> 285,647  CAGR 20.1%, max drawdown 14.4%, Sharpe (daily) 1.36
  LIVE 2026-10-01 close .. 2026-10-15: SGD 283,634 -> 266,334  return -6.10%   | STI -4.66%
Course performance metrics (execution account; 09_performance_metrics.csv):
  annual_return, sharpe_ratio_rf0, max_drawdown, win_rate_position_trades, annual_volatility,
  drawdown_count, number_of_trades_fills, avg_holding_period_days, profit_per_trade_sgd, ...
```

The results are written to `outputs/SG_Adaptive_K3_IVweekly_Top20/`. The files to submit or present:

| File | Use |
|---|---|
| `09_performance_metrics.csv` | course performance-metric table: TEST period (October 2026) and EVAL 2021–26 for reference |
| `10_portfolio_assets.csv`, `10_portfolio_daily_close.csv` | required CSV: assets in the portfolio and their daily closing prices |
| `06_performance_summary.csv`, `07_calendar_year_returns.csv` | backtest by period and by year |
| `02_annual_style_decisions.csv` | which styles were chosen each year, and their weights |
| `EXECUTION_SUMMARY.json`, `execution/` | full detail of the execution account |

**Conclusions:**
- **2021 to September 2026 (out of sample, execution account).** SGD 100,000 grows to 285,647.
  The CAGR is 20.1%, against 17.6% for the STI, with a similar maximum drawdown (14.4% vs 14.5%).
  This was never used to choose the configuration.
- **October 2026 test window.** −6.1% against −4.7% for the STI over 10 trading days. This is too
  short to judge.
- **Style choice.** Momentum is chosen every year, and Size in 10 of 11 years.

Options:
- `--skip-execution` runs Part A only (15 s).
- `--config file.yaml` runs a different configuration.
- `--out folder` sets the output folder.

## 3. Factor tests (2011–2015): which factors work

```bash
python tests/factor_tests/run_factor_tests.py            # add --no-plots to skip figures
```

It runs the single-factor tests for 2011–2015, on the period before the strategy uses any data:
- Rank IC and ICIR;
- top-30% minus bottom-30% long-short returns and quintiles;
- Top-20 excess return;
- Newey-West (HAC) t-statistics;
- yearly stability;
- factor correlations;
- 21 figures.

**Expected:** two tables, PRICE_ELIGIBLE_TRUE (primary) and ALL_PAIRED (control). The run ends with:

```
===== Reproduction of the branch's frozen results: 27 / 27 files identical =====
```

Output: `outputs/factor_tests/results/` and `outputs/factor_tests/figures/`.

**Conclusion (primary sample).** Momentum (IC t = 3.2) and Quality (IC t = 2.9) have significant
Rank IC and significant long-short returns. Low Risk has a significant IC but no long-short spread.
Investment is borderline. Size and Value show no premium on their own.

These tests motivate an *adaptive* choice of styles, rather than a fixed equal-weight mix of all
six. Details: `tests/factor_tests/README.md` and `tests/factor_tests/Six_Factor_Analysis_2011_2015.md`.

## 4. Strategy tests (2016–2020): why this configuration

```bash
python tests/strategy_tests/run_strategy_tests.py
```

It compares 24 configurations, all with a 3-year selection lookback:

| Setting | Values |
|---|---|
| K | 3 or 4 styles |
| Style weights | equal (EW), or inverse volatility (IV) re-estimated yearly, monthly or weekly |
| Share held | top 20%, 25% or 30% |

Only signal dates in 2016–2020 are used or printed; nothing from the evaluation or test periods
appears. The report, `outputs/strategy_tests/selection_report.txt`, has seven parts:

1. Matrices: Sharpe, Calmar, return, volatility and drawdown for every setting.
2. Ranking by 2016–20 Sharpe, with Calmar as the tie-break.
3. The median effect of each setting.
4. Robustness: the ranking at 20 and 30 bp costs, and the neighbours of the winner.
5. Significance against the STI and the equal-weight universe.
6. Turnover.
7. Integrity checks.

**Expected key lines:**

```
2. RANKING   rank 1  K3  IV_weekly  top 20%   Sharpe 0.94  Calmar 0.42   (2016-18 0.93, 2019-20 1.02)
4a. rank 1 at 10, 20 and 30 bp; rank correlation 10 vs 30 bp: 1.00
5. vs STI: active return 9.5%/yr, Newey-West t 1.71, bootstrap p (Sharpe gap <= 0) 0.046
7. all checks PASS, including "no look-ahead: yearly decisions unchanged when all later data is deleted"
```

**Conclusions:**
- **Three styles beat four** in all 12 matched pairs (median Sharpe 0.87 vs 0.75).
- **IV weights re-estimated weekly** with **top 20%** ranks first.
- **The choice is robust.** The ranking is unchanged at higher costs, and the nearest neighbour
  (IV monthly) is almost identical.
- **The edge over the STI is marginally significant** (p ≈ 0.05). Over the equal-weight universe it
  is not (p = 0.18).

This configuration is the one frozen in `config/strategy.yaml`.

## 5. Execution engine tests

```bash
python tests/execution_tests/run_execution_tests.py
```

There are 31 unit tests:
- **30 synthetic tests** by fangling. They cover accounting identities, board lots, minimum fees,
  T+2 settlement, dividends, splits, delisting, volume caps and no look-ahead in orders.
- **One integration test.** The real-data run must reproduce the frozen account: 5,418 fills and an
  ending NAV of SGD 266,334.30.

**Expected:** `Ran 31 tests ... OK`.

**Conclusion:** the account results in step 2 come from a tested engine.

## All tests at once

```bash
python tests/run_all_tests.py            # --skip factor | strategy | execution to leave a stage out
```

**Expected ending:**

```
SUMMARY
  Single-factor tests (2011-2015)      PASS
  Strategy selection (2016-2020)       PASS
  Execution engine tests               PASS
```

## How the pieces fit (for the presentation)

1. **Factors (2011–15).** Single-factor tests show that the premia differ across styles and over
   time. This motivates selecting styles adaptively.
2. **Configuration (2016–20).** The controlled 24-configuration grid picks K3 / IV weekly / top 20%,
   and the choice is frozen.
3. **Evaluation (2021–26/09).** The frozen strategy runs out of sample in the execution account:
   CAGR 20.1% against 17.6% for the STI.
4. **Test (October 2026).** The course test window gives the performance-metric table
   (`09_performance_metrics.csv`) and the asset price CSV (`10_*.csv`).
