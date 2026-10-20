"""Summary tables for a backtest run."""
from __future__ import annotations

import pandas as pd

from .metrics import performance


def period_mask(index: pd.Index, span: list[str]) -> pd.Series:
    return (index >= span[0]) & (index <= span[1])


def summary_table(weekly: pd.DataFrame, cfg: dict, series: list[str], bench: str = "STI") -> pd.DataFrame:
    rows = []
    for name in ("pre", "obs", "eval", "live"):
        m = period_mask(weekly.index, cfg["periods"][name])
        for s in series:
            r = weekly.loc[m, s]
            if name == "live":      # a few weeks only: annualised ratios would be meaningless
                p = {"weeks": len(r), "cum_return": float((1 + r).prod() - 1)}
            else:
                p = performance(r, weekly.loc[m, bench] if s != bench else None)
            rows.append({"period": name, "series": s, **p})
    return pd.DataFrame(rows)


def yearly_table(weekly: pd.DataFrame, series: list[str]) -> pd.DataFrame:
    years = weekly.index.str[:4]
    return (1 + weekly[series]).groupby(years).prod() - 1
