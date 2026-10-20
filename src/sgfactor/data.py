"""Read the clean data package (data/)."""
from __future__ import annotations

import pandas as pd

from .config import resolve


def load_universe(cfg: dict) -> pd.DataFrame:
    """Weekly investable universe: one row per (signal_date, ticker) with six style scores
    and the forward return from execution_date close to next_execution_date close."""
    u = pd.read_csv(resolve(cfg["data"]["universe"]), dtype={"ticker": str})
    missing = set(cfg["factors"].values()) - set(u.columns)
    if missing:
        raise ValueError(f"score columns missing from the universe file: {missing}")
    return u


def load_benchmark(cfg: dict) -> pd.Series:
    """STI total-return index level by date."""
    b = pd.read_csv(resolve(cfg["data"]["benchmark"]))
    return pd.Series(b["sti_tr_level"].to_numpy(), index=pd.to_datetime(b["date"])).sort_index()


def benchmark_weekly(levels: pd.Series, calendar: pd.DataFrame) -> pd.Series:
    """STI return over each holding week, using the last close on or before each execution date."""
    def at(day: str) -> float:
        return float(levels.loc[:pd.Timestamp(day)].iloc[-1])
    return pd.Series({s: at(n) / at(e) - 1.0
                      for s, e, n in calendar[["signal_date", "execution_date", "next_execution_date"]]
                      .itertuples(index=False)}, name="STI")
