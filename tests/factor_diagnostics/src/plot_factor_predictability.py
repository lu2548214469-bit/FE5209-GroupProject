
"""Plot annual out-of-sample validity of the adaptive Top-3 factor selection."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
DIAGNOSTICS_ROOT = Path(__file__).resolve().parents[1]
INPUT_DIR = REPOSITORY_ROOT / "outputs/SG_Adaptive_K3_IVweekly_Top20"
RESULTS_DIR = DIAGNOSTICS_ROOT / "results"
FIGURES_DIR = DIAGNOSTICS_ROOT / "figures"

STYLES = [
    "Quality",
    "Momentum",
    "Low Risk",
    "Investment",
    "Size",
    "Value",
]

START_YEAR = 2016
END_YEAR = 2026
CUTOFF = pd.Timestamp("2026-09-30")


def _require_file(path: Path) -> None:
    """Raise a clear error when the required main-backtest artifact is absent."""
    if not path.is_file():
        raise FileNotFoundError(
            f"Missing main-backtest output: {path}\n"
            "Run `python run_backtest.py --skip-execution` first."
        )


def main() -> None:
    """Calculate and plot annual returns for selected and unselected factors."""
    factor_returns_path = INPUT_DIR / "01_factor_returns_weekly.csv"
    decisions_path = INPUT_DIR / "02_annual_style_decisions.csv"
    _require_file(factor_returns_path)
    _require_file(decisions_path)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    returns = pd.read_csv(
        factor_returns_path,
        parse_dates=["signal_date", "next_execution_date"],
    )

    decisions = pd.read_csv(
        decisions_path
    )

    returns["factor_return"] = pd.to_numeric(
        returns["factor_return"], errors="coerce"
    )

    returns = returns[
        returns["next_execution_date"].notna()
        & (returns["next_execution_date"] <= CUTOFF)
        & (returns["signal_date"].dt.year >= START_YEAR)
        & (returns["signal_date"].dt.year <= END_YEAR)
    ].copy()

    returns["year"] = returns["signal_date"].dt.year

    results = []

    for year in range(START_YEAR, END_YEAR + 1):
        decision = decisions.loc[decisions["year"] == year]

        if len(decision) != 1:
            raise ValueError(
                f"Expected one annual decision for {year}"
            )

        selected = [
            s.strip()
            for s in decision.iloc[0]["selected"].split(",")
        ]

        if len(selected) != 3 or len(set(selected)) != 3:
            raise ValueError(
                f"Invalid Top-3 selection in {year}: {selected}"
            )

        if not set(selected).issubset(STYLES):
            raise ValueError(
                f"Unknown selected factor in {year}"
            )

        unselected = [
            s for s in STYLES if s not in selected
        ]

        year_data = returns[
            returns["year"] == year
        ].copy()

        factor_means = year_data.groupby("style")[
            "factor_return"
        ].mean()

        missing = set(STYLES) - set(factor_means.index)

        if missing:
            raise ValueError(
                f"Missing factor returns in {year}: {missing}"
            )

        selected_return = (
            factor_means.loc[selected].mean() * 52 * 100
        )

        unselected_return = (
            factor_means.loc[unselected].mean() * 52 * 100
        )

        results.append({
            "year": year,
            "selected_top3": ", ".join(selected),
            "unselected_bottom3": ", ".join(unselected),
            "selected_return_pct": selected_return,
            "unselected_return_pct": unselected_return,
            "spread_pp": selected_return - unselected_return,
            "weeks": year_data["signal_date"].nunique(),
        })

    result = pd.DataFrame(results)

    result.to_csv(RESULTS_DIR / "factor_predictability_2016_2026.csv", index=False)

    fig, ax = plt.subplots(figsize=(12.8, 5.6))

    x = np.arange(len(result))
    width = 0.36

    navy = "#173B56"
    teal = "#008C95"
    orange = "#E59A45"

    ax.bar(
        x - width / 2,
        result["selected_return_pct"],
        width,
        color=teal,
        label="Selected Top-3",
    )

    ax.bar(
        x + width / 2,
        result["unselected_return_pct"],
        width,
        color=orange,
        label="Unselected Bottom-3",
    )

    ax.axhline(
        0, color="#64748B", linewidth=0.9
    )

    ax.axvline(
        4.5,
        color="#94A3B8",
        linestyle="--",
        linewidth=1.3,
    )

    ax.set_xticks(x)

    ax.set_xticklabels([
        "2026 YTD" if y == 2026 else str(y)
        for y in result["year"]
    ])

    ax.set_ylabel(
        "Annualized Mean Factor Return (%)",
        fontsize=11,
        color=navy,
    )

    ax.set_title(
        "Predictive Validity of Annual Adaptive Top-3 Selection",
        fontsize=16,
        fontweight="bold",
        color=navy,
        pad=18,
    )

    ax.text(
        2,
        0.98,
        "Model Selection (2016–2020)",
        transform=ax.get_xaxis_transform(),
        ha="center",
        va="top",
        fontsize=10,
        color="#64748B",
    )

    ax.text(
        7.5,
        0.98,
        "OOS Evaluation (2021–2026)",
        transform=ax.get_xaxis_transform(),
        ha="center",
        va="top",
        fontsize=10,
        color="#64748B",
    )

    ax.legend(
        frameon=False,
        ncol=2,
        loc="upper center",
        bbox_to_anchor=(0.5, 1.0),
        fontsize=10,
    )

    ax.grid(
        axis="y",
        linestyle="--",
        alpha=0.18,
    )

    ax.set_axisbelow(True)

    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)

    fig.tight_layout()

    fig.savefig(
        FIGURES_DIR / "factor_predictability_2016_2026.png",
        dpi=300,
        bbox_inches="tight",
        facecolor="white",
    )

    fig.savefig(
        FIGURES_DIR / "factor_predictability_2016_2026.pdf",
        bbox_inches="tight",
        facecolor="white",
    )

    plt.close(fig)

    print("\n=== FACTOR PREDICTABILITY 2016–2026 ===")
    print(result.round(3).to_string(index=False))

    print("\n=== SUMMARY ===")

    print(
        "Years selected outperform:",
        int((result["spread_pp"] > 0).sum()),
        "/",
        len(result),
    )

    print(
        "Average annualized spread:",
        f"{result['spread_pp'].mean():.2f} pp",
    )

    print("\nResults:", RESULTS_DIR)
    print("Figures:", FIGURES_DIR)


if __name__ == "__main__":
    main()

