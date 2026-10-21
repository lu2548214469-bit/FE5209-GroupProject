"""Strategy selection test: which configuration is best on 2016-2020 data?

    python tests/strategy_tests/run_strategy_tests.py        # about 2 minutes

Only the selection period 2016-01 .. 2020-12 is used and reported (signal dates; split into
2016-18 and 2019-20 as well). Nothing after 2020 is printed or used to rank.

Grid, no baseline: every combination of
    K         styles selected each year      3, 4
    weights   how the selected styles are weighted, and how often the weights are re-estimated
              EW          equal weight
              IV_yearly   inverse volatility, re-estimated once a year (with the style selection)
              IV_monthly  inverse volatility, re-estimated at the first signal week of each month
              IV_weekly   inverse volatility, re-estimated every week
    top       share of the universe held     20, 25, 30 %   (buffer exit line = top + 10 pp)
= 24 configurations. Fixed for all: 3-year lookback for the yearly style selection, 52-week window
and 5-80% bounds for IV, 30% sector cap, small-cap Size, weekly stock rebalance, 10 bp one-way
cost, risk-free rate 0.

Ranking rule: 2016-20 Sharpe, ties broken by 2016-20 Calmar.

Output
  1  matrices per K (rows = weights, columns = share held) for every 2016-20 metric
  2  full ranking
  3  median effect of each setting
  4  robustness of the ranking: costs 10 / 20 / 30 bp; the top configuration's neighbours
  5  top configuration vs STI and the equal-weight universe: Newey-West t, bootstrap p
  6  turnover and holding statistics of the top 10
  7  integrity checks of the top configuration (weights, sector cap, look-ahead)
Files in outputs/strategy_tests/.
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
from sgfactor.backtest.metrics import performance, trade_stats      # noqa: E402
from sgfactor.config import load_config, override                   # noqa: E402
from sgfactor.data import load_universe                            # noqa: E402
from sgfactor.factors import factor_returns, style_scores           # noqa: E402
from sgfactor.strategy import select_styles                         # noqa: E402

LOOKBACK = 3
WEIGHTS = {"EW": ("EW", "yearly"), "IV_yearly": ("IV", "yearly"), "IV_monthly": ("IV", "monthly"),
           "IV_weekly": ("IV", "weekly")}
GRID = {"K": [3, 4], "weights": list(WEIGHTS), "top": [0.20, 0.25, 0.30]}
PERIODS = {"2016_20": ("2016-01-01", "2020-12-31"), "2016_18": ("2016-01-01", "2018-12-31"),
           "2019_20": ("2019-01-01", "2020-12-31")}
SEL = PERIODS["2016_20"]
COSTS = (0.001, 0.002, 0.003)
METRICS = ("ann_return", "ann_vol", "sharpe", "max_drawdown", "calmar")


def label(k, wm, top) -> str:
    return f"K{k}_{wm}_top{int(round(top * 100))}"


def configs():
    yield from itertools.product(*GRID.values())


def in_sel(index) -> np.ndarray:
    return (index >= SEL[0]) & (index <= SEL[1])


def run_grid(cfg0: dict, universe: pd.DataFrame):
    fret = factor_returns(style_scores(universe, cfg0), list(cfg0["factors"]), cfg0["factor_returns"]["leg_fraction"])
    rows, store = [], {}
    combos = list(configs())
    for i, (k, wm, top) in enumerate(combos, 1):
        method, freq = WEIGHTS[wm]
        cfg = override(cfg0, **{"selection.top_k": k, "selection.lookback_years": LOOKBACK,
                                "weighting.method": method, "weighting.rebalance": freq,
                                "portfolio.select_fraction": top, "portfolio.exit_fraction": round(top + 0.10, 2)})
        res = backtest(cfg, universe, fret)
        W, path = res["weekly"], res["path"]
        m = in_sel(W.index)
        name = label(k, wm, top)
        row = {"config": name, "K": k, "weights": wm,
               "top_pct": int(round(top * 100)), "avg_names": round(float(W.loc[m, "n_names"].mean()), 1),
               "ann_turnover": float(W.loc[m, "one_way_turnover"].mean() * 52)}
        for per, (a, b) in PERIODS.items():
            pm = (W.index >= a) & (W.index <= b)
            p = performance(W.loc[pm, "strategy"])
            row.update({f"{per}_{x}": p[x] for x in METRICS})
        for c in COSTS[1:]:
            net = (1 - c * path["gtr"]) * (1 + path["gross_return"]) - 1
            row[f"2016_20_sharpe_{int(c * 1e4)}bp"] = performance(net[in_sel(net.index)])["sharpe"]
        rows.append(row)
        store[name] = (cfg, res)
        print(f"  [{i:>2}/{len(combos)}] {name:<22} 2016-20 Sharpe {row['2016_20_sharpe']:.2f}  "
              f"Calmar {row['2016_20_calmar']:.2f}", flush=True)
    G = pd.DataFrame(rows).sort_values(["2016_20_sharpe", "2016_20_calmar"], ascending=False).reset_index(drop=True)
    G.insert(0, "rank", np.arange(1, len(G) + 1))
    return G, store


def matrices(G: pd.DataFrame, metric: str, pct: bool) -> str:
    out = []
    for k, g in G.groupby("K"):
        t = g.pivot(index="weights", columns="top_pct", values=metric).reindex(list(WEIGHTS))
        t = (t * 100).round(1) if pct else t.round(2)
        t.columns = [f"top{c}%" for c in t.columns]
        t.index.name = f"K={k}"
        out.append(t.to_string())
    return "\n\n".join(out)


def significance(r: pd.Series, b: pd.Series, reps: int = 2000, block: int = 8, seed: int = 0) -> dict:
    """Active return of r over b: mean, Newey-West t (4 lags), circular block bootstrap of the Sharpe gap."""
    d = pd.concat([r, b], axis=1).dropna()
    a = (d.iloc[:, 0] - d.iloc[:, 1]).to_numpy()
    x, y = d.iloc[:, 0].to_numpy(), d.iloc[:, 1].to_numpy()
    n = len(a)
    xc = a - a.mean()
    s = xc @ xc / n + sum(2 * (1 - L / 5) * (xc[L:] @ xc[:-L]) / n for L in range(1, 5))
    t = a.mean() / math.sqrt(s / n)
    sh = lambda v: v.mean() / v.std(ddof=1) * math.sqrt(52)
    obs = sh(x) - sh(y)
    rng = np.random.default_rng(seed)
    starts = rng.integers(0, n, size=(reps, math.ceil(n / block)))
    diffs = []
    for st in starts:
        idx = ((st[:, None] + np.arange(block)) % n).ravel()[:n]
        diffs.append(sh(x[idx]) - sh(y[idx]))
    diffs = np.array(diffs)
    return {"weeks": n, "active_ann_return": float(a.mean() * 52), "newey_west_t": float(t),
            "sharpe_strategy": float(sh(x)), "sharpe_benchmark": float(sh(y)), "sharpe_gap": float(obs),
            "bootstrap_p_gap_le_0": float((diffs <= 0).mean())}


def checks(cfg: dict, res: dict, universe: pd.DataFrame) -> pd.DataFrame:
    H, D, F = res["holdings"], res["decisions"], res["factor_returns"]
    H = H[(H.signal_date >= SEL[0]) & (H.signal_date <= SEL[1])]
    out = []

    def check(name, ok, detail=""):
        out.append({"check": name, "result": "PASS" if ok else "FAIL", "detail": detail})

    w = H.groupby("signal_date")["weight"].sum()
    check("weights are positive and sum to <= 1 each week", (H["weight"] > 0).all() and (w <= 1 + 1e-12).all(),
          f"min weekly invested {w.min():.3f}")
    check("no duplicate holdings", not H.duplicated(["signal_date", "ticker"]).any())
    caps = H.groupby(["signal_date", "sector"]).size().groupby("signal_date").max()
    n_target = (universe.groupby("signal_date").size().reindex(caps.index) * cfg["portfolio"]["select_fraction"]
                ).apply(math.floor)
    check("sector cap respected", (caps <= (n_target * cfg["portfolio"]["sector_cap"]).apply(math.floor)).all())
    check("holdings are inside the universe",
          H.merge(universe[["signal_date", "ticker"]], how="left", indicator=True)["_merge"].eq("both").all())
    D = D[D["year"] <= 2020]
    same = []
    for d, chosen in zip(D["decision_date"], D["selected"]):
        past = F[pd.to_datetime(F["next_execution_date"]) <= pd.Timestamp(d)]
        again, _ = select_styles(past, d, list(cfg["factors"]), cfg["selection"]["top_k"],
                                 cfg["selection"]["lookback_years"], cfg["selection"]["min_coverage"])
        same.append(", ".join(again) == chosen)
    check("no look-ahead: yearly decisions unchanged when all later data is deleted", all(same),
          f"{sum(same)}/{len(same)} years identical")
    return pd.DataFrame(out)


def pct(df: pd.DataFrame, cols) -> pd.DataFrame:
    df = df.copy()
    for c in cols:
        df[c] = (df[c] * 100).round(1)
    return df


def main() -> None:
    cfg0 = load_config()
    universe = load_universe(cfg0)
    out = ROOT / cfg0["output_dir"] / "strategy_tests"
    out.mkdir(parents=True, exist_ok=True)
    pd.set_option("display.width", 250)
    pd.set_option("display.max_rows", 200)
    n = len(list(configs()))
    print(f"Strategy selection on 2016-01 .. 2020-12 data only: {n} configurations (a few seconds each)\n")
    G, store = run_grid(cfg0, universe)
    G.to_csv(out / "selection_ranking_2016_20.csv", index=False)
    text = []

    def emit(s=""):
        print(s)
        text.append(s)

    emit("\n" + "=" * 100 + "\n1. MATRICES (one block per K; rows = weights; columns = share held)\n" + "=" * 100)
    for title, metric, is_pct in [("2016-20 Sharpe", "2016_20_sharpe", False), ("2016-20 Calmar", "2016_20_calmar", False),
                                  ("2016-20 annual return %", "2016_20_ann_return", True),
                                  ("2016-20 annual volatility %", "2016_20_ann_vol", True),
                                  ("2016-20 max drawdown %", "2016_20_max_drawdown", True),
                                  ("2016-18 Sharpe", "2016_18_sharpe", False), ("2019-20 Sharpe", "2019_20_sharpe", False)]:
        emit(f"\n----- {title} -----\n\n{matrices(G, metric, is_pct)}")

    emit("\n" + "=" * 100 + "\n2. RANKING by 2016-20 Sharpe (ties: Calmar)\n" + "=" * 100 + "\n")
    cols = ["rank", "K", "weights", "top_pct", "2016_20_ann_return", "2016_20_ann_vol", "2016_20_sharpe",
            "2016_20_max_drawdown", "2016_20_calmar", "2016_18_sharpe", "2016_18_calmar", "2019_20_sharpe",
            "2019_20_calmar"]
    emit(pct(G[cols], ["2016_20_ann_return", "2016_20_ann_vol", "2016_20_max_drawdown"]).round(2).to_string(index=False))

    emit("\n" + "=" * 100 + "\n3. MEDIAN EFFECT OF EACH SETTING (2016-20; median over all other settings)\n" + "=" * 100)
    for d in ("K", "weights", "top_pct"):
        emit("\n" + G.groupby(d)[["2016_20_sharpe", "2016_20_calmar", "2016_18_sharpe", "2019_20_sharpe"]]
             .median().round(2).T.to_string())

    best = G.iloc[0]
    emit("\n" + "=" * 100 + f"\n4. ROBUSTNESS OF THE RANKING   (top configuration: {best.config})\n" + "=" * 100)
    cost = G[["config", "2016_20_sharpe", "2016_20_sharpe_20bp", "2016_20_sharpe_30bp"]].copy()
    for c in ("2016_20_sharpe", "2016_20_sharpe_20bp", "2016_20_sharpe_30bp"):
        cost["rank_" + c.split("_")[-1]] = cost[c].rank(ascending=False, method="min").astype(int)
    cost = cost.rename(columns={"rank_sharpe": "rank_10bp"})
    emit("\n4a. Costs: 2016-20 Sharpe and rank at 10 / 20 / 30 bp one-way (top 10 at 10 bp)\n")
    emit(cost.head(10).round(2).to_string(index=False))
    emit(f"\nRank correlation of the whole ranking, 10 bp vs 30 bp: "
         f"{cost['2016_20_sharpe'].corr(cost['2016_20_sharpe_30bp'], method='spearman'):.2f}")
    keys = ["K", "weights", "top_pct"]
    diff = sum((G[k] != best[k]).astype(int) for k in keys)
    nb = G[diff == 1][["rank", "config", "2016_20_sharpe", "2016_20_calmar", "2016_18_sharpe", "2019_20_sharpe"]]
    emit(f"\n4b. Neighbours of {best.config} (one setting changed), with their rank among {len(G)}\n")
    emit(nb.round(2).to_string(index=False))

    emit("\n" + "=" * 100 + f"\n5. SIGNIFICANCE, {best.config}, weekly, 2016-20\n" + "=" * 100 + "\n")
    W = store[best.config][1]["weekly"]
    W = W[in_sel(W.index)]
    sig = pd.DataFrame({"vs STI": significance(W["strategy"], W["STI"]),
                        "vs EW universe (gross)": significance(W["strategy"], W["EW_universe"])}).T
    emit(sig.round(3).to_string())
    sig.to_csv(out / "selection_significance.csv")

    emit("\n" + "=" * 100 + "\n6. TURNOVER AND HOLDINGS, top 10, 2016-20\n" + "=" * 100 + "\n")
    rows = []
    for name in G["config"].head(10):
        cfg, res = store[name]
        h = res["holdings"]
        t = trade_stats(h[(h.signal_date >= SEL[0]) & (h.signal_date <= SEL[1])], res["universe"],
                        cfg["costs"]["one_way"])
        g = G.set_index("config").loc[name]
        rows.append({"config": name, "avg_names": g.avg_names, "one_way_turnover_per_year_%": round(g.ann_turnover * 100),
                     "round_trips": t["round_trips"], "avg_holding_weeks": round(t["avg_holding_weeks"], 1),
                     "trade_win_rate_%": round(t["trade_win_rate"] * 100, 1)})
    turn = pd.DataFrame(rows)
    emit(turn.to_string(index=False))
    turn.to_csv(out / "selection_turnover_top10.csv", index=False)

    emit("\n" + "=" * 100 + f"\n7. INTEGRITY CHECKS, {best.config}, 2016-20\n" + "=" * 100 + "\n")
    cfg, res = store[best.config]
    C = checks(cfg, res, universe)
    emit(C.to_string(index=False))
    C.to_csv(out / "checks.csv", index=False)
    with open(out / "selection_report.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(text))
    print(f"\nOutputs in {out}")
    if (C["result"] == "FAIL").any():
        sys.exit(1)


if __name__ == "__main__":
    main()
