# Single-factor tests, 2011–2015

These tests check each of the six style factors on its own, over the factor-selection period. They
come from Ganjunhui's branch `research/sg-single-factor-independent` (commit 0608b8e, 2026-10-21).

## Run

```bash
python tests/factor_tests/run_factor_tests.py              # about 1–2 minutes
python tests/factor_tests/run_factor_tests.py --no-plots   # tables only
```

The runner does three things:

1. It runs the four analysis modules from the repository's `data/factor_test_panel.csv.gz`.
2. It redraws the 21 figures.
3. It compares every result CSV with the frozen results in `results/`.

Outputs go to `outputs/factor_tests/`. The final line reports how many files are identical; it should read `27 / 27 files identical`.

## Contents

| Path | What it is |
|---|---|
| `src/factor_performance.py` | Rank IC and ICIR; top-30% minus bottom-30% long-short; quintiles; Top-20 excess return; coverage |
| `src/factor_validation.py` | Newey-West HAC tests (4 lags), Top-20% excess return, annual compounded long-short |
| `src/factor_robustness.py` | Year-by-year stability and universe-filter sensitivity. Reads the performance output |
| `src/factor_correlation.py` | Factor rank correlations, fixed equal-weight composites, leave-one-out increments |
| `src/plot_factor_results.py` | 21 report figures (PNG and PDF) |
| `results/`, `figures/` | The branch's frozen results and figures |
| `Six_Factor_Analysis_2011_2015.md` | The research write-up, in Chinese |

The tests use two samples:
- `PRICE_ELIGIBLE_TRUE` is the primary sample.
- `ALL_PAIRED` is the control.

## Changes from the branch

The analysis methods are unchanged. Only three things differ:

- **Input path.** The three modules that read data now take `DEFAULT_INPUT` from `data/factor_test_panel.csv.gz`. That file holds the same columns, with the same values, as the final panel `sg_six_factor_panel_2006_2026_final.csv.gz` (SHA-256 `ad7f37af…`) that the branch used.
- **pandas 3 fix.** In `plot_factor_results.py`, `values *= 100` became `values = values * 100`. The in-place version fails under pandas 3 because the arrays are read-only.
- **Runner.** `run_factor_tests.py` was added. It writes to `outputs/` instead of overwriting the frozen `results/`.

## Main results (`PRICE_ELIGIBLE_TRUE`, 261 weeks)

| Factor | Mean Rank IC | IC HAC t | IC > 0 years (of 5) | Long-short HAC t |
|---|---|---|---|---|
| Quality | 0.024 | 2.92 | 5 | 2.45 |
| Momentum | 0.038 | 3.20 | 5 | 2.22 |
| Low Risk | 0.027 | 2.46 | 4 | 0.12 |
| Investment | 0.015 | 1.93 | 4 | 0.59 |
| Size | −0.000 | −0.03 | 2 | 1.11 |
| Value | −0.011 | −1.14 | 3 | 0.54 |

- **Momentum and Quality** have the most consistent evidence, both in IC and in long-short returns.
- **Low Risk** has a significant IC but little return spread.
- **Investment** is weakly positive.
- **Size and Value** show no single-factor IC.

See `Six_Factor_Analysis_2011_2015.md` for the full discussion. All returns are gross of costs.
