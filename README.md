# SG Adaptive Multi-Factor Strategy

FE5209 Financial Econometrics group project. A long-only weekly stock-selection strategy on
Singapore-listed equities. Each year it picks the three style factors with the best recent
risk-adjusted performance. It weights them by inverse volatility, re-estimated every week, and holds
the top 20% of stocks by the combined score.

**New to the project? Start with [GUIDE.md](GUIDE.md)**. It covers setup in a fresh environment,
every command, what each one prints and the conclusion to draw from it.

**October 20 continuation:** [OOS update instructions](docs/OOS_UPDATE_20261020_ZH.md)
describe the calendar-inclusive test window, required new inputs, and separate reporting commands.
The original frozen configuration and its October 15 results are preserved. The continuation refuses
to report October 20 when prices, current weekly signals or exact STI total-return levels are missing.

## Quick start

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate      macOS / Linux: source .venv/bin/activate
pip install -r requirements.txt
python -m pip install -e .
python run_backtest.py
```

The run takes about 30 seconds. It reads `data/` and writes all results to
`outputs/SG_Adaptive_K3_IVweekly_Top20/`. Nothing needs downloading and no test code runs.

## Research pipeline

```
data/ (provider panel, cleaned)
  -> factors      six style scores -> weekly top-30% minus bottom-30% factor returns
  -> strategy     yearly selection of 3 styles -> weekly inverse-volatility weights -> composite score
                  -> top 20% holdings (buffer, sector cap) -> weekly target weights
  -> backtest     Part A: weekly NAV net of costs, metrics by period, live-window daily NAV
  -> live         Part B: daily execution account (board lots, fees, volume caps, T+2, dividends, FX)
  -> outputs/     course performance metrics (09_performance_metrics.csv) and all intermediate tables
tests/ (run separately)
  factor_tests    which factors work, 2011-2015
  strategy_tests  which configuration to use, 2016-2020   -> chose K3 / IV weekly / top 20%
  execution_tests is the execution engine correct
  ablation_tests  how K3/K6 and EW/IV change results, 2016-2026
  factor_diagnostics
                  post-backtest Top-3 predictability and factor-volatility diagnostics, 2016-2026
```

## Repository layout

```
GUIDE.md                     step-by-step guide: environment, commands, expected results
run_backtest.py              main entry: frozen strategy -> weekly backtest -> execution account -> metrics
config/strategy.yaml         frozen strategy configuration (single source of truth)
config/execution.yaml        frozen execution settings FINAL_100K_DIV14_V1
data/                        clean data package (see data/README.md)
src/sgfactor/
  data.py                    reads data/
  factors/                   style scores -> weekly long-short factor returns
  strategy/                  yearly style selection, style weights, composite score, holdings
  backtest/                  weekly NAV with drift and costs, metrics, summary tables, live window
  live/                      daily execution account (engine by fangling, Backtest-Framework-Top4)
                             + report.py: course performance metrics
tests/
  run_all_tests.py           all three test stages in order
  factor_tests/              single-factor tests 2011-15 (Ganjunhui, research/sg-single-factor-independent)
  strategy_tests/            configuration selection 2016-20 (24 configurations, no look-ahead)
  execution_tests/           execution engine tests + reproduction of the frozen final run
  ablation_tests/            2×2 K3/K6 × EW/IV weekly research ablation, results and figures
  factor_diagnostics/        post-backtest Top-3 predictability and factor-volatility diagnostics
scripts/build_clean_data.py  how data/ was built from the provider's raw files
```

## The strategy (frozen in `config/strategy.yaml`)

| Step | Rule |
|---|---|
| Universe | Weekly. SGX stocks that are price-eligible and have all six style scores (96 stocks ever eligible) |
| Style scores | Quality, Momentum (12-1), Low Risk, Investment, Size (small cap), Value. Supplied by the data team, standardised, higher = more favoured |
| Factor returns | Each week: top 30% minus bottom 30% by score, equal weight |
| Style selection | First signal week of each year: rank styles by mean / std of the last 3 years of completed weekly factor returns. Keep the top **3** |
| Style weights | Inverse volatility over the last 52 weeks, bounded to 5%–80%, **re-estimated every week** |
| Composite score | Weighted sum of the three selected style scores |
| Holdings | Top **20%** by composite score, equal weight (about 14–18 names). A holding is kept while it stays in the top 30% (buffer). At most 30% of names in one sector |
| Timing | Signal on Friday close; trade at the next trading day's close; hold one week |
| Costs | 10 bp one-way on turnover in Part A (20 bp also reported). Full fee schedule in Part B |

Only information available at each decision date is used: selection and weights use factor
returns whose holding period has already ended.

**Why this configuration.** `tests/strategy_tests` compares 24 configurations using 2016–2020 data only:
- K 3 or 4;
- style weights EW, or IV re-estimated yearly, monthly or weekly;
- top 20%, 25% or 30%.

This one ranks first on 2016–20 Sharpe: 0.94, with Calmar 0.42. Three styles beat four in every
matched pair; the median Sharpe is 0.87 for K3 against 0.75 for K4. Against the STI, the Newey-West t of the active
return is 1.71, and the block-bootstrap p-value that its Sharpe is no higher than the STI's is 0.046. The configuration was frozen before looking at any later
data.

## Periods

| Period | Signal dates | Use |
|---|---|---|
| Factor tests | 2011 .. 2015 | which factors carry a premium (tests/factor_tests) |
| Pre | 2016-01 .. 2018-12 | configuration selection (with OBS) |
| OBS (observation) | 2019-01 .. 2020-12 | configuration selection |
| EVAL (evaluation) | 2021-01 .. 2026-09-18 (last holding ends 2026-09-28) | out-of-sample, reported once, never used to choose |
| TEST / live | trades at the close of 2026-10-01, 10-05, 10-12 and 10-19, using the latest weekly signal before each (09-25, 10-02, 10-09, 10-16); marked daily to 2026-10-20 | course test period |

LSEG daily prices end on 2026-10-15; 10-16 .. 10-20 prices for the held stocks were added from public quotes (see `data/README.md`).

## Results

### Course test window: 2026-10-01 .. 2026-10-20

Data extended as described in `data/README.md` (signal week 2026-10-16 added; daily prices to 10-20 for held names;
P9D dividend of 10-12 added). The configuration selection (`tests/strategy_tests`, 2016–20 only) is unchanged:
K3 / IV weekly / top 20% ranks first (Sharpe 0.94). Execution account, trades at the close of 10-01, 10-05, 10-12 and
10-19 (signals 09-25, 10-02, 10-09, 10-16). Two window conventions, same account (ending NAV SGD 264,827.09):

| | From 10-01 close (`run_backtest.py`) | From 09-30 close, includes 10-01 (`scripts/report_oos.py`, OOS branch) |
|---|---|---|
| Strategy cumulative return | −6.63% (283,634 → 264,827) | −7.29% (285,647 → 264,827) |
| STI total return | −4.65% | −4.79% |
| Excess vs STI | −1.98 pp | −2.50 pp |
| Annual return / volatility (annualised short sample) | −73.6% / 18.0% | −74.4% / 17.3% |
| Sharpe (rf 0) / max drawdown | −7.28 / 7.3% | −7.76 / 7.3% |
| Fills / position trades / win rate | 61 / 19 / 5.3% | 75 / 19 / 5.3% |

The OOS branch's `continue_oos.py` on this data gives the same ending NAV (its >= 50-names market-coverage guard
was relaxed for that cross-check, because prices after 10-15 were added only for held names).
EVAL is unchanged (SGD 100,000 → 285,647). An earlier version of this README reported the window to 2026-10-15
(−6.10% vs STI −4.66%, before the P9D dividend was added).

### Part A: weekly backtest, net of 10 bp, risk-free rate 0

| | Annual return | Volatility | Sharpe | Max drawdown | Calmar |
|---|---|---|---|---|---|
| OBS 2019–20: strategy | 22.9% | 22.7% | 1.02 | 35.2% | 0.65 |
| OBS 2019–20: STI | 2.2% | 20.5% | 0.21 | 32.1% | 0.07 |
| EVAL 2021-01..2026-09: strategy | 24.5% | 16.6% | 1.41 | 12.3% | 1.99 |
| EVAL 2021-01..2026-09: STI | 17.3% | 12.2% | 1.37 | 10.5% | 1.65 |
| EVAL 2021-01..2026-09: equal-weight universe | 12.1% | 12.0% | 1.02 | 16.7% | 0.73 |

Live window, daily NAV from the 2026-10-01 close to 2026-10-20 (Part A, 10 bp proportional cost):
- Strategy: −6.9%.
- STI: −4.7%.
(The equal-weight universe is not reported after 10-15, because public prices were added only for held stocks.)

### Part B: daily execution account (headline result)

Setting `FINAL_100K_DIV14_V1`, frozen by the group on 2026-10-20 (see `config/execution.yaml`):

| Item | Setting |
|---|---|
| Starting cash | SGD 100,000 at the first 2021 signal; one continuous account through the live window |
| Trades | daily close, board lot of 100, 1% cash reserve |
| Volume limit | at most 10% of the day's volume and 10% of the lagged 20-day ADV |
| Order life | 5 sessions |
| Costs | commission 5 bp (minimum SGD 5) + market fees 4 bp + slippage 10 bp |
| Settlement | T+2 |
| Dividends | source cash dividends, paid 14 calendar days after the ex-date (an assumption) |
| Currency | USD / EUR listings converted to SGD with daily FX |

Course performance metrics (`09_performance_metrics.csv`):

| Metric | TEST 2026-10-01 close .. 10-20 | EVAL 2021-01 .. 2026-09 (reference) |
|---|---|---|
| NAV, SGD | 283,634 → 264,827 | 100,000 → 285,647 |
| Cumulative return (STI) | −6.63% (−4.65%) | +185.6% (+153.5%) |
| Annual return (STI) | −73.6% (−60.3%); annualised from 13 days | 20.2% (17.7%) |
| Annual volatility | 18.0% | 14.3% |
| Sharpe ratio, rf 0 (STI) | −7.28 (−5.19) | 1.36 (1.49) |
| Max drawdown (STI) | 7.3% (5.3%) | 14.4% (14.5%) |
| Drawdown patterns: count / longest | 2 / 9 days | 53 / 663 days |
| Win rate (position trades) | 5.3% (1 of 19) | 65.5% |
| Number of trades (fills: buys / sells) | 61 (37 / 24) | 5,357 (3,380 / 1,977) |
| Position trades | 19 | 84 |
| Average holding period | 12 days (whole window) | 293 trading days |
| Profit per trade (position trade), SGD | −990 | 2,210 |
| Sortino / Calmar | −5.62 / −10.10 | 1.33 / 1.41 |
| Fees / slippage / dividends, SGD | 326 / 45 / 322 | 27,937 / 2,780 / 46,269 |

Definitions are in `src/sgfactor/live/report.py`. Notes on two of them:
- **Number of trades** counts every execution. The account trims and tops up weights every week,
  so there are many more fills than position trades.
- **Position trade.** A position trade lasts from the day a stock is first held until it is fully
  sold, and its profit includes fees and dividends. Positions open at a window edge are cut at that
  edge.

Thirteen trading days are far too short to judge the strategy.

The engine port was checked against fangling's own run on the earlier 74-stock panel. Both
produced 3,525 fills and an ending NAV of SGD 328,755.

## Output files (`outputs/SG_Adaptive_K3_IVweekly_Top20/`)

| File | Content |
|---|---|
| `01_factor_returns_weekly.csv` | weekly long-short return of each style |
| `02_annual_style_decisions.csv` | styles chosen each year, their weights and selection scores |
| `03_target_holdings_weekly.csv` | weekly holdings with rank, sector and status (new / kept / kept by buffer) |
| `target_weights.csv` | `signal_date, execution_date, ticker, weight`: input for the execution framework |
| `04_trade_ledger.csv` | every buy and sell at each weekly rebalance |
| `05_weekly_returns.csv` | strategy (net, 20 bp stress, gross), STI, equal-weight universe |
| `06_performance_summary.csv` | Part A metrics by period |
| `07_calendar_year_returns.csv` | returns by calendar year |
| `08_live_daily_nav.csv`, `08_live_summary.csv`, `08_live_holdings.csv` | live window (Part A): daily NAV, summary, holdings at each live trade |
| `09_performance_metrics.csv` | **course performance metrics**, TEST period and EVAL reference (Part B) |
| `10_portfolio_assets.csv`, `10_portfolio_daily_close.csv` | **course deliverable**: assets in the test-period portfolio and their daily closing prices (listing currency) |
| `EXECUTION_SUMMARY.json` | daily execution account summary (EVAL and LIVE) |
| `execution/daily.csv` | daily NAV, cash, receivables, P&L, dividends, fees |
| `execution/holdings.csv`, `orders.csv`, `fills.csv`, `attempts.csv` | shares held, orders, fills, reasons for unfilled orders |
| `execution/dividends.csv`, `events.csv` | dividend events used (with assumed pay dates) and cash settlements |
| `execution/contributions.csv`, `risk.csv`, `audit.json` | per-stock daily contribution, concentration, accounting checks |
| `run_manifest.json` | configuration used and trade statistics |

## Course deliverables (`deliverables/`)

`outputs/` is not committed, so the files the course asks for are kept in `deliverables/`.
They are copies of what `python run_backtest.py` writes and are reproduced exactly by it.

| File | Content |
|---|---|
| `10_portfolio_assets.csv` | the assets held in the test-period portfolio (to 2026-10-20) |
| `10_portfolio_daily_close.csv` | their daily closing prices, 2025-10-01 to 2026-10-20 (listing currency) |
| `09_performance_metrics.csv` | course performance metrics, TEST period and EVAL reference |

## Tests (run separately)

```bash
python tests/run_all_tests.py                          # all three below in order, about 4 minutes
python tests/factor_tests/run_factor_tests.py          # single-factor tests 2011-15, about 1-2 minutes
python tests/strategy_tests/run_strategy_tests.py      # 24 configurations, 2016-20 only, about 2 minutes
python tests/execution_tests/run_execution_tests.py    # 31 tests, about 30 seconds
```

Two optional research analyses are deliberately separate from `run_all_tests.py`:

```bash
python tests/ablation_tests/src/run_ablation.py         # 2×2 K3/K6 × EW/IV ablation
python tests/ablation_tests/src/plot_ablation.py        # plots saved ablation results
python tests/factor_diagnostics/run_factor_diagnostics.py  # requires the main-backtest outputs above
```

The ablation run compares four full weekly-backtest variants and writes its results to
`tests/ablation_tests/results/` and figures to `tests/ablation_tests/figures/`. Factor diagnostics
read the final main-backtest factor-return and annual-decision files, then write their outputs to
`tests/factor_diagnostics/`. See [GUIDE.md](GUIDE.md) and [tests/README.md](tests/README.md) for
commands, prerequisites, and output details.

## Limitations

- **Survivorship bias.** The data cover the 114 stocks listed today, so history before the live
  window excludes companies that later delisted.
- **Missing fundamentals.** 96 of the 114 stocks ever enter the universe. The other 18 have no
  fundamental data in the source (e.g. SIA, Jardine C&C, Great Eastern).
- **Local-currency weekly returns.** In Part A, the weekly returns of USD and EUR listings are in
  their own currency. Part B converts them to SGD.
- **Not point-in-time.** Fundamentals behind Quality, Investment and Value are not strictly
  point-in-time, and Size and Value use a market-cap proxy.
- **Close-price proxy.** Part B models lots, fees and liquidity, but fills are at the close and
  zero-volume days are treated as data gaps.
- **Unverified dividend data.** Dividend pay dates, currency and tax treatment are assumed. The
  audit file labels the result `SOURCE_DIVIDEND_14D_ESTIMATE_UNVERIFIED_PRICE_SHARE_BASIS`.
- **Risk-free rate.** Sharpe ratios use a risk-free rate of 0, because there is no SGD risk-free
  series in the package.
- **Short test period.** The course test window is 13 trading days (10-01 close to 10-20), so its annualised figures are
  not meaningful.

## Data licence

The data are derived from LSEG / WRDS sources licensed to NUS. **Keep this repository private.**


## Performance attribution / 业绩归因

The frozen K3 / IV weekly / top20 run has a reconciled attribution delivery.
See [中文归因报告](performance_attribution/sg_k3_ivweekly_top20_20261021/REPORT_ZH.md)
and [复现说明](performance_attribution/sg_k3_ivweekly_top20_20261021/README_ZH.md).
The analysis adds stock, sector-group, dividend, FX, cost, drawdown and benchmark-relative
contributions without changing the strategy, execution configuration, or input data.


## Investability / 可投资性

See the [current K3 investability report](investability/sg_k3_ivweekly_top20_20261021/REPORT_ZH.md),
[reproduction guide](investability/sg_k3_ivweekly_top20_20261021/README_ZH.md), and
[current versus historical version notes](investability/README.md).
This additive study replays execution scenarios and exit paths without changing the frozen
strategy, execution configuration, data, main entry point, or existing attribution.
