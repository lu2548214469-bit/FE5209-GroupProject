#!/usr/bin/env python3
"""Run the 2x2 K3/K6 and equal/inverse-volatility weekly ablation.

Run after installing the project from its repository root:
    python -m pip install -e .
    python tests/ablation_tests/src/run_ablation.py
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from sgfactor.backtest import backtest
from sgfactor.backtest.metrics import performance
from sgfactor.config import load_config, override
from sgfactor.data import load_universe
from sgfactor.factors import factor_returns, style_scores

ROOT = Path(__file__).resolve().parents[3]
VARIANTS = {
    "K6_EW": (6, "EW"),
    "K6_IV": (6, "IV"),
    "K3_EW": (3, "EW"),
    "K3_IV": (3, "IV"),
}
PERIODS = {
    "TRAIN_2016_2020": ("2016-01-01", "2020-12-31"),
    "EVAL_2021_2026SEP": ("2021-01-01", "2026-09-18"),
    "FULL_2016_2026SEP": ("2016-01-01", "2026-09-18"),
}


def summarize(
    weekly: pd.DataFrame,
    label: str,
    period: str,
    start: str,
    end: str,
) -> dict[str, object]:
    """Summarize strategy and STI performance for one period."""
    period_data = weekly.loc[(weekly.index >= start) & (weekly.index <= end)]
    if len(period_data) < 2:
        raise ValueError(f"Insufficient rows for {label}/{period}")

    strategy_metrics = performance(period_data["strategy"])
    sti_metrics = performance(period_data["STI"])
    return {
        "period": period,
        "variant": label,
        "weeks": len(period_data),
        "start": str(period_data.index.min()),
        "end": str(period_data.index.max()),
        "annual_return": strategy_metrics["ann_return"],
        "cumulative_return": strategy_metrics["cum_return"],
        "annual_volatility": strategy_metrics["ann_vol"],
        "sharpe": strategy_metrics["sharpe"],
        "max_drawdown": strategy_metrics["max_drawdown"],
        "calmar": strategy_metrics["calmar"],
        "mean_weekly_turnover": float(period_data["one_way_turnover"].mean()),
        "annual_turnover_proxy": float(
            52 * period_data["one_way_turnover"].mean()
        ),
        "mean_n_names": float(period_data["n_names"].mean()),
        "STI_annual_return": sti_metrics["ann_return"],
        "STI_sharpe": sti_metrics["sharpe"],
    }


def effects(summary: pd.DataFrame) -> pd.DataFrame:
    """Calculate each main effect and the K-by-weighting interaction."""
    pairs = {
        "K3_vs_K6_EW": ("K3_EW", "K6_EW"),
        "K3_vs_K6_IV": ("K3_IV", "K6_IV"),
        "IV_vs_EW_K6": ("K6_IV", "K6_EW"),
        "IV_vs_EW_K3": ("K3_IV", "K3_EW"),
    }
    metrics = ("annual_return", "sharpe", "max_drawdown", "annual_turnover_proxy")
    rows: list[dict[str, object]] = []

    for period, group in summary.groupby("period", sort=False):
        table = group.set_index("variant")
        for comparison, (variant_a, variant_b) in pairs.items():
            rows.append(
                {
                    "period": period,
                    "comparison": comparison,
                    **{
                        f"delta_{metric}": float(
                            table.at[variant_a, metric]
                            - table.at[variant_b, metric]
                        )
                        for metric in metrics
                    },
                }
            )

        rows.append(
            {
                "period": period,
                "comparison": "interaction",
                **{
                    f"delta_{metric}": float(
                        table.at["K3_IV", metric]
                        - table.at["K3_EW", metric]
                        - table.at["K6_IV", metric]
                        + table.at["K6_EW", metric]
                    )
                    for metric in metrics
                },
            }
        )

    return pd.DataFrame(rows)


def validate_frozen_config(config: dict) -> None:
    """Ensure the ablation starts from the agreed frozen K3/IV setup."""
    expected_values = [
        ("selection", "top_k", 3),
        ("selection", "lookback_years", 3),
        ("weighting", "method", "IV"),
        ("weighting", "rebalance", "weekly"),
        ("weighting", "window_weeks", 52),
        ("portfolio", "select_fraction", 0.20),
        ("costs", "one_way", 0.001),
    ]
    for section, key, expected in expected_values:
        if config[section][key] != expected:
            raise ValueError(f"Frozen config mismatch: {section}.{key}")

    if len(config["factors"]) != 6:
        raise ValueError("Expected 6 style factors")


def verify_selections(
    decisions: pd.DataFrame,
    label: str,
    factor_names: list[str],
    top_k: int,
) -> None:
    """Verify every annual factor selection matches the variant definition."""
    for decision in decisions.itertuples(index=False):
        selected = [name.strip() for name in decision.selected.split(",")]
        has_expected_count = len(selected) == top_k
        has_unique_factors = len(set(selected)) == top_k
        includes_all_factors = top_k != 6 or set(selected) == set(factor_names)
        if not (has_expected_count and has_unique_factors and includes_all_factors):
            raise ValueError(
                f"Invalid selected factors {label} {decision.year}: {selected}"
            )


def check_reference(
    reference: pd.DataFrame,
    reference_path: Path,
    required: bool,
) -> str:
    """Confirm K3/IV reproduces its frozen weekly baseline when it is available."""
    if reference_path.exists():
        # run_backtest.py writes the signal date as an unnamed first (index) column
        frozen = pd.read_csv(reference_path, index_col=0, parse_dates=[0])["strategy"]
        frozen.index = pd.DatetimeIndex(frozen.index).as_unit("ns")
        frozen.index.name = "signal_date"
        frozen = frozen.sort_index()
        reproduced = reference["strategy"].sort_index()
        reproduced.index = pd.DatetimeIndex(reproduced.index).as_unit("ns")
        matches = frozen.index.equals(reproduced.index) and np.allclose(
            frozen, reproduced, rtol=0, atol=1e-12
        )
        if not matches:
            raise ValueError("Frozen K3_IV baseline reproduction FAILED")
        return "PASS"

    if required:
        raise FileNotFoundError(
            f"Frozen baseline reference not found: {reference_path}"
        )

    print("NOTICE: frozen reference not found; K3_IV reproduction not checked")
    return "NOT_CHECKED"


def write_outputs(
    output_dir: Path,
    summaries: list[dict[str, object]],
    weeklies: list[pd.DataFrame],
    decisions: list[pd.DataFrame],
    baseline_status: str,
) -> pd.DataFrame:
    """Write every ablation artifact and return the performance summary."""
    output_dir.mkdir(parents=True, exist_ok=True)
    summary = pd.DataFrame(summaries)
    summary.to_csv(output_dir / "ablation_performance.csv", index=False)
    effects(summary).to_csv(output_dir / "ablation_effects.csv", index=False)
    pd.concat(weeklies, ignore_index=True).to_csv(
        output_dir / "ablation_weekly_returns.csv", index=False
    )
    pd.concat(decisions, ignore_index=True).to_csv(
        output_dir / "ablation_annual_decisions.csv", index=False
    )
    methodology = {
        "variants": VARIANTS,
        "periods": PERIODS,
        "K3_IV_frozen_comparison": baseline_status,
        "costs": "Part A weekly net 10bp one-way; not Part B account",
        "max_drawdown": "positive loss magnitude",
        "same_parameters": (
            "3y selection lookback; IV 52w, bounds 5%-80%, weekly; top20% "
            "holdings, buffer 30%, sector cap 30%"
        ),
        "selection": (
            "K3 annually selects 3 based on mean/std completed factor L/S; "
            "K6 includes all 6"
        ),
        "note": (
            "Train 2016-20 used for configuration selection; evaluation "
            "2021-Sep2026 separate"
        ),
        "outputs": [
            "ablation_performance.csv",
            "ablation_effects.csv",
            "ablation_weekly_returns.csv",
            "ablation_annual_decisions.csv",
        ],
    }
    (output_dir / "methodology.json").write_text(
        json.dumps(methodology, indent=2), encoding="utf-8"
    )
    return summary


def main() -> None:
    """Run all four ablation variants and write their comparison artifacts."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=ROOT / "tests/ablation_tests/results"
    )
    parser.add_argument(
        "--reference",
        type=Path,
        default=ROOT / "outputs/SG_Adaptive_K3_IVweekly_Top20/05_weekly_returns.csv",
    )
    parser.add_argument("--require-reference", action="store_true")
    args = parser.parse_args()

    base_config = load_config()
    validate_frozen_config(base_config)
    universe = load_universe(base_config)
    factor_names = list(base_config["factors"])
    factor_returns_data = factor_returns(
        style_scores(universe, base_config),
        factor_names,
        base_config["factor_returns"]["leg_fraction"],
    )
    summaries: list[dict[str, object]] = []
    weekly_results: list[pd.DataFrame] = []
    annual_decisions: list[pd.DataFrame] = []
    strategy_series: dict[str, pd.DataFrame] = {}

    for label, (top_k, method) in VARIANTS.items():
        print(f"Running {label}", flush=True)
        config = override(
            base_config,
            **{
                "selection.top_k": top_k,
                "weighting.method": method,
                "weighting.rebalance": "weekly",
            },
        )
        run = backtest(config, universe, factor_returns_data)
        weekly = run["weekly"].sort_index()
        decisions = run["decisions"]
        verify_selections(decisions, label, factor_names, top_k)

        required_columns = ["strategy", "STI", "EW_universe", "one_way_turnover"]
        if weekly[required_columns].isna().any().any():
            raise ValueError(f"Missing weekly values for {label}")

        weekly_output = weekly.reset_index().rename(
            columns={weekly.index.name or "index": "signal_date"}
        )
        weekly_output.insert(1, "variant", label)
        weekly_results.append(weekly_output)

        decisions_output = decisions.copy()
        decisions_output.insert(0, "variant", label)
        annual_decisions.append(decisions_output)

        for period, (start, end) in PERIODS.items():
            summaries.append(summarize(weekly, label, period, start, end))
        strategy_series[label] = weekly

    frozen_reference = strategy_series["K3_IV"]
    for label, weekly in strategy_series.items():
        if not weekly.index.equals(frozen_reference.index):
            raise ValueError(f"Different observation dates for {label}")
        for column in ("STI", "EW_universe"):
            if not np.allclose(
                weekly[column], frozen_reference[column], rtol=0, atol=1e-12
            ):
                raise ValueError(f"Benchmark differs for {label}: {column}")

    baseline_status = check_reference(
        frozen_reference, args.reference.resolve(), args.require_reference
    )
    output_dir = args.output.resolve()
    summary = write_outputs(
        output_dir,
        summaries,
        weekly_results,
        annual_decisions,
        baseline_status,
    )
    columns = [
        "period",
        "variant",
        "annual_return",
        "sharpe",
        "max_drawdown",
        "annual_turnover_proxy",
    ]
    print(summary[columns].round(4).to_string(index=False))
    print(
        f"Frozen K3_IV baseline: {baseline_status} | Outputs: {output_dir} | "
        "No figures generated"
    )


if __name__ == "__main__":
    main()
