"""Integration check on the real data: the strategy + ported engine reproduce the frozen account.

History: with the earlier 74-stock panel this project reproduced fangling's own frozen run
FINAL_100K_DIV14_V1 exactly (ending NAV SGD 328,755.16, 3,525 fills; commit 8b486d7). The
reference below is the same engine and settings on the final FX-complete panel with the frozen
strategy (K3, IV re-estimated weekly, top 20%), run through the live window (first live trade
2026-10-01, last mark 2026-10-20).
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from run_backtest import backtest, execution_targets          # noqa: E402
from sgfactor.backtest.live_window import live_window          # noqa: E402
from sgfactor.config import load_config                        # noqa: E402
from sgfactor.data import load_benchmark                       # noqa: E402
from sgfactor.live import run_execution                        # noqa: E402

REFERENCE = dict(fills=5432, orders=4333, incomplete_orders=98, source_cash_events=477,
                 last_mark="2026-10-20", ending_nav=264827.09, dividend_income=46591.17,
                 total_fees=28336.12, eval_end_nav=285647.38)
# 2026-10-24: live window extended to 2026-10-20 (trade 2026-10-19 on the 2026-10-16 signal) and the P9D
# dividend of 2026-10-12 added; previous reference (last mark 2026-10-15): 5,418 fills, ending NAV 266,334.30.


class ReproduceFrozenAccount(unittest.TestCase):
    def test_matches_frozen_account(self):
        cfg = load_config()
        ecfg = load_config(ROOT / "config" / "execution.yaml")
        res = backtest(cfg)
        live = live_window(res["holdings"], res["universe"], load_benchmark(cfg), cfg)
        s = run_execution(execution_targets(res, live, cfg), ecfg, ecfg["eval_end"],
                          cfg["live_window"]["trade_dates"][0])["summary"]
        for k in ("fills", "orders", "incomplete_orders", "source_cash_events", "last_mark"):
            self.assertEqual(s[k], REFERENCE[k], k)
        for k in ("ending_nav", "dividend_income", "total_fees"):
            self.assertAlmostEqual(s[k], REFERENCE[k], delta=0.05, msg=k)
        self.assertAlmostEqual(s["EVAL"]["end_nav"], REFERENCE["eval_end_nav"], delta=0.05)


if __name__ == "__main__":
    unittest.main()
