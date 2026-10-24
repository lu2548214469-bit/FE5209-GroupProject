#!/usr/bin/env python3
"""Create figures from existing 2x2 ablation outputs without rerunning a backtest.

Run from the repository root:
    python tests/ablation_tests/src/plot_ablation.py

Use ``--include-sti`` to add the STI total-return line to the wealth chart.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.figure import Figure
from matplotlib.ticker import PercentFormatter

BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_RESULTS_DIR = BASE_DIR / "results"
DEFAULT_FIGURES_DIR = BASE_DIR / "figures"
VARIANT_ORDER = ("K6_EW", "K6_IV", "K3_EW", "K3_IV")
VARIANT_COLORS = {
    "K6_EW": "#95A0AE",
    "K6_IV": "#4477AA",
    "K3_EW": "#44AA99",
    "K3_IV": "#D97706",
}
EVALUATION_PERIOD = "EVAL_2021_2026SEP"
EVALUATION_START = pd.Timestamp("2021-01-01")
PLOT_END = pd.Timestamp("2026-09-18")
METRICS = (
    ("annual_return", "Annualized Return", True),
    ("sharpe", "Sharpe Ratio (rf = 0)", False),
    ("max_drawdown", "Maximum Drawdown", True),
    ("annual_turnover_proxy", "Annualized One-Way Turnover", True),
)


def read_performance(path: Path) -> pd.DataFrame:
    """Load and validate the evaluation-period performance summary."""
    if not path.is_file():
        raise FileNotFoundError(
            f"找不到绩效汇总文件：{path}\n请先运行 run_ablation.py。"
        )

    performance = pd.read_csv(path).rename(
        columns={
            "strategy": "variant",
            "sharpe_rf0": "sharpe",
            "max_drawdown_positive": "max_drawdown",
            "annualized_turnover_proxy": "annual_turnover_proxy",
        }
    )
    required_columns = {
        "period",
        "variant",
        "annual_return",
        "sharpe",
        "max_drawdown",
        "annual_turnover_proxy",
    }
    missing_columns = required_columns - set(performance.columns)
    if missing_columns:
        raise ValueError(
            f"绩效文件缺少列：{sorted(missing_columns)}；"
            f"现有列：{list(performance.columns)}"
        )

    evaluation = performance.loc[
        performance["period"].eq(EVALUATION_PERIOD)
    ].copy()
    if evaluation["variant"].duplicated().any():
        duplicates = evaluation.loc[
            evaluation["variant"].duplicated(keep=False), "variant"
        ].tolist()
        raise ValueError(f"EVAL 绩效文件包含重复策略标签：{duplicates}")

    evaluation = evaluation.set_index("variant").reindex(VARIANT_ORDER)
    numeric_columns = [metric for metric, _, _ in METRICS]
    if evaluation[numeric_columns].isna().any().any():
        raise ValueError("EVAL 四组绩效存在缺失值，请检查原实验结果。")
    return evaluation


def read_weekly(path: Path) -> tuple[pd.DataFrame, pd.Series | None]:
    """Load weekly strategy returns and the optional shared STI return series."""
    if not path.is_file():
        raise FileNotFoundError(
            f"找不到逐周收益文件：{path}\n请先运行 run_ablation.py。"
        )

    weekly = pd.read_csv(path)
    required_columns = {"signal_date", "strategy"}
    missing_columns = required_columns - set(weekly.columns)
    if missing_columns:
        raise ValueError(
            f"周度数据缺少列：{sorted(missing_columns)}；"
            f"实际列：{list(weekly.columns)}"
        )

    variant_column = next(
        (column for column in ("variant", "ablation_strategy") if column in weekly),
        None,
    )
    if variant_column is None:
        raise ValueError("周度数据缺少 variant / ablation_strategy 策略标签。")

    weekly["signal_date"] = pd.to_datetime(weekly["signal_date"], errors="raise")
    if weekly.duplicated(["signal_date", variant_column]).any():
        raise ValueError("逐周数据存在重复 (signal_date, variant)，停止绘图。")

    returns = (
        weekly.pivot(
            index="signal_date", columns=variant_column, values="strategy"
        )
        .sort_index()
        .reindex(columns=VARIANT_ORDER)
        .apply(pd.to_numeric, errors="coerce")
    )
    returns = returns.loc[returns.index <= PLOT_END]
    if returns.empty or returns.isna().any().any() or (returns <= -1).any().any():
        raise ValueError("四组周度收益不完整或收益率不合法，拒绝用 0 填充。")

    sti = _read_sti(weekly, returns.index)
    return returns, sti


def _read_sti(weekly: pd.DataFrame, dates: pd.Index) -> pd.Series | None:
    """Return one STI value per date and reject inconsistent benchmark inputs."""
    if "STI" not in weekly.columns:
        return None

    sti_data = weekly[["signal_date", "STI"]].copy()
    values_per_date = sti_data.groupby("signal_date")["STI"].nunique(dropna=False)
    if values_per_date.gt(1).any():
        raise ValueError("同一周四个实验所用 STI 不一致。")
    return (
        pd.to_numeric(
            sti_data.drop_duplicates("signal_date").set_index("signal_date")["STI"],
            errors="coerce",
        )
        .reindex(dates)
    )


def save_figure(figure: Figure, output_stem: Path) -> None:
    """Save a chart as matching high-resolution PNG and vector PDF files."""
    figure.tight_layout()
    for extension in ("png", "pdf"):
        figure.savefig(
            output_stem.with_suffix(f".{extension}"),
            dpi=300,
            bbox_inches="tight",
        )
    plt.close(figure)


def _style_axis(axis: plt.Axes) -> None:
    """Apply the shared clean style used by every chart axis."""
    axis.grid(axis="y", alpha=0.18)
    axis.set_axisbelow(True)
    axis.spines[["top", "right"]].set_visible(False)


def _bar_limits(values: pd.Series | np.ndarray) -> tuple[float, float]:
    """Return axis limits with headroom for positive, negative, or mixed bars."""
    minimum = float(np.min(values))
    maximum = float(np.max(values))
    if minimum == maximum:
        padding = abs(maximum) * 0.20 or 1.0
        return minimum - padding, maximum + padding
    padding = (maximum - minimum) * 0.15
    return min(0.0, minimum - padding), max(0.0, maximum + padding)


def plot_cumulative_wealth(
    weekly_returns: pd.DataFrame,
    sti_returns: pd.Series | None,
    output_dir: Path,
    include_sti: bool,
) -> None:
    """Plot cumulative wealth for all variants, optionally against STI."""
    figure, axis = plt.subplots(figsize=(11.8, 5.9))
    wealth = (1 + weekly_returns).cumprod()

    for variant in VARIANT_ORDER:
        is_reference = variant == "K3_IV"
        axis.plot(
            wealth.index,
            wealth[variant],
            color=VARIANT_COLORS[variant],
            linewidth=2.5 if is_reference else 1.8,
            label=variant,
            zorder=4 if is_reference else 2,
        )

    if include_sti:
        if sti_returns is None or sti_returns.isna().any():
            raise ValueError("已指定 --include-sti，但周度文件没有完整 STI 数据。")
        axis.plot(
            sti_returns.index,
            (1 + sti_returns).cumprod(),
            color="#222222",
            linestyle="--",
            linewidth=1.5,
            label="STI Total Return",
        )

    axis.axvline(EVALUATION_START, color="#777777", linestyle=":", linewidth=1.2)
    axis.axhline(1, color="#777777", linestyle=":", linewidth=0.6)
    axis.annotate(
        "Evaluation starts",
        xy=(EVALUATION_START, 1),
        xycoords=("data", "axes fraction"),
        xytext=(10, -26),
        textcoords="offset points",
        color="#666666",
        fontsize=9,
        va="top",
    )
    axis.set_title(
        f"2×2 Ablation: Cumulative Wealth ({wealth.index.min():%Y}–{wealth.index.max():%b %Y})",
        fontsize=15,
    )
    axis.set_ylabel("Growth of 1 (net of 10 bp one-way costs)")
    axis.set_xlabel("Year")
    axis.xaxis.set_major_locator(mdates.YearLocator(2))
    axis.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    axis.legend(ncol=3, frameon=False, loc="upper left")
    _style_axis(axis)
    save_figure(figure, output_dir / "a01_cumulative_wealth")


def plot_evaluation_metrics(evaluation: pd.DataFrame, output_dir: Path) -> None:
    """Plot the four evaluation-period metrics for every ablation variant."""
    figure, axes = plt.subplots(2, 2, figsize=(11.8, 7.2))

    for axis, (metric, title, is_percentage) in zip(axes.flat, METRICS):
        values = evaluation[metric].astype(float)
        if metric == "max_drawdown":
            values = values.abs()
        bars = axis.bar(
            np.arange(len(VARIANT_ORDER)),
            values,
            color=[VARIANT_COLORS[variant] for variant in VARIANT_ORDER],
            width=0.64,
        )
        axis.set_title(title, pad=12)
        axis.set_xticks(np.arange(len(VARIANT_ORDER)), VARIANT_ORDER)
        lower_limit, upper_limit = _bar_limits(values)
        axis.set_ylim(lower_limit, upper_limit)
        if is_percentage:
            axis.yaxis.set_major_formatter(PercentFormatter(xmax=1))

        label_offset = (upper_limit - lower_limit) * 0.025
        for bar, value in zip(bars, values):
            label = f"{value:.1%}" if is_percentage else f"{value:.2f}"
            axis.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + (label_offset if value >= 0 else -label_offset),
                label,
                ha="center",
                va="bottom" if value >= 0 else "top",
                fontsize=9,
            )
        _style_axis(axis)

    figure.suptitle(
        "2×2 Ablation: Evaluation Period (2021–Sep 2026)", fontsize=15
    )
    save_figure(figure, output_dir / "a02_eval_metrics")


def parse_args() -> argparse.Namespace:
    """Parse command-line paths and chart options."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--performance",
        type=Path,
        default=DEFAULT_RESULTS_DIR / "ablation_performance.csv",
    )
    parser.add_argument(
        "--weekly",
        type=Path,
        default=DEFAULT_RESULTS_DIR / "ablation_weekly_returns.csv",
    )
    parser.add_argument("--outdir", type=Path, default=DEFAULT_FIGURES_DIR)
    parser.add_argument("--include-sti", action="store_true")
    return parser.parse_args()


def main() -> None:
    """Load validated ablation outputs and write both figure pairs."""
    args = parse_args()
    evaluation = read_performance(args.performance)
    weekly_returns, sti_returns = read_weekly(args.weekly)
    args.outdir.mkdir(parents=True, exist_ok=True)

    plot_cumulative_wealth(
        weekly_returns, sti_returns, args.outdir, args.include_sti
    )
    plot_evaluation_metrics(evaluation, args.outdir)

    print(f"完成：{args.outdir.resolve()}")
    print("a01_cumulative_wealth.png/.pdf")
    print("a02_eval_metrics.png/.pdf")


if __name__ == "__main__":
    main()
