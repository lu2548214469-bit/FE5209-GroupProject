"""Integration check on the real data: the strategy + ported engine reproduce the frozen account.

History: with the earlier 74-stock panel this project reproduced fangling's own frozen run
FINAL_100K_DIV14_V1 exactly (ending NAV SGD 328,755.16, 3,525 fills; commit 8b486d7). The
reference below is the same engine and settings on the final FX-complete panel, run through the
live window (first live trade 2026-10-01, last mark 2026-10-15).
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

REFERENCE = dict(fills=5231, orders=4309, incomplete_orders=83, source_cash_events=466,
                 last_mark="2026-10-15", ending_nav=278856.26, dividend_income=48317.57,
                 total_fees=27404.90, eval_end_nav=297716.50)


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
