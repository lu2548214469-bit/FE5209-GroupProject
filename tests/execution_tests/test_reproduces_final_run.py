"""Integration check on the real data: this project's strategy + ported engine reproduce the group's
frozen final run FINAL_100K_DIV14_V1 (fangling's run_top4.py on the old repository, 2026-10-20)."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from run_backtest import backtest                      # noqa: E402
from sgfactor.config import load_config                # noqa: E402
from sgfactor.live import run_execution                # noqa: E402

REFERENCE = dict(ending_nav=328755.1589, fills=3525, orders=3043, incomplete_orders=49,
                 source_cash_events=418, dividend_income=36261.0366, total_fees=19292.0531,
                 last_mark="2026-09-21")


class ReproduceFinalRun(unittest.TestCase):
    def test_matches_frozen_final_run(self):
        cfg = load_config()
        res = backtest(cfg)
        cal = res["path"].reset_index()[["signal_date", "next_execution_date"]]
        s = run_execution(res["holdings"][["signal_date", "execution_date", "ticker", "weight"]], cal,
                          load_config(ROOT / "config" / "execution.yaml"))["summary"]
        for k in ("fills", "orders", "incomplete_orders", "source_cash_events", "last_mark"):
            self.assertEqual(s[k], REFERENCE[k], k)
        for k in ("ending_nav", "dividend_income", "total_fees"):
            self.assertAlmostEqual(s[k], REFERENCE[k], delta=0.01, msg=k)


if __name__ == "__main__":
    unittest.main()
