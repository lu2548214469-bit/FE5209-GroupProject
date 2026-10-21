"""Single-factor tests, 2011-2015 (factor-selection period).

    python tests/factor_tests/run_factor_tests.py            # about 1-2 minutes
    python tests/factor_tests/run_factor_tests.py --no-plots

Code and frozen results come from the teammate's branch research/sg-single-factor-independent
(src/, results/, figures/, Six_Factor_Analysis_2011_2015.md in this folder). The four analysis
scripts are unchanged except that they read data/factor_test_panel.csv.gz from this repository:
the same columns of the final FX-complete panel (sg_six_factor_panel_2006_2026_final.csv.gz,
SHA-256 ad7f37af...) that the branch used.

Steps
  1  performance  Rank IC / ICIR, top-30% minus bottom-30% long-short, quintiles, Top-20 excess, coverage
  2  validation   HAC (Newey-West, 4 lags) tests, Top-20% excess, annual compounded long-short
  3  robustness   year-by-year stability, universe-filter sensitivity (reads step 1 output)
  4  correlation  factor rank correlations, fixed equal-weight composites, leave-one-out increments
  5  figures      21 figures (PNG + PDF) from the new results
  6  check        every rerun CSV is compared with the branch's frozen results
Two samples throughout: PRICE_ELIGIBLE_TRUE (primary) and ALL_PAIRED (control).
Outputs: outputs/factor_tests/results/<module>/, outputs/factor_tests/figures/<module>/.
"""
from __future__ import annotations

import argparse
import importlib.util
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SRC = HERE / "src"
FROZEN = HERE / "results"
DATA = ROOT / "data" / "factor_test_panel.csv.gz"
OUT = ROOT / "outputs" / "factor_tests"
FACTORS = ["Quality", "Momentum", "LowRisk", "Investment", "Size", "Value"]


def run(script: str, *args: str) -> None:
    print(f"\n>>> {script} {' '.join(args)}", flush=True)
    subprocess.run([sys.executable, str(SRC / script), *args], check=True)


def plots(results: Path, figures: Path) -> None:
    spec = importlib.util.spec_from_file_location("plot_factor_results", SRC / "plot_factor_results.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["plot_factor_results"] = mod
    spec.loader.exec_module(mod)
    mod.RESULTS_DIR = results                      # read the rerun results instead of the frozen ones
    argv, sys.argv = sys.argv, ["plot_factor_results.py", "--outdir", str(figures)]
    try:
        mod.main()
    finally:
        sys.argv = argv


def compare(new: Path, old: Path) -> pd.DataFrame:
    rows = []
    for f in sorted(old.rglob("*.csv")):
        rel = f.relative_to(old)
        g = new / rel
        if not g.exists():
            rows.append({"file": str(rel), "result": "MISSING", "max_abs_diff": np.nan})
            continue
        a, b = pd.read_csv(f), pd.read_csv(g)
        if a.shape != b.shape or list(a.columns) != list(b.columns):
            rows.append({"file": str(rel), "result": "SHAPE DIFFERS", "max_abs_diff": np.nan})
            continue
        num = a.select_dtypes("number").columns
        d = float((a[num] - b[num]).abs().max().max()) if len(num) else 0.0
        same_text = a.drop(columns=num).astype(str).equals(b.drop(columns=num).astype(str))
        ok = (np.isnan(d) or d < 1e-9) and same_text
        rows.append({"file": str(rel), "result": "SAME" if ok else "DIFFERS", "max_abs_diff": d})
    return pd.DataFrame(rows)


def summary(results: Path) -> None:
    pd.set_option("display.width", 220)
    rob = pd.read_csv(results / "robustness" / "factor_robustness_summary.csv")
    val = pd.read_csv(results / "validation" / "PRICE_ELIGIBLE_TRUE_factor_validation_summary.csv")
    for sample in ("PRICE_ELIGIBLE_TRUE", "ALL_PAIRED"):
        r = rob[rob["sample"] == sample].set_index("factor").reindex(FACTORS)
        t = pd.DataFrame({
            "mean Rank IC": r["mean_rank_ic"], "IC HAC t": r["rank_ic_hac_t_4lags"],
            "IC>0 weeks": r["ic_positive_week_rate"], "IC>0 years (of 5)": r["positive_ic_years"],
            "L/S 30% weekly": r["avg_long_short_weekly"], "L/S HAC t": r["long_short_hac_t_4lags"],
            "Top-20 excess weekly": r["avg_top20_excess_weekly"], "Top-20 HAC t": r["top20_excess_hac_t_4lags"],
            "Q1-Q5 weekly": r["q1_minus_q5_mean"]})
        print(f"\n===== {sample}{' (primary)' if sample == 'PRICE_ELIGIBLE_TRUE' else ' (control)'}, 2011-2015, weekly =====\n")
        print(t.round(4).to_string())
    v = val.set_index("factor").reindex(FACTORS)
    print("\nIC HAC p-value (two-sided), PRICE_ELIGIBLE_TRUE: "
          + ", ".join(f"{f} {v.loc[f, 'ic_hac_p_two_sided']:.3f}" for f in FACTORS))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--no-plots", action="store_true")
    a = ap.parse_args()
    res = OUT / "results"
    run("factor_performance.py", "--input", str(DATA), "--outdir", str(res / "performance"))
    run("factor_validation.py", "--input", str(DATA), "--outdir", str(res / "validation"))
    run("factor_robustness.py", "--indir", str(res / "performance"), "--outdir", str(res / "robustness"))
    run("factor_correlation.py", "--input", str(DATA), "--outdir", str(res / "correlation"))
    if not a.no_plots:
        print("\n>>> plot_factor_results.py", flush=True)
        plots(res, OUT / "figures")
    summary(res)
    cmp = compare(res, FROZEN)
    cmp.to_csv(OUT / "reproduction_check.csv", index=False)
    print(f"\n===== Reproduction of the branch's frozen results: "
          f"{(cmp.result == 'SAME').sum()} / {len(cmp)} files identical =====")
    bad = cmp[cmp.result != "SAME"]
    if len(bad):
        print(bad.to_string(index=False))
    print(f"\nOutputs in {OUT}")
    if len(bad):
        sys.exit(1)


if __name__ == "__main__":
    main()
