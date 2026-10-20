"""Adaptive style selection (once a year, using only completed history).

At the first signal week of each year, look back `lookback_years` over weekly factor returns
whose holding period has already ended, score each style by mean / std, and keep the best K.
A style needs at least floor(lookback_years * 52 * min_coverage) weeks to be eligible.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd


def select_styles(fret: pd.DataFrame, cutoff: str, styles: list[str], top_k: int,
                  lookback_years: int = 3, min_coverage: float = 0.65) -> tuple[list[str], pd.DataFrame]:
    cutoff_ts = pd.Timestamp(cutoff)
    start = cutoff_ts - pd.DateOffset(years=lookback_years)
    end = pd.to_datetime(fret["next_execution_date"])
    hist = fret[fret["style"].isin(styles) & (end > start) & (end <= cutoff_ts)
                & np.isfinite(fret["factor_return"])]
    stats = hist.groupby("style")["factor_return"].agg(["count", "mean", "std"]).reindex(styles)
    min_obs = math.floor(lookback_years * 52 * min_coverage)
    stats["eligible"] = (stats["count"] >= min_obs) & (stats["std"] > 0)
    stats["score"] = np.where(stats["eligible"], stats["mean"] / stats["std"], np.nan)
    stats = stats.reset_index().sort_values(["score", "style"], ascending=[False, True], na_position="last")
    chosen = stats[stats["eligible"]].head(top_k)["style"].tolist()
    if len(chosen) < top_k:
        raise ValueError(f"only {len(chosen)} eligible styles at {cutoff}")
    stats["selected"] = stats["style"].isin(chosen)
    return chosen, stats.reset_index(drop=True)
