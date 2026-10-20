"""Performance metrics on weekly returns (52 weeks a year, risk-free rate 0)."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

WEEKS = 52


def performance(r: pd.Series, bench: pd.Series | None = None) -> dict:
    r = r.dropna().astype(float)
    n = len(r)
    if n < 2:
        return {"weeks": n, "cum_return": float((1 + r).prod() - 1) if n else np.nan}
    nav = (1 + r).cumprod()
    ann = float(nav.iloc[-1] ** (WEEKS / n) - 1)
    vol = float(r.std(ddof=1) * math.sqrt(WEEKS))
    mdd = float(-(nav / nav.cummax() - 1).min())
    out = {"weeks": n, "cum_return": float(nav.iloc[-1] - 1), "ann_return": ann, "ann_vol": vol,
           "sharpe": float(r.mean() / r.std(ddof=1) * math.sqrt(WEEKS)), "max_drawdown": mdd,
           "calmar": ann / mdd if mdd > 0 else np.nan, "hit_rate": float((r > 0).mean())}
    if bench is not None:
        b = bench.reindex(r.index)
        ok = b.notna()
        a = (r - b)[ok]
        te = float(a.std(ddof=1) * math.sqrt(WEEKS))
        c = np.cov(r[ok], b[ok], ddof=1)
        out.update({"beta": float(c[0, 1] / c[1, 1]), "active_return": float(a.mean() * WEEKS),
                    "tracking_error": te, "info_ratio": float(a.mean() * WEEKS / te) if te > 0 else np.nan})
    return out


def trade_stats(holdings: pd.DataFrame, universe: pd.DataFrame, one_way_cost: float) -> dict:
    """Round trips: a name entering the book and later leaving it is one trade."""
    m = holdings.merge(universe[["signal_date", "ticker", "forward_return"]], on=["signal_date", "ticker"])
    weeks = {d: i for i, d in enumerate(sorted(m["signal_date"].unique()))}
    m["wk"] = m["signal_date"].map(weeks)
    m = m.sort_values(["ticker", "wk"])
    m["trade"] = m.groupby("ticker")["wk"].diff().ne(1).cumsum()
    t = m.groupby("trade").agg(weeks=("wk", "size"), growth=("forward_return", lambda x: float(np.prod(1 + x))))
    net = (1 - one_way_cost) ** 2 * t["growth"] - 1
    return {"round_trips": int(len(t)), "avg_holding_weeks": float(t["weeks"].mean()),
            "trade_win_rate": float((net > 0).mean()), "avg_profit_per_trade": float(net.mean())}
