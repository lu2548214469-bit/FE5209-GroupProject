"""Strategy tests: controlled-variable comparison + integrity checks.

    python tests/strategy_tests/run_strategy_tests.py

Part 1  Comparison table. Start from the baseline (teammate spec: Top-3, 3-year lookback, IV,
        top 20%, buffer 20/30, 30% sector cap, 10 bp) and change ONE setting at a time.
        Selection rule, fixed in advance: a variant is preferred only if it beats the baseline
        on BOTH Sharpe and Calmar in the observation period (2019-20). The evaluation period
        (2021-01 .. 2026-09) is reported for every row but never used to choose.
        The live column is the live window (first trade 2026-10-01, daily NAV to 2026-10-15).
Part 2  Integrity checks on the frozen strategy (config/strategy.yaml): weights, sector cap,
        no look-ahead in the yearly style decisions, and reproduction of the frozen numbers.

Outputs: outputs/strategy_tests/comparison_table.csv, checks.csv
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from run_backtest import backtest                                   # noqa: E402
from sgfactor.backtest.live_window import daily_nav, live_schedule, load_daily_adjusted  # noqa: E402
from sgfactor.backtest.metrics import performance                  # noqa: E402
from sgfactor.backtest.report import period_mask                   # noqa: E402
from sgfactor.config import load_config, override                   # noqa: E402
from sgfactor.data import load_universe                            # noqa: E402
from sgfactor.factors import factor_returns, style_scores           # noqa: E402
from sgfactor.strategy import select_styles                         # noqa: E402

BASELINE = {"selection.top_k": 3}
VARIANTS = [   # (dimension, label, config changes on top of the baseline, data change)
    ("baseline", "Top-3, 3y, IV, top20%, buffer, cap30%", {}, None),
    ("K", "Top-1", {"selection.top_k": 1}, None),
    ("K", "Top-2", {"selection.top_k": 2}, None),
    ("K", "Top-4  [frozen]", {"selection.top_k": 4}, None),
    ("K", "Top-5", {"selection.top_k": 5}, None),
    ("K", "All 6 (no selection)", {"selection.top_k": 6}, None),
    ("lookback", "5-year lookback", {"selection.lookback_years": 5}, None),
    ("style weights", "EW", {"weighting.method": "EW"}, None),
    ("style weights", "MV", {"weighting.method": "MV"}, None),
    ("names held", "top 25% (exit 35%)", {"portfolio.select_fraction": 0.25, "portfolio.exit_fraction": 0.35}, None),
    ("names held", "top 30% (exit 40%)", {"portfolio.select_fraction": 0.30, "portfolio.exit_fraction": 0.40}, None),
    ("buffer", "no buffer (exit = entry)", {"portfolio.exit_fraction": 0.20}, None),
    ("sector cap", "no sector cap", {"portfolio.sector_cap": 1.0}, None),
    ("Size direction", "Size = large cap", {}, "size_large"),
]
REFERENCE = {   # frozen Top-4 on data/ (final FX-complete panel), EVAL 2021-01 .. signal 2026-09-18, 10 bp
    "ann_return": 0.2502, "sharpe": 1.5677, "max_drawdown": 0.1160, "calmar": 2.1572}
ADJ = None


def live_return(res: dict, cfg: dict) -> float:
    """Live window (first trade 2026-10-01), daily NAV, same rules as run_backtest.py."""
    global ADJ
    ADJ = load_daily_adjusted(cfg) if ADJ is None else ADJ
    h = res["holdings"]
    sched = live_schedule(res["universe"]["signal_date"].unique(), cfg)
    tg = {s: h[h.signal_date == s].set_index("ticker")["weight"] for s, _ in sched}
    return float(daily_nav(tg, sched, ADJ, cfg["live_window"]["end"], cfg["costs"]["one_way"]).iloc[-1] - 1)


def metrics_row(W: pd.DataFrame, cfg: dict, live: float | None = None) -> dict:
    row = {}
    for per in ("pre", "obs", "eval"):
        m = period_mask(W.index, cfg["periods"][per])
        p = performance(W.loc[m, "strategy"], W.loc[m, "STI"])
        row.update({f"{per}_{k}": p[k] for k in ("ann_return", "sharpe", "max_drawdown", "calmar")})
    m = period_mask(W.index, cfg["periods"]["eval"])
    row["eval_beta"] = performance(W.loc[m, "strategy"], W.loc[m, "STI"])["beta"]
    row["eval_ann_turnover"] = float(W.loc[m, "one_way_turnover"].mean() * 52)
    row["avg_names"] = float(W["n_names"].mean())
    row["live_cum_return"] = live
    return row


def comparison(cfg0: dict, universe: pd.DataFrame) -> pd.DataFrame:
    styles = list(cfg0["factors"])
    fret = factor_returns(style_scores(universe, cfg0), styles, cfg0["factor_returns"]["leg_fraction"])
    flipped = universe.assign(size_score=-universe["size_score"])
    rows, base_weekly = [], None
    for dim, label, changes, data in VARIANTS:
        cfg = override(cfg0, **{**BASELINE, **changes})
        uni, fr = (flipped, None) if data == "size_large" else (universe, fret)
        res = backtest(cfg, uni, fr)
        W = res["weekly"]
        base_weekly = W if base_weekly is None else base_weekly
        rows.append({"dimension": dim, "variant": label, **metrics_row(W, cfg, live_return(res, cfg))})
        print(f"  {label:<38} OBS Sharpe {rows[-1]['obs_sharpe']:.2f}  EVAL Sharpe {rows[-1]['eval_sharpe']:.2f}")
    T = pd.DataFrame(rows)
    b = T.iloc[0]
    better = (T["obs_sharpe"] > b["obs_sharpe"]) & (T["obs_calmar"] > b["obs_calmar"])
    T["beats_baseline_in_OBS"] = np.where(better, "yes", "no")
    T.loc[0, "beats_baseline_in_OBS"] = "-"
    sched = live_schedule(universe["signal_date"].unique(), cfg0)
    sti = pd.read_csv(ROOT / cfg0["data"]["benchmark"], parse_dates=["date"]).set_index("date")["sti_tr_level"]
    ew = {s: (g := universe[universe.signal_date == s].set_index("ticker")).assign(w=1 / len(g))["w"] for s, _ in sched}
    live_bench = {"STI": float(sti.loc[cfg0["live_window"]["end"]] / sti.loc[sched[0][1]] - 1),
                  "EW_universe": float(daily_nav(ew, sched, ADJ, cfg0["live_window"]["end"], 0.0).iloc[-1] - 1)}
    for per, name in (("STI", "STI"), ("EW_universe", "EW universe (gross)")):
        W = base_weekly.assign(strategy=base_weekly[per])
        r = {"dimension": "benchmark", "variant": name, **metrics_row(W, cfg0, live_bench[per])}
        r.pop("eval_ann_turnover"); r.pop("avg_names")
        T = pd.concat([T, pd.DataFrame([r])], ignore_index=True)
    return T


def checks(cfg: dict, universe: pd.DataFrame) -> pd.DataFrame:
    res = backtest(cfg, universe)
    H, D, F, W = res["holdings"], res["decisions"], res["factor_returns"], res["weekly"]
    out = []

    def check(name, ok, detail=""):
        out.append({"check": name, "result": "PASS" if ok else "FAIL", "detail": detail})

    w = H.groupby("signal_date")["weight"].sum()
    check("weights are positive and sum to <= 1 each week", (H["weight"] > 0).all() and (w <= 1 + 1e-12).all(),
          f"min weekly invested {w.min():.3f}")
    check("no duplicate holdings", not H.duplicated(["signal_date", "ticker"]).any())
    n = H.groupby("signal_date").size()
    caps = H.groupby(["signal_date", "sector"]).size().groupby("signal_date").max()
    n_target = (universe.groupby("signal_date").size().reindex(n.index) * cfg["portfolio"]["select_fraction"]).apply(math.floor)
    check("sector cap respected", (caps <= (n_target * cfg["portfolio"]["sector_cap"]).apply(math.floor)).all())
    check("holdings are inside the universe",
          H.merge(universe[["signal_date", "ticker"]], how="left", indicator=True)["_merge"].eq("both").all())
    styles, sc = list(cfg["factors"]), cfg["selection"]
    same = []
    for d, chosen in zip(D["decision_date"], D["selected"]):
        past = F[pd.to_datetime(F["next_execution_date"]) <= pd.Timestamp(d)]   # delete everything later
        again, _ = select_styles(past, d, styles, sc["top_k"], sc["lookback_years"], sc["min_coverage"])
        same.append(", ".join(again) == chosen)
    check("no look-ahead: yearly decisions unchanged when all later data is deleted", all(same),
          f"{sum(same)}/{len(same)} years identical")
    m = period_mask(W.index, cfg["periods"]["eval"])
    p = performance(W.loc[m, "strategy"])
    diffs = {k: abs(p[k] - v) for k, v in REFERENCE.items()}
    check("reproduces the frozen Top-4 EVAL numbers", max(diffs.values()) < 0.0005,
          ", ".join(f"{k} {p[k]:.4f}" for k in REFERENCE))
    return pd.DataFrame(out)


def main() -> None:
    cfg = load_config()
    universe = load_universe(cfg)
    out = ROOT / cfg["output_dir"] / "strategy_tests"
    out.mkdir(parents=True, exist_ok=True)
    print("Part 1: controlled-variable comparison (baseline = Top-3)")
    T = comparison(cfg, universe)
    T.to_csv(out / "comparison_table.csv", index=False)
    print("\nPart 2: integrity checks on the frozen strategy")
    C = checks(cfg, universe)
    C.to_csv(out / "checks.csv", index=False)
    pd.set_option("display.width", 250)
    cols = ["dimension", "variant", "avg_names", "pre_sharpe", "obs_sharpe", "obs_calmar", "beats_baseline_in_OBS",
            "eval_ann_return", "eval_sharpe", "eval_max_drawdown", "eval_calmar", "live_cum_return"]
    print("\n" + T[cols].round(3).to_string(index=False))
    print("\n" + C.to_string(index=False))
    print(f"\nOutputs in {out}")
    if (C["result"] == "FAIL").any():
        sys.exit(1)


if __name__ == "__main__":
    main()
