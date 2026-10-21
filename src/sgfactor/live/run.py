"""Connect the execution engine to this project's data and target weights.

Mirrors the group's frozen final scenario (fangling's run_top4.py, FINAL_100K_DIV14_V1):
targets from the first evaluation signal onward, account starts from SGD 100,000 cash,
source cash dividends paid ex-date + 14 days, source split events not applied again
(prices are already split-adjusted).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..config import resolve
from .dividends import PERFORMANCE_SCOPE, prepare_source_dividends
from .engine import ExecutionConfig, plans_from_targets, simulate
from .metrics import execution_metrics
from .risk import risk_diagnostics


def load_execution_data(ecfg: dict) -> dict:
    d = ecfg["data"]
    prices = pd.read_csv(resolve(d["prices"]))
    prices["date"] = pd.to_datetime(prices["date"])
    prices = prices[prices["date"] >= ecfg["price_history_from"]].copy()
    sessions = pd.DatetimeIndex(pd.to_datetime(pd.read_csv(resolve(d["sessions"]))["date"]))
    sessions = sessions[sessions >= ecfg["price_history_from"]]
    master = pd.read_csv(resolve(d["security_master"]))
    actions = pd.read_csv(resolve(d["corporate_actions"]))
    return dict(prices=prices, sessions=sessions, master=master, actions=actions)


def execution_targets(target_weights: pd.DataFrame, calendar: pd.DataFrame, ecfg: dict,
                      sessions: pd.DatetimeIndex) -> pd.DataFrame:
    """Evaluation targets whose holding period ends by `end`, inside the daily data with room for T+2."""
    t = target_weights.merge(calendar[["signal_date", "next_execution_date"]], on="signal_date")
    for c in ("signal_date", "execution_date", "next_execution_date"):
        t[c] = pd.to_datetime(t[c])
    last_ok = min(pd.Timestamp(ecfg["end"]), sessions[-1 - ecfg["settings"]["settlement_sessions"]])
    keep = (t["signal_date"] >= ecfg["start"]) & (t["next_execution_date"] <= last_ok)
    return t[keep].reset_index(drop=True)


def run_execution(target_weights: pd.DataFrame, calendar: pd.DataFrame, ecfg: dict,
                  sti_levels: pd.Series | None = None) -> dict:
    data = load_execution_data(ecfg)
    t = execution_targets(target_weights, calendar, ecfg, data["sessions"])
    currency = data["master"].set_index("ticker")["currency"]
    if not currency.reindex(t["ticker"].unique()).eq("SGD").all():
        raise ValueError("Non-SGD or unknown traded currency; FX accounting required")
    ec = ExecutionConfig(**ecfg["settings"])
    end = pd.Timestamp(t["next_execution_date"].max())
    dividends = (prepare_source_dividends(data["actions"], t, data["sessions"], end)
                 if ecfg["dividends"]["enabled"] else None)
    if dividends is not None and ecfg["dividends"]["payment_delay_calendar_days"] != 14:
        raise ValueError("Frozen preset pays dividends ex-date + 14 days")
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
                           calendar_source=">=50 names reporting positive volume; proxy")
    metrics = execution_metrics(result)
    marks = data["prices"].pivot(index="date", columns="ticker", values="close").reindex(data["sessions"]).ffill()
    o = result["orders"]
    m = np.array([marks.at[d, k] for d, k in zip(o.signal_date, o.ticker)])
    requested, remaining = float((o.requested.abs() * m).sum()), float((o.remaining.abs() * m).sum())
    daily = result["daily"]
    summary = dict(release=ecfg["release"],
                   first_signal=str(t["signal_date"].min().date()), last_mark=str(end.date()),
                   initial_cash=ec.initial_cash, source_cash_events=0 if dividends is None else len(dividends),
                   dividend_income=float(daily.action_income.sum()),
                   requested_value_completion=1 - remaining / requested if requested else None, **metrics)
    nav = daily.set_index("date")["nav"]
    years = (nav.index[-1] - nav.index[0]).days / 365.25
    summary["daily_ann_vol"] = float(daily["net_return"].std(ddof=1) * np.sqrt(252))
    summary["daily_sharpe_rf0"] = float(daily["net_return"].mean() / daily["net_return"].std(ddof=1) * np.sqrt(252))
    if sti_levels is not None:
        s = sti_levels.reindex(nav.index, method="ffill")
        summary["sti_tr_same_dates_cagr"] = float((s.iloc[-1] / s.iloc[0]) ** (1 / years) - 1)
        summary["sti_tr_same_dates_max_drawdown"] = float(-(s / s.cummax() - 1).min())
    result.update(summary=summary, dividends=dividends, targets=t,
                  risk=risk_diagnostics(result, data["master"]))
    return result
