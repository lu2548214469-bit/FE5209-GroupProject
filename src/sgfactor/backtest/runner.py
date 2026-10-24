"""Reusable entry point for running the weekly strategy backtest."""

from __future__ import annotations

import pandas as pd

from sgfactor.backtest.engine import net_returns, weekly_backtest
from sgfactor.data import benchmark_weekly, load_benchmark, load_universe
from sgfactor.strategy import run_strategy


def backtest(
    cfg: dict,
    universe: pd.DataFrame | None = None,
    fret: pd.DataFrame | None = None,
) -> dict:
    """Run the strategy and weekly backtest, returning all intermediate tables."""
    universe = load_universe(cfg) if universe is None else universe
    result = run_strategy(universe, cfg, fret)
    path, ledger = weekly_backtest(result["holdings"], universe)
    calendar = path.reset_index()[
        ["signal_date", "execution_date", "next_execution_date"]
    ]
    weekly = pd.DataFrame(
        {
            "strategy": net_returns(path, cfg["costs"]["one_way"]),
            "strategy_stress_cost": net_returns(
                path, cfg["costs"]["stress_one_way"]
            ),
            "strategy_gross": path["gross_return"],
            "STI": benchmark_weekly(load_benchmark(cfg), calendar),
            "EW_universe": universe.groupby("signal_date")["forward_return"]
            .mean()
            .reindex(path.index),
        }
    )
    weekly.insert(0, "next_execution_date", path["next_execution_date"])
    weekly["n_names"] = path["n_names"]
    weekly["one_way_turnover"] = path["one_way_turnover"]
    result.update(path=path, ledger=ledger, weekly=weekly, universe=universe)
    return result
