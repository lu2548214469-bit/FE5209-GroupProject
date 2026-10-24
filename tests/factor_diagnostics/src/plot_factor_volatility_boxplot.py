"""Plot the distribution of trailing 52-week factor volatility."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.ticker import FuncFormatter

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
DIAGNOSTICS_ROOT = Path(__file__).resolve().parents[1]
SOURCE = REPOSITORY_ROOT / "outputs/SG_Adaptive_K3_IVweekly_Top20/01_factor_returns_weekly.csv"
FIGURES_DIR = DIAGNOSTICS_ROOT / "figures"

STYLES = ["Quality", "Momentum", "Low Risk", "Investment", "Size", "Value"]
START = pd.Timestamp("2016-01-01")
END = pd.Timestamp("2026-09-30")

def _require_source() -> None:
    """Raise a clear error when the required main-backtest artifact is absent."""
    if not SOURCE.is_file():
        raise FileNotFoundError(
            f"Missing main-backtest output: {SOURCE}\n"
            "Run `python run_backtest.py --skip-execution` first."
        )


def main() -> None:
    """Calculate and plot trailing 52-week volatility distributions."""
    _require_source()
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(
        SOURCE,
        parse_dates=["signal_date", "next_execution_date"]
    )

    df["factor_return"] = pd.to_numeric(
        df["factor_return"], errors="coerce"
    )

    df = df[
        df["next_execution_date"].notna()
        & (df["next_execution_date"] <= END)
        & df["style"].isin(STYLES)
    ].copy()

    df = df.sort_values(["style", "next_execution_date"])

    if df.duplicated(["style", "signal_date"]).any():
        raise ValueError("Duplicate factor-week observations")

    df["rolling_vol"] = (
        df.groupby("style")["factor_return"]
        .transform(lambda x: x.rolling(52, min_periods=52).std())
    )

    df = df[
        (df["next_execution_date"] >= START)
        & (df["next_execution_date"] <= END)
    ].copy()

    data = [
        df.loc[df["style"] == style, "rolling_vol"].dropna().to_numpy() * 100
        for style in STYLES
    ]

    if any(len(x) == 0 for x in data):
        raise ValueError("Missing volatility observations")

    fig, ax = plt.subplots(figsize=(11.5, 5.4))

    bp = ax.boxplot(
        data,
        patch_artist=True,
        showfliers=False,
        widths=0.52,
        whis=1.5,
        medianprops={"color": "#07334B", "linewidth": 2.2},
        boxprops={"edgecolor": "#00838F", "linewidth": 1.4},
        whiskerprops={"color": "#64748B", "linewidth": 1.3},
        capprops={"color": "#64748B", "linewidth": 1.3},
    )

    for patch in bp["boxes"]:
        patch.set_facecolor("#CDECEF")
        patch.set_alpha(0.95)

    ax.set_xticks(range(1, len(STYLES) + 1))
    ax.set_xticklabels(STYLES, fontsize=12)

    ax.set_ylabel(
        "Trailing 52-Week Volatility (%)",
        fontsize=12,
        color="#07334B",
    )

    ax.set_title(
        "Historical Factor Volatility Distribution",
        fontsize=17,
        fontweight="bold",
        color="#07334B",
        pad=16,
    )

    ax.text(
        0.5, 1.01,
        "Weekly long-short factor returns | 2016–Sep 2026",
        transform=ax.transAxes,
        ha="center",
        va="bottom",
        fontsize=10,
        color="#64748B",
    )

    ax.yaxis.set_major_formatter(
        FuncFormatter(lambda y, _: f"{y:.1f}%")
    )

    ax.grid(axis="y", linestyle="--", alpha=0.20)
    ax.set_axisbelow(True)

    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)

    fig.tight_layout()

    fig.savefig(
        FIGURES_DIR / "factor_volatility_boxplot.png",
        dpi=300,
        bbox_inches="tight",
        facecolor="white",
    )

    fig.savefig(
        FIGURES_DIR / "factor_volatility_boxplot.pdf",
        bbox_inches="tight",
        facecolor="white",
    )

    plt.close(fig)

    summary = (
        df.groupby("style")["rolling_vol"]
        .agg(["median", "mean", "min", "max", "count"])
        .reindex(STYLES)
        * 1
    )

    for col in ["median", "mean", "min", "max"]:
        summary[col] *= 100

    print("\n=== ROLLING 52W VOLATILITY SUMMARY ===")
    print(summary.round(3).to_string())
    print("\nFigures:", FIGURES_DIR)

if __name__ == "__main__":
    main()
