"""Weekly backtest of target holdings.

Accounting:
  - the book starts in cash; before each rebalance the previous weights have drifted with returns;
  - GTR_t = sum |target - drifted| over stocks (cash excluded), one-way turnover = GTR / 2;
  - net return: 1 + R_net = (1 - c * GTR_t)(1 + R_gross), c = one-way cost;
  - unfilled weight is cash and earns 0.
"""
from __future__ import annotations

import pandas as pd

CASH = "__CASH__"


def weekly_backtest(holdings: pd.DataFrame, universe: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Returns (weekly path, trade ledger)."""
    m = holdings.merge(universe[["signal_date", "ticker", "next_execution_date", "forward_return"]],
                       on=["signal_date", "ticker"], how="left")
    rows, trades, drifted = [], [], {CASH: 1.0}
    for signal_date, week in m.groupby("signal_date", sort=True):
        target = dict(zip(week["ticker"], week["weight"]))
        cash = 1.0 - sum(target.values())
        if cash > 1e-12:
            target[CASH] = cash
        gtr = 0.0
        for k in sorted((set(target) | set(drifted)) - {CASH}):
            delta = target.get(k, 0.0) - drifted.get(k, 0.0)
            gtr += abs(delta)
            if abs(delta) > 1e-15:
                trades.append({"signal_date": signal_date, "execution_date": week["execution_date"].iloc[0],
                               "ticker": k, "from_weight": drifted.get(k, 0.0), "to_weight": target.get(k, 0.0),
                               "side": "BUY" if delta > 0 else "SELL"})
        r = dict(zip(week["ticker"], week["forward_return"].fillna(0.0)))
        gross = sum(w * r.get(k, 0.0) for k, w in target.items())
        value = {k: w * (1.0 + r.get(k, 0.0)) for k, w in target.items()}
        total = sum(value.values())
        drifted = {k: v / total for k, v in value.items()}
        rows.append({"signal_date": signal_date, "execution_date": week["execution_date"].iloc[0],
                     "next_execution_date": week["next_execution_date"].iloc[0], "n_names": len(week),
                     "gross_return": gross, "gtr": gtr, "one_way_turnover": gtr / 2})
    return pd.DataFrame(rows).set_index("signal_date"), pd.DataFrame(trades)


def net_returns(path: pd.DataFrame, one_way_cost: float) -> pd.Series:
    return (1.0 - one_way_cost * path["gtr"]) * (1.0 + path["gross_return"]) - 1.0
