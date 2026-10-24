# Guide: running the project from scratch

This guide takes you from a fresh computer to every result in the project. For each step it shows
the command, the expected output and the conclusion to draw from it. The tests (steps 3–5) and
research analyses (steps 6–7) are optional and run separately from the main program (step 2).

| Step | Command | Time | Answers |
|---|---|---|---|
| 1 | set up the environment | 2 min | – |
| 2 | `python run_backtest.py` | 30 s | how the frozen strategy performs (main result, course metrics) |
| 3 | `python tests/factor_tests/run_factor_tests.py` | 1–2 min | which style factors carry a premium (2011–15) |
| 4 | `python tests/strategy_tests/run_strategy_tests.py` | 2 min | why this configuration (2016–20) |
| 5 | `python tests/execution_tests/run_execution_tests.py` | 30 s | is the execution engine correct |
| 6 | `python tests/ablation_tests/src/run_ablation.py` | about 10 s | whether K3/K6 and EW/IV drive the result |
| 7 | `python tests/factor_diagnostics/run_factor_diagnostics.py` | under 1 min | whether annual Top-3 selection is predictive and how factor volatility differs |
| all tests | `python tests/run_all_tests.py` | 4 min | steps 3–5 in order, with a PASS/FAIL summary |

## 1. Environment

**Requirements:**
- Python 3.10–3.14 (developed on 3.13, also checked on 3.14).
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
python -m pip install -e .               # install the local src/sgfactor package
```

Conda works too: `conda create -n sgfactor python=3.12`, then `conda activate sgfactor`, then
`pip install -r requirements.txt` and `python -m pip install -e .`.

**PyCharm:**
1. Open the project folder.
2. Settings → Project → Python Interpreter → Add Interpreter → Virtualenv → New, base Python 3.10–3.14.
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
   SGD 100,000 in January 2021 and running to 2026-10-20. It models:
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
LIVE window ... strategy -0.0693   STI -0.0465
Part B: daily execution account ...
  EVAL 2021-01-08 .. 2026-09-30: SGD 100,000 -> 285,647  CAGR 20.1%, max drawdown 14.4%, Sharpe (daily) 1.36
  LIVE 2026-10-01 close .. 2026-10-20:
  SGD 283,634 -> 264,827
  return -6.63% | STI -4.65%
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
- October 2026 test window. The execution account returned -6.63% versus -4.65% for the STI from October 1 close to October 20 close, covering 13 daily return observations. This short period is insufficient to assess long-term performance. This is too
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

There are **39 automated tests**:

- **30 synthetic execution tests** by fangling. They cover accounting identities, board lots, minimum fees, T+2 settlement, dividends, splits, delisting, volume caps, and no look-ahead in orders.
- **8 OOS readiness and reporting tests.** They verify data completeness, signal availability, benchmark consistency, reporting boundaries, and P&L reconciliation.
- **One integration test.** The real-data run must reproduce the frozen account: **5,432 fills** and an **ending NAV of SGD 264,827.09** (as of 2026-10-20).

**Expected:** `Ran 39 tests ... OK`.

**Conclusion:** the account results in step 2 come from a tested engine.

## 6. Ablation analysis (2016–2026)

```bash
python tests/ablation_tests/src/run_ablation.py
python tests/ablation_tests/src/plot_ablation.py
# Optional: add STI total return to the cumulative-wealth chart
python tests/ablation_tests/src/plot_ablation.py --include-sti
```

The ablation holds the frozen weekly setup fixed and compares all four combinations of factor
selection breadth and weighting:

| Variant | Selection | Weighting |
|---|---:|---|
| `K6_EW` | 6 factors | Equal weight |
| `K6_IV` | 6 factors | Inverse volatility |
| `K3_EW` | 3 factors | Equal weight |
| `K3_IV` | 3 factors | Inverse volatility |

**Outputs:** calculation tables and methodology in `tests/ablation_tests/results/`; cumulative-
wealth and evaluation-metric figures in `tests/ablation_tests/figures/`.

**Conclusion:** this is a sensitivity analysis, not a configuration-selection stage. It is excluded
from `run_all_tests.py` because it runs four full weekly backtests.

## 7. Factor diagnostics (2016–2026)

Run step 2 first, because the diagnostics use its factor-return and annual-selection files:

```bash
python run_backtest.py --skip-execution
python tests/factor_diagnostics/run_factor_diagnostics.py
```

The diagnostics examine:

- annualized factor returns for the selected Top-3 versus unselected Bottom-3 factors;
- the distribution of trailing 52-week long-short factor volatility.

**Outputs:** `tests/factor_diagnostics/results/factor_predictability_2016_2026.csv` and PNG/PDF
figures in `tests/factor_diagnostics/figures/`.

**Conclusion:** these are post-backtest research diagnostics. They remain outside
`run_all_tests.py` because they require generated `outputs/SG_Adaptive_K3_IVweekly_Top20/` files.

## All tests at once

```bash
python tests/run_all_tests.py            # --skip factor | strategy | execution to leave a stage out
```

This command runs only steps 3–5. Run the ablation and factor diagnostics separately when their
research outputs are needed.

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
5. **Ablation (2016–26/09).** The 2×2 K3/K6 × EW/IV comparison separates selection-breadth and
   weighting effects under the frozen weekly framework.
6. **Diagnostics (2016–26/09).** Annual Top-3 predictability and rolling factor-volatility figures
   provide supporting evidence on adaptive selection and factor risk.
