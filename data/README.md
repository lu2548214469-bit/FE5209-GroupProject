# Data package

## `sg_universe_weekly.csv.gz`: weekly investable universe, 2007-10 .. 2026-10-09

There is one row per (signal week, stock), and only stock-weeks that are in the universe are kept:
55,726 rows, 993 weeks and 74 distinct tickers out of the provider's 114. To rebuild the file, run
`scripts/build_clean_data.py`.

| Column | Meaning |
|---|---|
| `signal_date` | Friday on which the signal is formed |
| `execution_date` | next trading day; trades happen at this close |
| `next_execution_date` | execution date of the following week; the holding ends at this close |
| `ticker` | SGX ticker (RIC) |
| `sector` | one of six SG sector buckets |
| `market_cap_proxy_sgd` | weekly market-cap proxy (SGD) |
| `quality_score` … `value_score` | six style scores, standardised, higher = more favoured. `size_score` is high for small caps (−ln market cap) |
| `forward_return` | total return from `execution_date` close to `next_execution_date` close |

**Source.** The source file is `sg_six_factor_candidate_panel_2006_to_2026_10_09_no_imputation_markers.csv.gz`
(third version from the data team). The style scores are used exactly as supplied.

**Cleaning.** These steps were applied to the source file:
- Kept only rows that are price-eligible and have all six scores, meaning the availability flag is 1 and the value is a finite number. In the four newest weeks (2026-09-18 .. 10-09) the provider left `price_eligible` blank, so it is treated as eligible there.
- Removed the internal columns: availability flags, `panel_status`, the PIT and source notes, the raw inputs behind Size and Value, and currency notes.
- Checked that every kept row has a forward return and a sector.

## `sti_total_return_daily.csv`: benchmark

This is the FTSE Straits Times Index total return (LSEG `.TRISTI`, SGD), daily from 2006-01-03 to 2026-10-16.
