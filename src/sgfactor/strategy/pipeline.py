"""One full strategy run: yearly style decisions -> weekly composite scores -> target holdings.

Styles are selected once a year (first signal week). Style weights are set at the same time by
default (weighting.rebalance = "yearly"); "monthly" or "weekly" re-estimates the weights of the
same selected styles at the first signal week of each month, or every week, using only factor
returns completed by that date.
"""
from __future__ import annotations

import pandas as pd

from ..factors import factor_returns, style_scores
from .portfolio import build_holdings
from .scoring import composite_scores
from .selection import select_styles
from .weighting import style_weights


def run_strategy(universe: pd.DataFrame, cfg: dict, fret: pd.DataFrame | None = None) -> dict:
    styles = list(cfg["factors"])
    scores = style_scores(universe, cfg)
    if fret is None:
        fret = factor_returns(scores, styles, cfg["factor_returns"]["leg_fraction"])
    sel_cfg, w_cfg, p_cfg = cfg["selection"], cfg["weighting"], cfg["portfolio"]

    live = scores[scores["signal_date"] >= cfg["periods"]["backtest_start"]]
    dates = pd.to_datetime(pd.Series(sorted(live["signal_date"].unique())))
    decisions, parts = [], []
    for year, first_week in dates.groupby(dates.dt.year).min().items():
        cutoff = first_week.strftime("%Y-%m-%d")
        chosen, stats = select_styles(fret, cutoff, styles, sel_cfg["top_k"], sel_cfg["lookback_years"],
                                      sel_cfg["min_coverage"])
        weights = style_weights(fret, cutoff, chosen, styles, w_cfg["method"], w_cfg["window_weeks"],
                                w_cfg["min_weight"], w_cfg["max_weight"], w_cfg["mv_shrinkage"])
        decisions.append({"year": int(year), "decision_date": cutoff, "selected": ", ".join(chosen),
                          **{f"weight_{s}": round(weights.get(s, 0.0), 4) for s in styles},
                          **{f"mean_over_std_{r.style}": r.score for r in stats.itertuples()}})
        year_rows = live[pd.to_datetime(live["signal_date"]).dt.year == year]
        freq = w_cfg.get("rebalance", "yearly")
        if freq == "yearly":
            parts.append(composite_scores(year_rows, weights))
            continue
        yd = pd.to_datetime(year_rows["signal_date"])
        key = yd.dt.month if freq == "monthly" else yd
        for _, block in year_rows.groupby(key.to_numpy(), sort=True):
            start = block["signal_date"].min()
            w = weights if start == cutoff else style_weights(
                fret, start, chosen, styles, w_cfg["method"], w_cfg["window_weeks"],
                w_cfg["min_weight"], w_cfg["max_weight"], w_cfg["mv_shrinkage"])
            parts.append(composite_scores(block, w))
    composite = pd.concat(parts, ignore_index=True)
    holdings = build_holdings(composite, p_cfg["select_fraction"], p_cfg["exit_fraction"], p_cfg["sector_cap"])
    return {"factor_returns": fret, "decisions": pd.DataFrame(decisions), "composite": composite,
            "holdings": holdings}
