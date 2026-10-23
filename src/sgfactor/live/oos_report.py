"""Calendar-inclusive OOS reporting on the unchanged execution account.

The first test day's return uses the previous session's close. Legacy reports
that start at the first test day's close remain reproducible separately.
"""
from __future__ import annotations

import json
from pathlib import Path
import numpy as np
import pandas as pd
from .report import course_metrics, position_trades


def load_account(folder: str | Path) -> dict:
    folder = Path(folder)
    result = {}
    for name in ("daily", "holdings", "fills", "orders", "signals", "contributions", "events"):
        try:
            frame = pd.read_csv(folder / f"{name}.csv")
        except pd.errors.EmptyDataError:
            frame = pd.DataFrame()
        for col in ("date", "signal_date", "execution_date", "activation", "settlement_date"):
            if col in frame:
                frame[col] = pd.to_datetime(frame[col])
        result[name] = frame
    result["audit"] = json.loads((folder / "audit.json").read_text(encoding="utf-8"))
    return result


def report_window(ex: dict, start: str, end: str, benchmark: pd.Series) -> dict:
    """Report [start, end] session returns without inventing the last mark.

    Win rate follows the group's existing window-marked position episodes,
    including open positions. It is not a closed-round-trip win rate.
    """
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    daily = ex["daily"].copy().set_index("date").sort_index()
    daily.index = pd.to_datetime(daily.index)
    if start > end:
        raise ValueError("Test start is after test end")
    if start not in daily.index or end not in daily.index:
        raise ValueError(f"Requested first/last test session missing: {start.date()} .. {end.date()}")
    previous = daily.index[daily.index < start]
    if previous.empty:
        raise ValueError("A previous-session close is required for a continuous test account")
    base_date = previous[-1]
    days = daily.index[(daily.index >= start) & (daily.index <= end)]
    benchmark = benchmark.copy()
    benchmark.index = pd.to_datetime(benchmark.index)
    required = pd.DatetimeIndex([base_date]).append(days)
    if benchmark.index.has_duplicates:
        raise ValueError("Duplicate benchmark dates")
    missing = required.difference(benchmark.dropna().index)
    if len(missing):
        raise ValueError("Missing exact benchmark sessions: " + ", ".join(missing.strftime("%Y-%m-%d")))
    if not np.isfinite(benchmark.reindex(required)).all() or (benchmark.reindex(required) <= 0).any():
        raise ValueError("Invalid benchmark levels")
    metrics = course_metrics(ex, str(base_date.date()), str(end.date()), benchmark)
    metrics.update(test_first_session=str(start.date()), test_last_session=str(end.date()),
                   base_close_date=str(base_date.date()), interval_convention="[first session, last session] returns",
                   annualisation_warning="252-session scaling of a short sample, not a long-run forecast",
                   position_trade_definition="Window-marked holding episodes including open positions, not closed round trips")
    previous_nav = daily.nav.shift(1)
    c = ex["contributions"].copy()
    c["date"] = pd.to_datetime(c["date"])
    c = c[c.date.isin(days)]
    pnl = c.groupby("date").contribution_amount.sum().reindex(days, fill_value=0.)
    expected = daily.nav.diff().reindex(days)
    accounting_error = float((pnl - expected).abs().max())
    if accounting_error > 1e-6:
        raise ValueError(f"Daily stock contributions do not reconcile: {accounting_error}")
    pt = position_trades(ex, base_date, end)
    if abs(float(pt.pnl_sgd.sum()) - metrics["pnl_sgd"]) > 1e-6:
        raise ValueError("Window position P&L does not reconcile to the account")

    # Exact active-wealth bridge, with the same beginning exposures as the
    # already delivered attribution. Cash includes unsettled receivables.
    held = ex["holdings"][["date", "ticker", "weight"]].copy()
    held["date"] = pd.to_datetime(held["date"])
    held["date"] = held.date.map(dict(zip(daily.index[:-1], daily.index[1:])))
    held = held.rename(columns={"weight": "begin_weight"}).dropna(subset=["date"])
    detail = c.merge(held, on=["date", "ticker"], how="outer", validate="one_to_one")
    detail = detail[detail.date.isin(days)].copy()
    detail["begin_weight"] = detail.begin_weight.fillna(0.)
    detail["contribution_amount"] = detail.contribution_amount.fillna(0.)
    levels = benchmark.reindex(required)
    market_return = levels.pct_change().iloc[1:]
    base_nav = float(daily.nav.at[base_date])
    linking = previous_nav.reindex(days) / base_nav * (levels.iloc[-1] / levels.iloc[1:])
    detail["active_daily_effect"] = detail.contribution_amount / detail.date.map(previous_nav) - detail.begin_weight * detail.date.map(market_return)
    detail["active_contribution_pp"] = detail.active_daily_effect * detail.date.map(linking) * 100
    stocks = detail.groupby("ticker", as_index=False).agg(net_pnl=("contribution_amount", "sum"), active_contribution_pp=("active_contribution_pp", "sum"))
    stocks["absolute_contribution_pp"] = stocks.net_pnl / base_nav * 100
    noninvested = (1 - daily.market_value.shift(1) / previous_nav).reindex(days)
    cash_pp = float((-noninvested * market_return * linking).sum() * 100)
    active_error = float(stocks.active_contribution_pp.sum() + cash_pp - metrics["excess_return_vs_STI"] * 100)
    if abs(active_error) > 1e-7:
        raise ValueError(f"Active attribution does not reconcile: {active_error} pp")
    component_columns = [k for k in ("price_pnl", "action_income", "fees", "slippage_cost") if k in c]
    components = {k: float(c[k].sum()) for k in component_columns}
    metrics.update(daily_accounting_error_max=accounting_error,
                   active_reconciliation_error_pp=active_error,
                   cash_and_receivables_active_pp=cash_pp,
                   stock_active_pp=float(stocks.active_contribution_pp.sum()))
    path = daily.loc[required, ["nav"]].copy()
    path["strategy_rebased"] = path.nav / base_nav
    path["sti_rebased"] = levels / levels.iloc[0]
    return dict(metrics=metrics, daily_nav=path, stocks=stocks.sort_values("active_contribution_pp", ascending=False),
                position_trades=pt, components=components)


def save_report(result: dict, out: str | Path) -> None:
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    metrics = {k: (None if isinstance(v, (float, np.floating)) and not np.isfinite(v) else v)
               for k, v in result["metrics"].items()}
    (out / "OOS_METRICS.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    pd.Series(result["metrics"], name="value").rename_axis("metric").to_csv(out / "oos_metrics.csv")
    result["daily_nav"].to_csv(out / "oos_daily_nav.csv", index_label="date")
    result["stocks"].to_csv(out / "oos_stock_attribution.csv", index=False)
    result["position_trades"].to_csv(out / "oos_position_episodes.csv", index=False)
    (out / "oos_components.json").write_text(json.dumps(result["components"], indent=2), encoding="utf-8")
