"""Build the clean data package in data/ from the provider's raw files.

Not needed to run the strategy: data/ already contains the output. Kept so the cleaning
step is transparent and can be re-run if the provider sends a new panel.

Raw inputs (not in the repo):
  --panel    sg_six_factor_candidate_panel_2006_to_2026_10_09_no_imputation_markers.csv.gz
  --sti      STI_Total_Return_LSEG_export.xlsx  (LSEG .TRISTI, daily, SGD)
  --package  the unzipped SGX_comprehensive_2006_2026_handoff/ folder, for the daily execution inputs:
             data/prices_daily_2006.csv, data/stock_universe_six_sectors.csv, data/corporate_actions_2006.csv

Cleaning rules:
  1. A stock-week enters the investable universe only if
       - price_eligible is True (blank in the four newest weeks 2026-09-18..10-09 -> treated as True;
         the provider left it blank, and the only ineligible name on 2026-09-11 has no full score set), and
       - all six style scores are present (availability flag = 1 and the score is a finite number).
     Every other row is dropped.
  2. Only the columns the strategy uses are kept; internal flags, PIT/source notes and the raw
     inputs behind Size / Value are removed.
  3. The STI export is reduced to a two-column daily table (date, level).
  4. Daily execution inputs (used by the live / execution framework):
       trading_sessions.csv  proxy trading calendar = days on which >= 50 of the 114 names report
                             positive volume (the execution framework's rule)
       prices_daily.csv.gz   date, ticker, close, volume for the stocks that ever enter the universe
       security_master.csv   ticker, company name, trading currency, sector, listing date (all 114)
       corporate_actions.csv cash dividends and splits for universe stocks (source/notes dropped)
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

SCORES = {"quality": "Quality", "momentum": "Momentum", "low_risk": "LowRisk",
          "investment": "Investment", "size": "Size", "value": "Value"}


def clean_panel(path: Path) -> pd.DataFrame:
    p = pd.read_csv(path, low_memory=False)
    eligible = p["price_eligible"].map({True: True, False: False, "True": True, "False": False}).fillna(True)
    ok = eligible.astype(bool).to_numpy().copy()
    for src in SCORES.values():
        ok &= (p[f"{src}_available"].astype(float) == 1).to_numpy() & np.isfinite(p[f"{src}_score"]).to_numpy()
    p = p[ok]
    out = pd.DataFrame({
        "signal_date": pd.to_datetime(p["signal_date"]).dt.strftime("%Y-%m-%d"),
        "execution_date": p["execution_date"],
        "next_execution_date": p["next_execution_date"],
        "ticker": p["ticker"],
        "sector": p["six_sector"],
        "market_cap_proxy_sgd": p["weekly_market_cap_proxy"],
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


def clean_execution_inputs(package: Path, tickers: set[str], out: Path) -> None:
    d = package / "data"
    prices = pd.read_csv(d / "prices_daily_2006.csv", usecols=["date", "ticker", "close", "volume"])
    active = prices.assign(pos=prices["volume"].gt(0)).groupby("date")["pos"].sum()
    sessions = active[active.ge(50)].index
    pd.DataFrame({"date": sessions}).to_csv(out / "trading_sessions.csv", index=False)
    prices = prices[prices["ticker"].isin(tickers)].sort_values(["ticker", "date"])
    prices.to_csv(out / "prices_daily.csv.gz", index=False, float_format="%.10g",
                  compression={"method": "gzip", "mtime": 0})
    master = pd.read_csv(d / "stock_universe_six_sectors.csv")
    master[["ticker", "company_name", "currency", "six_sector", "listing_date"]].to_csv(
        out / "security_master.csv", index=False)
    actions = pd.read_csv(d / "corporate_actions_2006.csv")
    actions = actions[actions["ticker"].isin(tickers)][["date", "ticker", "action_type", "dividend", "split_ratio"]]
    actions.sort_values(["date", "ticker"]).to_csv(out / "corporate_actions.csv", index=False)
    print(f"sessions {len(sessions)} ({sessions.min()}..{sessions.max()}), price rows {len(prices)}, "
          f"actions {len(actions)}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--panel", required=True)
    ap.add_argument("--sti", required=True)
    ap.add_argument("--package", required=True)
    ap.add_argument("--out", default=str(Path(__file__).resolve().parents[1] / "data"))
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    panel = clean_panel(Path(a.panel))
    sti = clean_sti(Path(a.sti))
    panel.to_csv(out / "sg_universe_weekly.csv.gz", index=False, float_format="%.10g",
                 compression={"method": "gzip", "mtime": 0})
    sti.to_csv(out / "sti_total_return_daily.csv", index=False)
    print(f"universe rows {len(panel)}, weeks {panel.signal_date.nunique()}, tickers {panel.ticker.nunique()}, "
          f"{panel.signal_date.min()}..{panel.signal_date.max()}")
    clean_execution_inputs(Path(a.package), set(panel["ticker"]), out)
    print(f"STI days {len(sti)}, {sti.date.min()}..{sti.date.max()}")


if __name__ == "__main__":
    main()
