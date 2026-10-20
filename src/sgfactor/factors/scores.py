"""Style scores for each stock-week."""
from __future__ import annotations

import pandas as pd


def style_scores(universe: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Keys plus one column per style, named by the style (e.g. 'Low Risk')."""
    keys = ["signal_date", "execution_date", "next_execution_date", "ticker", "sector", "forward_return"]
    out = universe[keys].copy()
    for style, col in cfg["factors"].items():
        out[style] = universe[col].astype(float)
    return out
