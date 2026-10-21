# Data package

## `sg_universe_weekly.csv.gz`: weekly investable universe, 2007-10 .. 2026-10-09

Each row is one (signal week, stock) pair. Only stock-weeks that are in the universe are kept.
The file has 68,161 rows covering 993 weeks and 96 distinct tickers out of the provider's 114.
Rebuild it with `scripts/build_clean_data.py`.

| Column | Meaning |
|---|---|
| `signal_date` | Friday on which the signal is formed |
| `execution_date` | next trading day; trades happen at this close |
| `next_execution_date` | execution date of the following week; the holding ends at this close |
| `ticker` | SGX ticker (RIC) |
| `sector` | one of six SG sector buckets |
| `market_cap_sgd` | weekly market cap in SGD: close × lagged shares × FX |
| `quality_score` … `value_score` | the six style scores, standardised, higher = more favoured. `size_score` is high for small caps (−ln market cap) |
| `forward_return` | total return from the `execution_date` close to the `next_execution_date` close, in the listing currency |

**Source**

The file is built from `sg_six_factor_panel_2006_2026_final.csv.gz`, the data team's final panel
of 2026-10-21. In that panel, FX conversion has been back-filled over the whole history, so stocks
that report in a foreign currency have Size and Value scores. The style scores are used exactly as
supplied.

**How the scores are built**

These rules come from the provider's scripts and were checked against the panel.

| Score | Raw input | Standardisation |
|---|---|---|
| Momentum | adjusted price 21 days ago ÷ adjusted price 252 days ago − 1 | z-score (1/99% winsorised), minus the sector mean, then z-scored again |
| Low Risk | −(252-day volatility) | z-score (1/99% winsorised), minus the sector mean, then z-scored again |
| Size | −ln(market cap in SGD) | z-score within each sector (winsorised) |
| Value | book equity in SGD ÷ market cap | z-score within each sector (winsorised) |
| Quality | annual fundamentals, lagged 183 days | — |
| Investment | annual fundamentals, lagged 183 days | — |

**Cleaning**

- Kept only rows that are price-eligible and have all six scores, i.e. the availability flag is set and the score is a finite number.
- Flag spellings: in the four newest weeks `price_eligible` is blank and is treated as eligible. The provider writes the Size and Value flags as True/False in the history but as 1/0 in the newest weeks; both spellings are accepted.
- Removed: availability flags, `panel_status`, PIT and source notes, FX working columns, and the raw inputs behind Size and Value.

## `sti_total_return_daily.csv`: benchmark

FTSE Straits Times Index total return (LSEG `.TRISTI`, SGD), daily from 2006-01-03 to 2026-10-16.

## Daily inputs (live window and execution account)

| File | Content |
|---|---|
| `prices_daily.csv.gz` | `date, ticker, close, adj_close, volume` for the 96 universe stocks, 2006-01-03 .. 2026-10-15. `close` is in the listing currency |
| `fx_daily.csv` | SGD per USD and SGD per EUR, used to convert non-SGD listings |
| `trading_sessions.csv` | proxy trading calendar: days on which at least 50 of the 114 names report positive volume, plus the SGX_TEAM_HANDOFF trading days after 2026-09-24 |
| `security_master.csv` | `ticker, company_name, currency, six_sector, listing_date` for all 114 names |
| `corporate_actions.csv` | `date, ticker, action_type, dividend, split_ratio` for universe stocks (source events up to 2026-09-15) |
| `team_ticker_map.csv` | SGX ticker ↔ SGX_TEAM_HANDOFF `gvkey_iid`, matched on daily closes in 2026 |

Where these come from:
- **Prices up to 2026-09-24** come from `SGX_comprehensive_2006_2026_handoff`.
- **Prices from 2026-09-25 to 2026-10-15** come from `SGX_TEAM_HANDOFF`. The two series are joined on 2026-09-24; over September 2026 their daily returns and volumes are identical.
- **Top Glove (BVA)** is not in SGX_TEAM_HANDOFF, so it has no price after 2026-09-24.

Notes on use:
- Prices are split-adjusted, so split events are not applied a second time.
- Cash dividends are paid in the account 14 calendar days after the ex-date. This is the group's assumption, not a verified pay date.
