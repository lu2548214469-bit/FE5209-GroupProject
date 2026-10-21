"""Strategy tests: controlled-variable comparison + integrity checks.

    python tests/strategy_tests/run_strategy_tests.py

Part 1  Full grid, no baseline: every combination of
          K (styles selected each year) 2..6  x  lookback 3 / 5 years  x  style weights EW / IV / MV
          x  share held top 20 / 25 / 30 %          = 90 configurations,
        all with the same buffer (+10 pp), 30% sector cap, small-cap Size and 10 bp costs.
        Selection data: 2016-20 only (2016-18 and 2019-20 also shown separately). The evaluation
        period (2021-01 .. 2026-09) and the live window are reported for every row, never used to choose.
        Printed as matrices (one block per K) so each setting can be compared with all others fixed.
        The live column is the live window (first trade 2026-10-01, daily NAV to 2026-10-15).
Part 2  Integrity checks on the frozen strategy (config/strategy.yaml): weights, sector cap,
        no look-ahead in the yearly style decisions, and reproduction of the frozen numbers.

Outputs: outputs/strategy_tests/comparison_table.csv, checks.csv
"""
from __future__ import annotations

import itertools
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

GRID = {   # every combination is run; nothing is a baseline
    "K": [2, 3, 4, 5, 6],                 # styles selected each year (6 = all styles, so lookback has no effect)
    "lookback": [3, 5],                    # years of factor returns used to rank the styles
    "weights": ["EW", "IV", "MV"],         # how the selected styles are weighted
    "top": [0.20, 0.25, 0.30],             # share of the universe held (buffer exit = top + 10 pp)
}
PERIODS = {"pre": ("2016-01-01", "2018-12-31"), "obs": ("2019-01-01", "2020-12-31"),
           "insample": ("2016-01-01", "2020-12-31"), "eval": ("2021-01-01", "2026-09-18")}
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


def run_grid(cfg0: dict, universe: pd.DataFrame) -> pd.DataFrame:
    styles = list(cfg0["factors"])
    fret = factor_returns(style_scores(universe, cfg0), styles, cfg0["factor_returns"]["leg_fraction"])
    rows = []
    combos = list(itertools.product(*GRID.values()))
    for i, (k, lb, wm, top) in enumerate(combos, 1):
        cfg = override(cfg0, **{"selection.top_k": k, "selection.lookback_years": lb, "weighting.method": wm,
                                "portfolio.select_fraction": top, "portfolio.exit_fraction": round(top + 0.10, 2)})
        res = backtest(cfg, universe, fret)
        W = res["weekly"]
        row = {"K": k, "lookback": lb, "weights": wm, "top_pct": int(round(top * 100)),
               "avg_names": round(float(W["n_names"].mean()), 1)}
        for per, (a, b) in PERIODS.items():
            m = (W.index >= a) & (W.index <= b)
            p = performance(W.loc[m, "strategy"])
            row.update({f"{per}_{x}": p[x] for x in ("ann_return", "sharpe", "max_drawdown", "calmar")})
        row["live_cum_return"] = live_return(res, cfg)
        rows.append(row)
        print(f"  [{i:>2}/{len(combos)}] K={k} {lb}y {wm} top{row['top_pct']}%   "
              f"2016-20 Sharpe {row['insample_sharpe']:.2f}  EVAL Sharpe {row['eval_sharpe']:.2f}", flush=True)
    return pd.DataFrame(rows)


def matrices(G: pd.DataFrame, metric: str, pct: bool) -> str:
    """One block per K: rows = lookback x weights, columns = share held."""
    out = []
    for k, g in G.groupby("K"):
        t = g.assign(row=g["lookback"].astype(str) + "y " + g["weights"]).pivot(
            index="row", columns="top_pct", values=metric)
        t = (t * 100).round(1) if pct else t.round(2)
        t.columns = [f"top{c}%" for c in t.columns]
        t.index.name = f"K={k}"
        out.append(t.to_string())
    return "\n\n".join(out)


def ranking(G: pd.DataFrame) -> pd.DataFrame:
    G = G.copy()
    G["worst_of_pre_obs_sharpe"] = G[["pre_sharpe", "obs_sharpe"]].min(axis=1)
    cols = ["K", "lookback", "weights", "top_pct", "insample_ann_return", "insample_sharpe", "insample_max_drawdown",
            "insample_calmar", "worst_of_pre_obs_sharpe", "eval_ann_return", "eval_sharpe", "eval_max_drawdown",
            "eval_calmar", "live_cum_return"]
    return G.sort_values("insample_sharpe", ascending=False)[cols].reset_index(drop=True)


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
    n = 1
    for v in GRID.values():
        n *= len(v)
    print(f"Part 1: full grid, {n} configurations (about 4 seconds each)")
    G = run_grid(cfg, universe)
    G.to_csv(out / "grid_all_configurations.csv", index=False)
    R = ranking(G)
    R.to_csv(out / "grid_ranked_by_2016_20_sharpe.csv", index=False)

    pd.set_option("display.width", 250)
    pd.set_option("display.max_rows", 200)
    blocks = [("2016-20 Sharpe (selection data)", "insample_sharpe", False),
              ("2016-20 Calmar (selection data)", "insample_calmar", False),
              ("2016-20 annual return %", "insample_ann_return", True),
              ("2016-20 max drawdown %", "insample_max_drawdown", True),
              ("2016-18 Sharpe", "pre_sharpe", False),
              ("2019-20 Sharpe", "obs_sharpe", False),
              ("EVAL 2021-01..2026-09 annual return %", "eval_ann_return", True),
              ("EVAL Sharpe", "eval_sharpe", False),
              ("EVAL max drawdown %", "eval_max_drawdown", True),
              ("EVAL Calmar", "eval_calmar", False),
              ("LIVE 2026-10-01..10-15 return %", "live_cum_return", True)]
    with open(out / "grid_matrices.txt", "w", encoding="utf-8") as f:
        for title, metric, pct in blocks:
            text = f"\n===== {title} =====\n\n{matrices(G, metric, pct)}\n"
            print(text)
            f.write(text)

    print("\n===== All configurations ranked by 2016-20 Sharpe (selection uses 2016-20 only) =====\n")
    show = R.copy()
    for c in ("insample_ann_return", "insample_max_drawdown", "eval_ann_return", "eval_max_drawdown", "live_cum_return"):
        show[c] = (show[c] * 100).round(1)
    print(show.round(2).to_string())
    print("\nMedian by setting (each setting averaged over all other settings):")
    for d in ("K", "lookback", "weights", "top_pct"):
        print(G.groupby(d)[["insample_sharpe", "insample_calmar", "eval_sharpe", "eval_calmar"]].median().round(2).T
              .to_string(), "\n")
    rho_s = G[["insample_sharpe", "eval_sharpe"]].corr(method="spearman").iloc[0, 1]
    rho_c = G[["insample_calmar", "eval_calmar"]].corr(method="spearman").iloc[0, 1]
    print(f"Rank correlation 2016-20 -> EVAL: Sharpe {rho_s:.2f}, Calmar {rho_c:.2f}")

    print("\nPart 2: integrity checks on the configured strategy (config/strategy.yaml)")
    C = checks(cfg, universe)
    C.to_csv(out / "checks.csv", index=False)
    print(C.to_string(index=False))
    print(f"\nOutputs in {out}")
    if (C["result"] == "FAIL").any():
        sys.exit(1)


if __name__ == "__main__":
    main()
