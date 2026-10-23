"""Report the course test window from an existing continuous execution account."""
from pathlib import Path
import argparse
import json
import sys
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sgfactor.live.oos_report import load_account, report_window, save_report

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--execution-dir", type=Path, required=True)
    ap.add_argument("--benchmark", type=Path, default=ROOT / "data/sti_total_return_daily.csv")
    ap.add_argument("--start", default="2026-10-01")
    ap.add_argument("--end", default="2026-10-20")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    b = pd.read_csv(args.benchmark, parse_dates=["date"]).set_index("date").sti_tr_level
    result = report_window(load_account(args.execution_dir), args.start, args.end, b)
    save_report(result, args.out)
    print((args.out / "OOS_METRICS.json").read_text(encoding="utf-8"))

if __name__ == "__main__":
    main()
