"""Connect the execution engine to this project's data and target weights.

Mirrors the group's frozen final scenario (fangling's run_top4.py, FINAL_100K_DIV14_V1): the
account starts from SGD 100,000 cash at the first evaluation signal, source cash dividends are paid
ex-date + 14 days, source split events are not applied again (prices are already split-adjusted).

Extensions in this project:
  - non-SGD listings (USD / EUR quoted names such as T14, DCRU): closes and dividends are converted
    to SGD with the daily FX in data/fx_daily.csv, so the account is kept in SGD;
  - one continuous account through the evaluation period and the live window. Evaluation targets are
    traded on their weekly execution dates; live targets on the live trade dates (first live trade
    2026-10-01). Results are reported separately for EVAL (to periods.eval end of holdings) and LIVE.
  - two calendar-only sessions after the last price day so that T+2 settlement of trades in the last
    days can be booked (no prices on those days; the account is marked at `end`).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..config import resolve
from .dividends import PERFORMANCE_SCOPE, prepare_source_dividends
from .engine import ExecutionConfig, plans_from_targets, simulate
from .metrics import drawdown, execution_metrics
from .risk import risk_diagnostics


def load_execution_data(ecfg: dict) -> dict:
    d = ecfg["data"]
    master = pd.read_csv(resolve(d["security_master"]))
    fx = pd.read_csv(resolve(d["fx"]), parse_dates=["date"]).set_index("date").sort_index()
    prices = pd.read_csv(resolve(d["prices"]), usecols=["date", "ticker", "close", "volume"])
    prices["date"] = pd.to_datetime(prices["date"])
    prices = prices[prices["date"] >= ecfg["price_history_from"]].copy()
    ccy = prices["ticker"].map(master.set_index("ticker")["currency"])
    rate = pd.Series(1.0, index=prices.index)
    for code, col in (("USD", "sgd_per_usd"), ("EUR", "sgd_per_eur")):
        m = ccy.eq(code)
        rate[m] = fx[col].reindex(prices.loc[m, "date"]).ffill().to_numpy()
    prices["close"] = prices["close"] * rate                       # SGD
    sessions = pd.DatetimeIndex(pd.to_datetime(pd.read_csv(resolve(d["sessions"]))["date"]))
    sessions = sessions[sessions >= ecfg["price_history_from"]]
    sessions = sessions.union(pd.DatetimeIndex(pd.to_datetime(ecfg["settlement_calendar_extension"])))
    actions = pd.read_csv(resolve(d["corporate_actions"]))
    a_ccy = actions["ticker"].map(master.set_index("ticker")["currency"])
    for code, col in (("USD", "sgd_per_usd"), ("EUR", "sgd_per_eur")):
        m = a_ccy.eq(code)
        actions.loc[m, "dividend"] = actions.loc[m, "dividend"].to_numpy() * \
            fx[col].reindex(pd.to_datetime(actions.loc[m, "date"])).ffill().to_numpy()
    return dict(prices=prices, sessions=sessions, master=master, actions=actions)


def run_execution(targets: pd.DataFrame, ecfg: dict, eval_end: str, live_start: str,
                  sti_levels: pd.Series | None = None) -> dict:
    """targets: signal_date, execution_date, ticker, weight (complete snapshot per signal)."""
    data = load_execution_data(ecfg)
    t = targets.copy()
    for c in ("signal_date", "execution_date"):
        t[c] = pd.to_datetime(t[c])
    t = t[t["signal_date"] >= ecfg["start"]].reset_index(drop=True)
    ec = ExecutionConfig(**ecfg["settings"])
    end = pd.Timestamp(ecfg["end"])
    dividends = (prepare_source_dividends(data["actions"], t, data["sessions"], end)
                 if ecfg["dividends"]["enabled"] else None)
    result = simulate(data["prices"], data["sessions"], plans_from_targets(t), ec,
                      actions=dividends, actions_verified=False, end=end)

    # the same post-run checks as the frozen final entry point
    f = result["fills"]
    if not f.empty:
        assert (f.shares.abs() <= ec.participation * f.source_volume + 1e-6).all()
        assert (f.shares.abs() * f.reference_close <= ec.participation * f.lagged_adv + 1e-5).all()
        assert ((f.shares.abs() % f.lot_size) == 0).all()
        assert (f.date > f.order_id.map(result["orders"].set_index("order_id").signal_date)).all()
    assert result["daily"].cash.ge(-1e-7).all()

    result["audit"].update(performance_scope=PERFORMANCE_SCOPE, framework_release=ecfg["release"],
                           corporate_action_and_price_basis_verified=False,
                           actual_dividend_payment_dates_verified=False,
                           non_sgd_listings="converted to SGD with data/fx_daily.csv",
                           calendar_source=">=50 names reporting positive volume; proxy")
    metrics = execution_metrics(result)
    nav = result["daily"].set_index("date")["nav"]

    def window(a, b, base):
        n = nav[(nav.index > a) & (nav.index <= b)]
        n0 = base if base is not None else float(nav.loc[:a].iloc[-1])
        r = pd.concat([pd.Series([n0]), n.reset_index(drop=True)]).pct_change().dropna()
        out = dict(start=str(pd.Timestamp(a).date()) if base is None else str(nav.index[0].date()),
                   end=str(n.index[-1].date()), start_nav=n0, end_nav=float(n.iloc[-1]),
                   cum_return=float(n.iloc[-1] / n0 - 1), max_drawdown=drawdown(n, n0))
        yrs = (n.index[-1] - pd.Timestamp(a)).days / 365.25
        if yrs > 1:
            out.update(cagr=float((n.iloc[-1] / n0) ** (1 / yrs) - 1),
                       daily_ann_vol=float(r.std() * np.sqrt(252)),
                       daily_sharpe_rf0=float(r.mean() / r.std() * np.sqrt(252)))
        if sti_levels is not None:
            s = sti_levels.reindex(n.index.union([pd.Timestamp(a)]), method="ffill")
            out["sti_cum_return"] = float(s.iloc[-1] / s.iloc[0] - 1)
            if yrs > 1:
                out["sti_cagr"] = float((s.iloc[-1] / s.iloc[0]) ** (1 / yrs) - 1)
                out["sti_max_drawdown"] = float(-(s / s.cummax() - 1).min())
        return out

    first = nav.index[0]
    ev = window(first - pd.Timedelta(days=1), pd.Timestamp(eval_end), ec.initial_cash)
    lv = window(pd.Timestamp(live_start), end, None)
    o = result["orders"]
    marks = data["prices"].pivot(index="date", columns="ticker", values="close").reindex(data["sessions"]).ffill()
    m = np.array([marks.at[d, k] for d, k in zip(o.signal_date, o.ticker)])
    requested, remaining = float((o.requested.abs() * m).sum()), float((o.remaining.abs() * m).sum())
    summary = dict(release=ecfg["release"], initial_cash=ec.initial_cash,
                   first_signal=str(t["signal_date"].min().date()), last_mark=str(end.date()),
                   EVAL=ev, LIVE=lv,
                   source_cash_events=0 if dividends is None else len(dividends),
                   dividend_income=float(result["daily"].action_income.sum()),
                   requested_value_completion=1 - remaining / requested if requested else None, **metrics)
    result.update(summary=summary, dividends=dividends, targets=t, risk=risk_diagnostics(result, data["master"]))
    return result
