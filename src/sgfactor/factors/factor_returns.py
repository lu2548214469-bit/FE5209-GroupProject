"""Weekly long-short return of each style factor.

Each signal week: rank the universe by the style score, long the top 30% and short the bottom 30%
(count = floor(0.30 * N), ties broken by ticker), equal weight, held from execution close to the
next execution close. Factor return = long-leg mean - short-leg mean.
"""
from __future__ import annotations

import math

import pandas as pd


def _leg_mean(week: pd.DataFrame, style: str, n: int, top: bool) -> float:
    ranked = week.sort_values([style, "ticker"], ascending=[not top, True])
    return float(ranked["forward_return"].head(n).mean())


def factor_returns(scores: pd.DataFrame, styles: list[str], leg_fraction: float = 0.30) -> pd.DataFrame:
    """Long table: signal_date, next_execution_date, style, factor_return."""
    rows = []
    for signal_date, week in scores.groupby("signal_date", sort=True):
        n = math.floor(leg_fraction * len(week))
        nxt = str(week["next_execution_date"].iloc[0])
        for style in styles:
            r = _leg_mean(week, style, n, True) - _leg_mean(week, style, n, False) if n >= 1 else float("nan")
            rows.append({"signal_date": signal_date, "next_execution_date": nxt, "style": style,
                         "factor_return": r})
    return pd.DataFrame(rows)
