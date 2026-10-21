# SG Adaptive Multi-Factor Strategy

FE5209 Financial Econometrics group project. A long-only weekly stock-selection strategy on
Singapore-listed equities. Each year it chooses the four style factors with the best recent
risk-adjusted performance, combines their scores, and holds the top-ranked stocks.

## Quick start

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate      macOS / Linux: source .venv/bin/activate
pip install -r requirements.txt
python run_backtest.py
```

The run takes about 25 seconds. It reads `data/` and writes all results to `outputs/SG_Adaptive_Top4/`.
Nothing needs downloading and no test code is run. It has two parts:

- **Part A: strategy and weekly backtest.** Builds the weekly target weights and a weekly NAV net of 10 bp per side.
- **Part B: daily execution account** (`src/sgfactor/live/`). Trades the same targets from SGD 100,000 in cash
  starting in January 2021, with:
  - board lots;
  - minimum commissions and fees;
  - volume limits;
  - T+2 settlement;
  - dividends.

  This is the headline result. Use `--skip-execution` to run Part A only.

## Repository layout

```
run_backtest.py              main entry: historical backtest of the frozen strategy
config/strategy.yaml         frozen configuration (single source of truth)
data/                        clean data package (see data/README.md)
src/sgfactor/
  data.py                    reads data/
  factors/                   style scores -> weekly long-short factor returns
  strategy/                  yearly style selection, style weights, composite score, holdings
  backtest/                  weekly NAV with drift and costs, metrics, summary tables
  live/                      daily execution account (engine by fangling, Backtest-Framework-Top4)
config/execution.yaml        frozen execution settings FINAL_100K_DIV14_V1
tests/
  strategy_tests/            controlled-variable comparison + integrity checks
  execution_tests/           execution engine tests + reproduction of the frozen final run
  factor_tests/              factor tests (to be added)
scripts/build_clean_data.py  how data/ was built from the provider's raw files
```

## The strategy

| Step | Rule |
|---|---|
| Universe | Weekly. SGX stocks that are price-eligible and have all six style scores |
| Style scores | Quality, Momentum (12-1), Low Risk, Investment, Size (small cap), Value. Supplied by the data team, standardised, higher = more favoured |
| Factor returns | Each week: top 30% minus bottom 30% by score, equal weight |
| Style selection | First signal week of each year: rank styles by mean / std of the last 3 years of completed weekly factor returns, keep the top 4 |
| Style weights | Inverse volatility over the last 52 weeks, bounded to 5%–80% |
| Composite score | Weighted sum of the four selected style scores |
| Holdings | Top 20% by composite score, equal weight (about 13 names). Buffer: a holding is kept while it stays in the top 30%. At most 30% of names in one sector |
| Timing | Signal on Friday close; trade at the next trading day's close; hold one week |
| Costs | 10 bp one-way on turnover (20 bp also reported) |

Only information available at each decision date is used: selection and weights use factor
returns whose holding period has already ended.

## Periods

| Period | Signal dates | Use |
|---|---|---|
| Pre | 2016-01 .. 2018-12 | robustness only |
| OBS (observation) | 2019-01 .. 2020-12 | choosing the configuration |
| EVAL (evaluation) | 2021-01 .. 2026-09-18 (last holding ends 2026-09-28) | reported once, never used to choose |
| Live | 2026-09-25 .. 2026-10-09 (holdings 2026-09-28 .. 10-19) | live window |

## Results (`python run_backtest.py`, net of 10 bp, risk-free rate 0)

| | Annual return | Volatility | Sharpe | Max drawdown | Calmar |
|---|---|---|---|---|---|
| OBS 2019–20: strategy | 24.7% | 20.1% | 1.20 | 30.3% | 0.81 |
| OBS 2019–20: STI | 2.2% | 20.5% | 0.21 | 32.1% | 0.07 |
| EVAL 2021-01..2026-09: strategy | 26.8% | 14.9% | 1.67 | 15.2% | 1.76 |
| EVAL 2021-01..2026-09: STI | 17.3% | 12.2% | 1.37 | 10.5% | 1.65 |
| EVAL 2021-01..2026-09: equal-weight universe | 11.0% | 11.7% | 0.95 | 15.7% | 0.70 |

Live window (3 weeks, cumulative): strategy −4.3%, STI −5.6%, equal-weight universe −5.5%.

### Daily execution account (Part B, headline result)

Setting `FINAL_100K_DIV14_V1`, frozen by the group on 2026-10-20 (see `config/execution.yaml`):

| Item | Setting |
|---|---|
| Starting cash | SGD 100,000 at the first 2021 signal |
| Trades | daily close, board lot of 100, 1% cash reserve |
| Volume limit | at most 10% of the day's volume and 10% of the lagged 20-day ADV |
| Order life | 5 sessions |
| Costs | commission 5 bp (minimum SGD 5) + market fees 4 bp + slippage 10 bp |
| Settlement | T+2 |
| Dividends | source cash dividends, paid 14 calendar days after the ex-date (an assumption) |

| 2021-01-08 .. 2026-09-21 | Strategy | STI total return, same dates |
|---|---|---|
| SGD 100,000 grows to | 328,755 | |
| CAGR | 23.2% | 17.1% |
| Max drawdown | 16.9% | 14.5% |
| Sharpe (daily, rf 0) | 1.70 | |

Breakdown:
- Dividends received: SGD 36,261.
- Fees: SGD 19,292.
- Slippage: SGD 3,452.
- Share of requested order value that was filled: 98.5%.

These numbers match the group's frozen final run exactly: 3,525 fills, 3,043 orders and the same
ending NAV. That run was produced by `run_top4.py` on the `Backtest-Framework-Top4` branch.

**Why the account stops at 2026-09-21:** the daily price file ends on 2026-09-24. The live window
can be added once daily prices to mid-October are available.

## Output files (`outputs/SG_Adaptive_Top4/`)

| File | Content |
|---|---|
| `01_factor_returns_weekly.csv` | weekly long-short return of each style |
| `02_annual_style_decisions.csv` | styles chosen each year, their weights and selection scores |
| `03_target_holdings_weekly.csv` | weekly holdings with rank, sector and status (new / kept / kept by buffer) |
| `target_weights.csv` | `signal_date, execution_date, ticker, weight`: input for the execution framework |
| `04_trade_ledger.csv` | every buy and sell at each rebalance |
| `05_weekly_returns.csv` | strategy (net, 20 bp stress, gross), STI, equal-weight universe |
| `06_performance_summary.csv` | metrics by period |
| `07_calendar_year_returns.csv` | returns by calendar year |
| `run_manifest.json` | configuration used and trade statistics |
| `EXECUTION_SUMMARY.json` | **daily execution account: headline result** |
| `execution/daily.csv` | daily NAV, cash, receivables, P&L, dividends, fees |
| `execution/holdings.csv`, `orders.csv`, `fills.csv`, `attempts.csv` | shares held, orders, fills, reasons for unfilled orders |
| `execution/dividends.csv`, `events.csv` | dividend events used (with assumed pay dates) and cash settlements |
| `execution/contributions.csv`, `risk.csv`, `audit.json` | per-stock contribution, concentration, accounting checks |

## Tests (run separately)

```bash
python tests/strategy_tests/run_strategy_tests.py      # about 1 minute
python tests/execution_tests/run_execution_tests.py    # 31 tests, about 25 seconds
python tests/factor_tests/run_factor_tests.py          # placeholder
```

The strategy tests change one setting at a time from the baseline (Top-3) and report every
period. The selection rule, fixed in advance, is that a variant must beat the baseline on both
Sharpe and Calmar in OBS. They also check weights, the sector cap, look-ahead (each yearly
decision is recomputed with all later data deleted) and reproduction of earlier results.
The execution tests are fangling's 30 synthetic-data tests of the engine. They cover accounting,
lots and fees, settlement, corporate actions and look-ahead. There is also one check that the
real-data run reproduces the frozen final result.

## Limitations

- **Survivorship bias.** The universe is the 114 stocks listed today, so history before the live
  window excludes companies that later delisted.
- **Not point-in-time.** Fundamentals behind Quality, Investment and Value are not strictly
  point-in-time, and Size and Value use a market-cap proxy.
- **Simplified execution in the weekly backtest.** Part A ignores board lots, minimum commissions and
  liquidity limits. Part B models them, but only as a close-price proxy: zero-volume days are
  assumed to be data gaps, and fills are capped by that day's realised volume.
- **Unverified dividend data.** Dividend pay dates, currency and tax treatment are assumed, and the
  vendor's share basis has not been verified. The audit file labels the result
  `SOURCE_DIVIDEND_14D_ESTIMATE_UNVERIFIED_PRICE_SHARE_BASIS`.
- **Risk-free rate.** Sharpe ratios use a risk-free rate of 0, because the package has no SGD
  risk-free rate series.
- **Hindsight.** The evaluation period had been looked at before the configuration was frozen.

## Data licence

The data are derived from LSEG / WRDS sources licensed to NUS. **Keep this repository private.**
