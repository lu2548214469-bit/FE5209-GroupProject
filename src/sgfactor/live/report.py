"""Course performance metrics (FE5209 'Group Project: Performance Metric') from the execution account.

All figures come from the daily execution account (real board-lot trades, fees, T+2, dividends), not
from the weekly research backtest. A window (a, b] uses the NAV at the close of `a` as its base.

Definitions
  Annual return        (end NAV / start NAV) ** (252 / trading days) - 1
  Annual volatility    std of daily NAV returns * sqrt(252)
  Sharpe ratio         mean / std of daily NAV returns * sqrt(252), risk-free rate 0
  Max drawdown         largest fall of the NAV from a running peak (the start NAV counts as a peak)
  Drawdown patterns    number of separate drawdowns: spells where the NAV is below its running peak,
                       each ending when a new peak is made (or at the end of the window)
  Number of trades     executions (fills) in the window; buys and sells are also shown
  Position trades      one position trade = one stock from the day it is first held until it is fully
                       sold; positions open at the window edges are cut at the edges and marked at the close
  Win rate             share of position trades with a profit in the window (price change + dividends
                       - fees - slippage, from the engine's per-stock daily contribution)
  Average holding      trading days a position trade is held inside the window
  Profit per trade     total profit of position trades / number of position trades (SGD)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

DAYS = 252


def _drawdown_spells(nav: pd.Series, base: float) -> tuple[int, int, float]:
    n = np.r_[base, nav.to_numpy(float)]
    peak = np.maximum.accumulate(n)
    under = n < peak - 1e-9
    starts = int(np.sum(under[1:] & ~under[:-1]))
    longest, run = 0, 0
    for u in under:
        run = run + 1 if u else 0
        longest = max(longest, run)
    return starts, longest, float(np.max(1 - n / peak))


def position_trades(ex: dict, a: pd.Timestamp, b: pd.Timestamp) -> pd.DataFrame:
    """One row per position trade inside the window (a, b]."""
    h = ex["holdings"][["date", "ticker", "shares"]].copy()
    c = ex["contributions"][["date", "ticker", "contribution_amount"]].copy()
    for t in (h, c):
        t["date"] = pd.to_datetime(t["date"])
    sessions = pd.DatetimeIndex(sorted(pd.to_datetime(ex["daily"]["date"]).unique()))
    rows = []
    for tk, g in h[h.shares > 0].groupby("ticker"):
        held = pd.Series(False, index=sessions)
        held[pd.DatetimeIndex(g["date"])] = True
        starts = held & ~held.shift(1, fill_value=False)
        ep = starts.cumsum()                       # episode number, carried forward past the exit
        cc = c[c.ticker == tk]
        cc = cc.assign(ep=ep.reindex(cc["date"]).to_numpy())
        win_c = cc[(cc.date > a) & (cc.date <= b) & (cc.ep > 0)]
        win_h = held[(held.index > a) & (held.index <= b)]
        for e in sorted(set(win_c.ep) | set(ep[win_h[win_h].index])):
            days = int((win_h & (ep.reindex(win_h.index) == e)).sum())
            pnl = float(win_c.loc[win_c.ep == e, "contribution_amount"].sum())
            rows.append({"ticker": tk, "episode": int(e), "held_days_in_window": days, "pnl_sgd": pnl})
    return pd.DataFrame(rows, columns=["ticker", "episode", "held_days_in_window", "pnl_sgd"])


def course_metrics(ex: dict, a: str, b: str, sti_levels: pd.Series | None = None) -> dict:
    a, b = pd.Timestamp(a), pd.Timestamp(b)
    d = ex["daily"].assign(date=lambda x: pd.to_datetime(x["date"])).set_index("date")
    base = float(d["nav"].loc[:a].iloc[-1]) if (d.index <= a).any() else float(ex["audit"]["config"]["initial_cash"])
    nav = d.loc[(d.index > a) & (d.index <= b), "nav"]
    r = pd.concat([pd.Series([base]), nav.reset_index(drop=True)]).pct_change().dropna()
    n = len(r)
    cum = float(nav.iloc[-1] / base - 1)
    spells, longest, mdd = _drawdown_spells(nav, base)
    f = ex["fills"].assign(date=lambda x: pd.to_datetime(x["date"]))
    f = f[(f.date > a) & (f.date <= b)]
    pt = position_trades(ex, a, b)
    down = r[r < 0]
    out = {
        "window": f"{a.date()} close .. {b.date()} close", "trading_days": n,
        "start_nav_sgd": base, "end_nav_sgd": float(nav.iloc[-1]), "pnl_sgd": float(nav.iloc[-1] - base),
        "cumulative_return": cum,
        "annual_return": float((1 + cum) ** (DAYS / n) - 1),
        "annual_volatility": float(r.std(ddof=1) * np.sqrt(DAYS)),
        "sharpe_ratio_rf0": float(r.mean() / r.std(ddof=1) * np.sqrt(DAYS)),
        "max_drawdown": mdd,
        "drawdown_count": spells, "longest_drawdown_days": longest,
        "win_rate_position_trades": float((pt.pnl_sgd > 0).mean()) if len(pt) else np.nan,
        "number_of_trades_fills": int(len(f)),
        "buys": int((f.shares > 0).sum()), "sells": int((f.shares < 0).sum()),
        "position_trades": int(len(pt)),
        "avg_holding_period_days": float(pt.held_days_in_window.mean()) if len(pt) else np.nan,
        "profit_per_trade_sgd": float(pt.pnl_sgd.mean()) if len(pt) else np.nan,
        "sortino_ratio_rf0": float(r.mean() / np.sqrt((down ** 2).mean()) * np.sqrt(DAYS)) if len(down) else np.nan,
        "calmar_ratio": float(((1 + cum) ** (DAYS / n) - 1) / mdd) if mdd > 0 else np.nan,
        "daily_win_rate": float((r > 0).mean()),
        "best_day": float(r.max()), "worst_day": float(r.min()),
        "fees_sgd": float(f.total_fee.sum()), "slippage_sgd": float(f.slippage_cost.sum()),
        "dividends_sgd": float(d.loc[nav.index, "action_income"].sum()),
        "turnover_traded_value_over_avg_nav": float(f.notional.abs().sum() / nav.mean()),
    }
    if sti_levels is not None:
        s = sti_levels.copy()
        s.index = pd.to_datetime(s.index)
        s = s.reindex(nav.index.union([a]), method="ffill")
        sr = s.pct_change().dropna()
        scum = float(s.iloc[-1] / s.iloc[0] - 1)
        _, _, smdd = _drawdown_spells(s.iloc[1:], float(s.iloc[0]))
        out.update({"STI_cumulative_return": scum, "STI_annual_return": float((1 + scum) ** (DAYS / n) - 1),
                    "STI_annual_volatility": float(sr.std(ddof=1) * np.sqrt(DAYS)),
                    "STI_sharpe_ratio_rf0": float(sr.mean() / sr.std(ddof=1) * np.sqrt(DAYS)),
                    "STI_max_drawdown": smdd, "excess_return_vs_STI": cum - scum})
    return out


def metrics_table(windows: dict[str, dict]) -> pd.DataFrame:
    return pd.DataFrame(windows).rename_axis("metric")


def portfolio_prices(ex_targets: pd.DataFrame, prices_path, start: str, end: str) -> pd.DataFrame:
    """Course deliverable: the assets in the portfolio and their daily closing prices (wide CSV)."""
    tickers = sorted(ex_targets["ticker"].unique())
    p = pd.read_csv(prices_path, usecols=["date", "ticker", "close"])
    p = p[p.ticker.isin(tickers) & (p.date >= start) & (p.date <= end)]
    return p.pivot(index="date", columns="ticker", values="close").sort_index()
