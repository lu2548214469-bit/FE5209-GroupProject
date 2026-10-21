"""Build the clean data package in data/ from the providers' raw files.

Not needed to run the strategy: data/ already contains the output. Kept so the cleaning
step is transparent and can be re-run if a provider sends new files.

Raw inputs (not in the repo):
  --panel    sg_six_factor_panel_2006_2026_final.csv.gz  (weekly six-factor panel, FX back-filled)
  --sti      STI_Total_Return_LSEG_export.xlsx           (LSEG .TRISTI, daily, SGD)
  --package  unzipped SGX_comprehensive_2006_2026_handoff/ (daily prices to 2026-09-24, security
             master, corporate actions)
  --team     unzipped SGX_TEAM_HANDOFF/ (daily prices and FX to 2026-10-15, used to extend the
             daily data past 2026-09-24; needs pyarrow to read the parquet file)

Cleaning rules:
  1. A stock-week enters the investable universe only if
       - price_eligible is True (blank in the four newest weeks 2026-09-18..10-09 -> treated as True), and
       - all six style scores are present (availability flag 1 / "1" / True and a finite score; the
         provider writes the Size and Value flags as True/False in history and 1/0 in the new weeks).
     Every other row is dropped.
  2. Only the columns the strategy uses are kept; internal flags, PIT/source notes, FX working
     columns and the raw inputs behind Size / Value are removed.
  3. The STI export is reduced to a two-column daily table (date, level).
  4. Daily inputs for the live window and the execution account:
       prices_daily.csv.gz   date, ticker, close (listing currency), adj_close (total-return adjusted),
                             volume. SGX_comprehensive to 2026-09-24, then SGX_TEAM_HANDOFF, chained on
                             2026-09-24 (the two sources agree exactly over September 2026).
       fx_daily.csv          SGD per USD / EUR (from SGX_TEAM_HANDOFF), for non-SGD listings
       trading_sessions.csv  proxy trading calendar: >= 50 of the 114 names with positive volume,
                             plus the SGX_TEAM_HANDOFF trading days after 2026-09-24
       security_master.csv   ticker, company name, listing currency, sector, listing date (all 114)
       corporate_actions.csv cash dividends and splits for universe stocks
       team_ticker_map.csv   SGX ticker <-> SGX_TEAM_HANDOFF gvkey_iid, matched on daily closes in 2026
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

SCORES = {"quality": "Quality", "momentum": "Momentum", "low_risk": "LowRisk",
          "investment": "Investment", "size": "Size", "value": "Value"}
GZ = {"method": "gzip", "mtime": 0}


def clean_panel(path: Path) -> pd.DataFrame:
    p = pd.read_csv(path, low_memory=False)
    eligible = p["price_eligible"].map({True: True, False: False, "True": True, "False": False}).fillna(True)
    ok = eligible.astype(bool).to_numpy().copy()
    for src in SCORES.values():
        flag = p[f"{src}_available"].astype(str).str.strip().map({"1": 1, "1.0": 1, "True": 1}).fillna(0)
        ok &= (flag == 1).to_numpy() & np.isfinite(p[f"{src}_score"]).to_numpy()
    p = p[ok]
    mcap = p["market_cap_sgd_rebuilt"] if "market_cap_sgd_rebuilt" in p else p["weekly_market_cap_proxy"]
    out = pd.DataFrame({
        "signal_date": pd.to_datetime(p["signal_date"]).dt.strftime("%Y-%m-%d"),
        "execution_date": p["execution_date"],
        "next_execution_date": p["next_execution_date"],
        "ticker": p["ticker"],
        "sector": p["six_sector"],
        "market_cap_sgd": mcap,
        **{f"{k}_score": p[f"{v}_score"] for k, v in SCORES.items()},
        "forward_return": p["forward_return"],
    })
    assert out["forward_return"].notna().all(), "universe row without a forward return"
    assert out["sector"].notna().all(), "universe row without a sector"
    return out.sort_values(["signal_date", "ticker"]).reset_index(drop=True)


def clean_sti(path: Path) -> pd.DataFrame:
    x = pd.read_excel(path, header=None)
    d = x[pd.to_datetime(x[0], errors="coerce").notna() & pd.to_numeric(x[1], errors="coerce").notna()]
    s = pd.DataFrame({"date": pd.to_datetime(d[0]).dt.strftime("%Y-%m-%d"),
                      "sti_tr_level": pd.to_numeric(d[1])})
    return s.drop_duplicates("date").sort_values("date").reset_index(drop=True)


def read_team_daily(team: Path) -> pd.DataFrame:
    cols = ["gvkey", "iid", "date", "price", "available_adjusted_price", "volume", "currency", "fx_to_sgd"]
    t = pd.read_parquet(team / "data" / "sgx_daily_market.parquet", columns=cols)
    t["sec"] = t["gvkey"].astype(str) + "_" + t["iid"].astype(str)
    t["date"] = pd.to_datetime(t["date"]).dt.normalize()
    return t


def match_team_tickers(comp: pd.DataFrame, team: pd.DataFrame) -> pd.DataFrame:
    """Map each SGX ticker to the TEAM security whose 2026 daily close matches most often (within 0.5%)."""
    t = team[team["date"] >= "2026-01-01"].pivot_table(index="date", columns="sec", values="price", aggfunc="last")
    c = comp[comp["date"] >= "2026-01-01"].pivot(index="date", columns="ticker", values="close").reindex(t.index)
    tv, rows = t.to_numpy(), []
    for k in c.columns:
        x = c[k].to_numpy()[:, None]
        hits = ((np.abs(tv - x) <= 0.0051 * np.abs(x)) & np.isfinite(tv) & np.isfinite(x)).sum(0)
        j = int(hits.argmax())
        rows.append({"ticker": k, "team_sec": t.columns[j], "matched_days": int(hits[j]),
                     "days": int(np.isfinite(x).sum())})
    m = pd.DataFrame(rows)
    return m[m["matched_days"] >= 80].reset_index(drop=True)      # below this the stock is not in TEAM


def clean_daily_inputs(package: Path, team_dir: Path, tickers: set[str], out: Path) -> None:
    d = package / "data"
    comp = pd.read_csv(d / "prices_daily_2006.csv", usecols=["date", "ticker", "close", "adj_close", "volume"])
    comp["date"] = pd.to_datetime(comp["date"])
    last = comp["date"].max()
    active = comp.assign(pos=comp["volume"].gt(0)).groupby("date")["pos"].sum()
    sessions = set(active[active.ge(50)].index)

    team = read_team_daily(team_dir)
    tmap = match_team_tickers(comp, team)
    tmap.to_csv(out / "team_ticker_map.csv", index=False)
    t = team.merge(tmap[["ticker", "team_sec"]], left_on="sec", right_on="team_sec")
    anchor_c = comp[comp["date"] == last].set_index("ticker")["adj_close"]
    anchor_t = t[t["date"] == last].set_index("ticker")["available_adjusted_price"]
    ext = t[t["date"] > last].copy()
    ext["adj_close"] = ext["available_adjusted_price"] / ext["ticker"].map(anchor_t) * ext["ticker"].map(anchor_c)
    ext = ext.rename(columns={"price": "close"})[["date", "ticker", "close", "adj_close", "volume"]]
    sessions |= set(ext["date"].unique())

    prices = pd.concat([comp, ext])
    prices = prices[prices["ticker"].isin(tickers)].sort_values(["ticker", "date"])
    prices["date"] = prices["date"].dt.strftime("%Y-%m-%d")
    prices.to_csv(out / "prices_daily.csv.gz", index=False, float_format="%.10g", compression=GZ)
    pd.DataFrame({"date": sorted(pd.DatetimeIndex(list(sessions)).strftime("%Y-%m-%d"))}).to_csv(
        out / "trading_sessions.csv", index=False)

    fx = team[team["currency"].isin(["USD", "EUR"])].dropna(subset=["fx_to_sgd"])
    fx = fx.groupby(["date", "currency"])["fx_to_sgd"].median().unstack().sort_index()
    fx.index = fx.index.strftime("%Y-%m-%d")
    fx.rename(columns={"USD": "sgd_per_usd", "EUR": "sgd_per_eur"}).to_csv(out / "fx_daily.csv",
                                                                         index_label="date", float_format="%.8g")

    master = pd.read_csv(d / "stock_universe_six_sectors.csv")
    master[["ticker", "company_name", "currency", "six_sector", "listing_date"]].to_csv(
        out / "security_master.csv", index=False)
    actions = pd.read_csv(d / "corporate_actions_2006.csv")
    actions = actions[actions["ticker"].isin(tickers)][["date", "ticker", "action_type", "dividend", "split_ratio"]]
    actions.sort_values(["date", "ticker"]).to_csv(out / "corporate_actions.csv", index=False)
    print(f"sessions {len(sessions)}, prices {len(prices)} rows to {prices['date'].max()}, "
          f"TEAM-mapped tickers {len(tmap)}, actions {len(actions)}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--panel", required=True)
    ap.add_argument("--sti", required=True)
    ap.add_argument("--package", required=True)
    ap.add_argument("--team", required=True)
    ap.add_argument("--out", default=str(Path(__file__).resolve().parents[1] / "data"))
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    panel = clean_panel(Path(a.panel))
    sti = clean_sti(Path(a.sti))
    panel.to_csv(out / "sg_universe_weekly.csv.gz", index=False, float_format="%.10g", compression=GZ)
    sti.to_csv(out / "sti_total_return_daily.csv", index=False)
    print(f"universe rows {len(panel)}, weeks {panel.signal_date.nunique()}, tickers {panel.ticker.nunique()}, "
          f"{panel.signal_date.min()}..{panel.signal_date.max()}")
    clean_daily_inputs(Path(a.package), Path(a.team), set(panel["ticker"]), out)
    print(f"STI days {len(sti)}, {sti.date.min()}..{sti.date.max()}")


if __name__ == "__main__":
    main()
