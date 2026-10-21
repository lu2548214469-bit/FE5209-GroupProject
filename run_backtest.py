"""Run the main strategy (SG Adaptive Top-4) on the historical data and write the results.

    python run_backtest.py                       # strategy + daily execution account
    python run_backtest.py --skip-execution      # strategy and weekly backtest only (~15 s)
    python run_backtest.py --config my.yaml --out outputs/my_run

Part A  strategy + weekly backtest: clean universe -> style long-short returns -> yearly style
        selection and weights -> weekly composite score -> target weights -> weekly NAV with
        10 bp costs -> metrics vs STI, by period.
Part B  daily execution account (src/sgfactor/live, config/execution.yaml): the same target
        weights traded from SGD 100,000 cash in 2021 with board lots, minimum fees, volume
        limits, T+2 settlement and dividends. This is the headline "real-money" result.
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
from sgfactor.live import run_execution                                         # noqa: E402
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
    ap.add_argument("--execution-config", default=str(resolve("config/execution.yaml")))
    ap.add_argument("--skip-execution", action="store_true", help="skip the daily execution account")
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
    if not a.skip_execution:
        print("\nPart B: daily execution account (board lots, fees, volume caps, T+2, dividends) ...")
        ecfg = load_config(a.execution_config)
        cal = res["path"].reset_index()[["signal_date", "next_execution_date"]]
        ex = run_execution(res["holdings"][["signal_date", "execution_date", "ticker", "weight"]], cal, ecfg,
                           load_benchmark(cfg))
        d = out / "execution"
        d.mkdir(exist_ok=True)
        for key in ("daily", "holdings", "orders", "fills", "attempts", "signals", "events", "contributions",
                    "receipts_at_end", "unsettled_shares_at_end", "risk", "dividends"):
            if isinstance(ex.get(key), pd.DataFrame):
                ex[key].to_csv(d / f"{key}.csv", index=False)
        with open(d / "audit.json", "w") as f:
            json.dump(ex["audit"], f, indent=2, default=str)
        with open(out / "EXECUTION_SUMMARY.json", "w") as f:
            json.dump(ex["summary"], f, indent=2, default=str)
        s = ex["summary"]
        print(f"  {s['first_signal']} .. {s['last_mark']}: SGD {s['initial_cash']:,.0f} -> {s['ending_nav']:,.0f}  "
              f"CAGR {s['diagnostic_cagr_calendar']:.1%}, max drawdown {s['max_drawdown']:.1%}, "
              f"Sharpe (daily) {s['daily_sharpe_rf0']:.2f}")
        print(f"  dividends SGD {s['dividend_income']:,.0f}, fees SGD {s['total_fees']:,.0f}, "
              f"slippage SGD {s['proxy_slippage_cost']:,.0f}, order value completed {s['requested_value_completion']:.1%}")
        print(f"  STI total return, same dates: CAGR {s['sti_tr_same_dates_cagr']:.1%}, "
              f"max drawdown {s['sti_tr_same_dates_max_drawdown']:.1%}")
    print(f"\nOutputs in {out}  ({time.time() - t0:.0f} s)")


if __name__ == "__main__":
    main()
