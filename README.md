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

The run takes about 15 seconds. It reads `data/` and writes all results to `outputs/SG_Adaptive_Top4/`.
Nothing needs downloading and no test code is run.

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
  live/                      live / execution framework (to be added)
tests/
  strategy_tests/            controlled-variable comparison + integrity checks
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

## Tests (run separately)

```bash
python tests/strategy_tests/run_strategy_tests.py    # about 1 minute
python tests/factor_tests/run_factor_tests.py        # placeholder
```

The strategy tests change one setting at a time from the baseline (Top-3) and report every
period. The selection rule, fixed in advance, is that a variant must beat the baseline on both
Sharpe and Calmar in OBS. They also check weights, the sector cap, look-ahead (each yearly
decision is recomputed with all later data deleted) and reproduction of earlier results.

## Limitations

- **Survivorship bias.** The universe is the 114 stocks listed today, so history before the live
  window excludes companies that later delisted.
- **Not point-in-time.** Fundamentals behind Quality, Investment and Value are not strictly
  point-in-time, and Size and Value use a market-cap proxy.
- **Simplified execution.** Weekly returns ignore board lots, minimum commissions and liquidity
  limits. The execution framework will handle these.
- **Risk-free rate.** Sharpe ratios use a risk-free rate of 0, because the package has no SGD
  risk-free rate series.
- **Hindsight.** The evaluation period had been looked at before the configuration was frozen.

## Data licence

The data are derived from LSEG / WRDS sources licensed to NUS. **Keep this repository private.**
