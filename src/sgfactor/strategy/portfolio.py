"""Weekly target holdings from composite scores.

  N_target = max(1, floor(select_fraction * N)) names, equal weight 1 / N_target, long only.
  Buffer: last week's names are kept while they rank inside the top exit_fraction; the rest
          of the book is filled with the best-ranked new names.
  Sector cap: at most floor(sector_cap * N_target) names per sector; a name whose sector is
          full is skipped. Unfilled weight stays in cash.
Ranking: composite score descending, ties by ticker.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd


def _one_week(week: pd.DataFrame, previous: set[str], select_fraction: float, exit_fraction: float,
              sector_cap: float, use_buffer: bool) -> pd.DataFrame:
    ranked = week.sort_values(["composite_score", "ticker"], ascending=[False, True], kind="mergesort")
    ranked = ranked.reset_index(drop=True)
    ranked["rank"] = np.arange(1, len(ranked) + 1)
    n = len(ranked)
    n_target = max(1, math.floor(select_fraction * n))
    n_exit = math.floor(exit_fraction * n)
    cap = math.floor(sector_cap * n_target)
    if use_buffer and previous:
        keep = ranked["ticker"].isin(previous) & (ranked["rank"] <= n_exit)
        ranked = pd.concat([ranked[keep], ranked[~keep]])
    picked, per_sector = [], {}
    for row in ranked.itertuples(index=False):
        if len(picked) == n_target or cap < 1:
            break
        if per_sector.get(row.sector, 0) >= cap:
            continue
        per_sector[row.sector] = per_sector.get(row.sector, 0) + 1
        picked.append(row)
    hold = pd.DataFrame(picked, columns=ranked.columns)
    hold["weight"] = 1.0 / n_target
    hold["status"] = np.where(~hold["ticker"].isin(previous), "NEW",
                              np.where(hold["rank"] > n_target, "KEPT_BY_BUFFER", "KEPT"))
    return hold


def build_holdings(composite: pd.DataFrame, select_fraction: float = 0.20, exit_fraction: float = 0.30,
                   sector_cap: float = 0.30, use_buffer: bool = True) -> pd.DataFrame:
    weeks, previous = [], set()
    for _, week in composite.groupby("signal_date", sort=True):
        hold = _one_week(week, previous, select_fraction, exit_fraction, sector_cap, use_buffer)
        weeks.append(hold)
        previous = set(hold["ticker"])
    cols = ["signal_date", "execution_date", "ticker", "sector", "composite_score", "rank", "status", "weight"]
    return pd.concat(weeks, ignore_index=True)[cols]
