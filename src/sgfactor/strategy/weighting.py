"""Weights of the selected styles (set once a year with the selection).

Covariance: last `window_weeks` weeks in which every candidate style has a completed return.
  EW  equal weight
  IV  inverse volatility, projected onto the bounds [min_weight, max_weight] (sum = 1)
  MV  minimum variance with `mv_shrinkage` of the off-diagonal shrunk to zero, same bounds
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import minimize


def _bounded(objective, n: int, lo: float, hi: float) -> np.ndarray:
    if not n * lo <= 1 <= n * hi:
        raise ValueError("infeasible weight bounds")
    res = minimize(objective, x0=np.ones(n) / n, method="SLSQP", bounds=[(lo, hi)] * n,
                   constraints=[{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}],
                   options={"ftol": 1e-12, "maxiter": 1000})
    if not res.success:
        raise RuntimeError(res.message)
    return res.x


def style_covariance(fret: pd.DataFrame, cutoff: str, styles: list[str], window: int) -> np.ndarray:
    done = fret[pd.to_datetime(fret["next_execution_date"]) <= pd.Timestamp(cutoff)]
    wide = done.pivot(index="signal_date", columns="style", values="factor_return").reindex(columns=styles)
    wide = wide.dropna().tail(window)
    if len(wide) != window:
        raise ValueError(f"not enough common history for the covariance at {cutoff}")
    return wide.cov().to_numpy(dtype=float)


def style_weights(fret: pd.DataFrame, cutoff: str, selected: list[str], all_styles: list[str],
                  method: str = "IV", window_weeks: int = 52, min_weight: float = 0.05,
                  max_weight: float = 0.80, mv_shrinkage: float = 0.10) -> dict[str, float]:
    n = len(selected)
    if n == 1:
        return {selected[0]: 1.0}
    if method == "EW":
        return {s: 1.0 / n for s in selected}
    cov_all = style_covariance(fret, cutoff, all_styles, window_weeks)
    idx = [all_styles.index(s) for s in selected]
    cov = cov_all[np.ix_(idx, idx)]
    if method == "IV":
        target = 1.0 / np.sqrt(np.diag(cov))
        target = target / target.sum()
        w = _bounded(lambda w: float(np.sum((w - target) ** 2)), n, min_weight, max_weight)
    elif method == "MV":
        shrunk = (1 - mv_shrinkage) * cov + mv_shrinkage * np.diag(np.diag(cov))
        scale = max(float(np.trace(shrunk)), 1e-12)
        w = _bounded(lambda w: float(w @ shrunk @ w / scale), n, min_weight, max_weight)
    else:
        raise ValueError(f"unknown weighting method {method}")
    return dict(zip(selected, map(float, w)))
