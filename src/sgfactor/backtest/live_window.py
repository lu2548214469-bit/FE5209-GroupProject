"""Live window with a daily NAV (first trade 2026-10-01).

The live window does not follow the weekly Monday schedule at its start: the first live trade is
at the close of the first live trade date, using the latest weekly signal available before it
(e.g. trade 2026-10-01 on the 2026-09-25 signal). Later trades follow the weekly schedule.
Holdings drift with daily total-return-adjusted closes; each trade pays one_way_cost x the
two-sided weight traded. The portfolio starts from cash, so the first trade pays for the build.
NAV = 1 before the first trade; the window return runs from that close to `end`.
"""
from __future__ import annotations

import pandas as pd

from ..config import resolve


def load_daily_adjusted(cfg: dict) -> pd.DataFrame:
    p = pd.read_csv(resolve(cfg["live_window"]["prices"]), usecols=["date", "ticker", "adj_close"])
    p["date"] = pd.to_datetime(p["date"])
    return p.pivot(index="date", columns="ticker", values="adj_close").sort_index()


def live_schedule(signal_dates, cfg: dict) -> list[tuple[str, str]]:
    """(signal_date, trade_date) pairs: each trade uses the latest weekly signal before it."""
    sig = sorted(signal_dates)
    out = []
    for t in cfg["live_window"]["trade_dates"]:
        before = [s for s in sig if s < t]
        out.append((before[-1], t))
    return out


def daily_nav(targets: dict[str, pd.Series], schedule, adj: pd.DataFrame, end: str, cost: float) -> pd.Series:
    """targets: signal_date -> weights (ticker index). Returns the daily NAV from the first trade to `end`."""
    days = adj.index[(adj.index >= schedule[0][1]) & (adj.index <= end)]
    prices = adj.reindex(days).ffill()
    nav, held, out = 1.0, pd.Series(dtype=float), {}
    trades = {pd.Timestamp(t): s for s, t in schedule}
    for i, d in enumerate(days):
        if i > 0 and len(held):
            growth = prices.loc[d, held.index] / prices.loc[days[i - 1], held.index]
            value = held * growth.fillna(1.0)
            cash = 1.0 - held.sum()
            total = float(value.sum()) + cash
            nav *= total
            held = value / total
        if d in trades:
            w = targets[trades[d]]
            w = w[w.index.isin(prices.columns)]
            idx = w.index.union(held.index)
            gtr = float((w.reindex(idx, fill_value=0) - held.reindex(idx, fill_value=0)).abs().sum())
            nav *= 1 - cost * gtr
            held = w.copy()
        out[d] = nav
    return pd.Series(out, name="nav")


def live_window(holdings: pd.DataFrame, universe: pd.DataFrame, sti_levels: pd.Series, cfg: dict) -> dict:
    lw = cfg["live_window"]
    adj = load_daily_adjusted(cfg)
    sched = live_schedule(universe["signal_date"].unique(), cfg)
    strat = {s: holdings[holdings.signal_date == s].set_index("ticker")["weight"] for s, _ in sched}
    ew = {s: (g := universe[universe.signal_date == s].set_index("ticker")).assign(w=1 / len(g))["w"]
          for s, _ in sched}
    navs = pd.DataFrame({
        "strategy": daily_nav(strat, sched, adj, lw["end"], cfg["costs"]["one_way"]),
        "strategy_stress_cost": daily_nav(strat, sched, adj, lw["end"], cfg["costs"]["stress_one_way"]),
        "EW_universe": daily_nav(ew, sched, adj, lw["end"], 0.0),
    })
    sti = sti_levels.reindex(navs.index, method="ffill")
    navs["STI"] = sti / sti.iloc[0]
    navs.index.name = "date"
    return {"nav": navs, "schedule": sched,
            "holdings": pd.concat({t: strat[s] for s, t in sched}, names=["trade_date", "ticker"]).reset_index()}
