"""Run the main strategy (SG Adaptive Top-4) on the historical data and write the results.

    python run_backtest.py                       # uses config/strategy.yaml
    python run_backtest.py --config my.yaml --out outputs/my_run

Steps: clean universe -> style long-short returns -> yearly style selection and weights
-> weekly composite score -> target holdings -> weekly NAV with costs -> metrics vs STI.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from sgfactor.backtest import net_returns, trade_stats, weekly_backtest          # noqa: E402
from sgfactor.backtest.report import period_mask, summary_table, yearly_table   # noqa: E402
from sgfactor.config import load_config, resolve                                # noqa: E402
from sgfactor.data import benchmark_weekly, load_benchmark, load_universe        # noqa: E402
from sgfactor.strategy import run_strategy                                      # noqa: E402


def backtest(cfg: dict, universe: pd.DataFrame | None = None, fret: pd.DataFrame | None = None) -> dict:
    """Full run for one configuration. Returns all intermediate tables."""
    universe = load_universe(cfg) if universe is None else universe
    res = run_strategy(universe, cfg, fret)
    path, ledger = weekly_backtest(res["holdings"], universe)
    cal = path.reset_index()[["signal_date", "execution_date", "next_execution_date"]]
    weekly = pd.DataFrame({
        "strategy": net_returns(path, cfg["costs"]["one_way"]),
        "strategy_stress_cost": net_returns(path, cfg["costs"]["stress_one_way"]),
        "strategy_gross": path["gross_return"],
        "STI": benchmark_weekly(load_benchmark(cfg), cal),
        "EW_universe": universe.groupby("signal_date")["forward_return"].mean().reindex(path.index),
    })
    weekly.insert(0, "next_execution_date", path["next_execution_date"])
    weekly["n_names"] = path["n_names"]
    weekly["one_way_turnover"] = path["one_way_turnover"]
    res.update(path=path, ledger=ledger, weekly=weekly, universe=universe)
    return res


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=None)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    t0 = time.time()
    cfg = load_config(a.config)
    out = resolve(a.out or f"{cfg['output_dir']}/{cfg['name']}")
    out.mkdir(parents=True, exist_ok=True)

    res = backtest(cfg)
    W = res["weekly"]
    series = ["strategy", "strategy_stress_cost", "STI", "EW_universe"]
    summary = summary_table(W, cfg, series)
    ev = period_mask(W.index, cfg["periods"]["eval"])
    trades = trade_stats(res["holdings"][res["holdings"]["signal_date"].isin(W.index[ev])],
                         res["universe"], cfg["costs"]["one_way"])

    res["factor_returns"].to_csv(out / "01_factor_returns_weekly.csv", index=False)
    res["decisions"].to_csv(out / "02_annual_style_decisions.csv", index=False)
    res["holdings"].to_csv(out / "03_target_holdings_weekly.csv", index=False)
    res["holdings"][["signal_date", "execution_date", "ticker", "weight"]].to_csv(
        out / "target_weights.csv", index=False)
    res["ledger"].to_csv(out / "04_trade_ledger.csv", index=False)
    W.to_csv(out / "05_weekly_returns.csv")
    summary.to_csv(out / "06_performance_summary.csv", index=False)
    yearly_table(W, series).to_csv(out / "07_calendar_year_returns.csv")
    with open(out / "run_manifest.json", "w") as f:
        json.dump({"config": cfg, "eval_trade_stats": trades, "weeks": len(W),
                   "first_signal": W.index[0], "last_signal": W.index[-1]}, f, indent=2)

    pd.set_option("display.width", 200)
    cols = ["period", "series", "weeks", "cum_return", "ann_return", "ann_vol", "sharpe", "max_drawdown", "calmar"]
    print(f"\n{cfg['name']}  ({len(W)} weeks {W.index[0]} .. {W.index[-1]}, "
          f"cost {cfg['costs']['one_way'] * 1e4:.0f} bp one-way)\n")
    print(summary[cols].round(4).to_string(index=False))
    print("\nStyles chosen each year:")
    print(res["decisions"][["year", "selected"]].to_string(index=False))
    print(f"\nEVAL trades: {trades}")
    print(f"\nOutputs in {out}  ({time.time() - t0:.0f} s)")


if __name__ == "__main__":
    main()
