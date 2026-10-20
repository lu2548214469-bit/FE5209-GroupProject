"""Composite score = weighted sum of the selected style scores."""
from __future__ import annotations

import pandas as pd


def composite_scores(scores: pd.DataFrame, weights: dict[str, float]) -> pd.DataFrame:
    out = scores[["signal_date", "execution_date", "ticker", "sector"]].copy()
    out["composite_score"] = sum(scores[s] * w for s, w in weights.items())
    return out
