"""Summary tables for a backtest run."""
from __future__ import annotations

import pandas as pd

from .metrics import performance


def period_mask(index: pd.Index, span: list[str]) -> pd.Series:
    return (index >= span[0]) & (index <= span[1])


def summary_table(weekly: pd.DataFrame, cfg: dict, series: list[str], bench: str = "STI") -> pd.DataFrame:
    rows = []
    for name in ("pre", "obs", "eval"):
        m = period_mask(weekly.index, cfg["periods"][name])
        for s in series:
            r = weekly.loc[m, s]
            p = performance(r, weekly.loc[m, bench] if s != bench else None)
            rows.append({"period": name, "series": s, **p})
    return pd.DataFrame(rows)


def yearly_table(weekly: pd.DataFrame, series: list[str]) -> pd.DataFrame:
    years = weekly.index.str[:4]
    return (1 + weekly[series]).groupby(years).prod() - 1


def live_table(navs: pd.DataFrame) -> pd.DataFrame:
    """Window return, max drawdown and best / worst day of each daily NAV in the live window."""
    rows = []
    for s in navs.columns:
        n = navs[s]
        r = n.pct_change().dropna()
        rows.append({"period": "live", "series": s, "from": str(n.index[0].date()), "to": str(n.index[-1].date()),
                     "trading_days": len(r), "cum_return": float(n.iloc[-1] / n.iloc[0] - 1)
                     if s == "STI" else float(n.iloc[-1] - 1),
                     "max_drawdown": float(-(n / n.cummax() - 1).min()),
                     "worst_day": float(r.min()), "best_day": float(r.max())})
    return pd.DataFrame(rows)
