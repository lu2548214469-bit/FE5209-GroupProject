# Tests

The repository separates its validation work into a standard test suite and two research-analysis modules:

- `tests/run_all_tests.py` runs the self-contained factor, strategy, and execution tests.
- `tests/factor_diagnostics/` creates post-backtest research diagnostics from the final strategy outputs. It is intentionally separate because it requires generated main-backtest artifacts.
- `tests/ablation_tests/` runs the 2×2 K3/K6 × EW/IV research ablation and produces its comparison tables and figures.

## Standard test suite

These checks are not run automatically by `run_backtest.py`.

| Command | What it does |
|---|---|
| `python tests/run_all_tests.py` | Runs factor tests (2011–2015), strategy selection tests (2016–2020), and execution-engine tests in research order. Prints a PASS/FAIL summary. Use `--skip factor`, `--skip strategy`, or `--skip execution` to omit a stage. Takes about 4 minutes. |
| `python tests/factor_tests/run_factor_tests.py` | Independent single-factor research for 2011–2015: Rank IC/ICIR, long-short and quintile returns, Top-20 excess return, HAC tests, annual robustness, factor correlations, composites, and 21 figures. It also reproduces the branch's frozen results. See `tests/factor_tests/README.md`. |
| `python tests/strategy_tests/run_strategy_tests.py` | Tests 24 strategy-selection configurations on 2016–2020 data: K 3/4, EW or IV weighting at three rebalance frequencies, and 20/25/30% holdings. Reports rankings, robustness, significance, turnover, and integrity checks. |
| `python tests/execution_tests/run_execution_tests.py` | Runs the execution engine's synthetic accounting, lot, fee, settlement, dividend, split, delisting, and no-look-ahead tests, plus reproduction of the frozen final run. |

## Ablation analysis (2016–2026)

The ablation module isolates the effect of factor-selection breadth and portfolio weighting under the frozen weekly strategy configuration. It compares four variants:

| Variant | Number of factors | Weighting |
|---|---:|---|
| `K6_EW` | 6 | Equal weight |
| `K6_IV` | 6 | Inverse volatility |
| `K3_EW` | 3 | Equal weight |
| `K3_IV` | 3 | Inverse volatility |

Run the calculation first:

```bash
python tests/ablation_tests/src/run_ablation.py
```

Then create the figures from the saved results, without rerunning the backtest:

```bash
python tests/ablation_tests/src/plot_ablation.py
```

Add the STI total-return series to the cumulative-wealth chart when needed:

```bash
python tests/ablation_tests/src/plot_ablation.py --include-sti
```

The calculation writes its CSV and methodology artifacts to `tests/ablation_tests/results/`; the plotting script writes PNG and PDF figures to `tests/ablation_tests/figures/`. The module is not part of `tests/run_all_tests.py`, because it is a research ablation that reruns the full weekly backtest for four configurations.

## Factor diagnostics (2016–2026)

The factor diagnostics assess the final adaptive Top-3 strategy after its main backtest has produced the required inputs. They are not part of `tests/run_all_tests.py`, because a fresh checkout does not necessarily contain the strategy-output files.

First generate the final main-backtest outputs:

```bash
python run_backtest.py --skip-execution
```

Then generate the diagnostic results and figures:

```bash
python tests/factor_diagnostics/run_factor_diagnostics.py
```

The diagnostics read:

- `outputs/SG_Adaptive_K3_IVweekly_Top20/01_factor_returns_weekly.csv`
- `outputs/SG_Adaptive_K3_IVweekly_Top20/02_annual_style_decisions.csv`

They write to `tests/factor_diagnostics/`:

| Location | Content |
|---|---|
| `results/factor_predictability_2016_2026.csv` | Annualized returns for the selected Top-3 and unselected Bottom-3 factors, their spread, and weekly coverage. |
| `figures/factor_predictability_2016_2026.png/.pdf` | Predictive-validity chart for annual adaptive Top-3 selection. |
| `figures/factor_volatility_boxplot.png/.pdf` | Distribution of trailing 52-week long-short factor volatility. |
