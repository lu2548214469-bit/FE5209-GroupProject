"""Boundary, missing-data and attribution checks for the course report."""
from pathlib import Path
import sys
import unittest
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from sgfactor.live.oos_report import report_window


def account():
    dates=pd.to_datetime(['2026-09-30','2026-10-01','2026-10-02','2026-10-05'])
    nav=np.array([100.,98.,99.,97.])
    daily=pd.DataFrame(dict(date=dates,nav=nav,market_value=nav-50,action_income=0.))
    holdings=pd.DataFrame(dict(date=dates,ticker='A',shares=10.,weight=(nav-50)/nav))
    contributions=pd.DataFrame(dict(date=dates,ticker='A',contribution_amount=np.r_[0.,np.diff(nav)],
                                    price_pnl=np.r_[0.,np.diff(nav)],action_income=0.,fees=0.,slippage_cost=0.))
    fills=pd.DataFrame(columns=['date','shares','total_fee','slippage_cost','notional'])
    ex=dict(daily=daily,holdings=holdings,contributions=contributions,fills=fills,
            audit={'config':{'initial_cash':100.}})
    benchmark=pd.Series([100.,99.,100.,98.],index=dates)
    return ex,benchmark


class TestOOSReporting(unittest.TestCase):
    def test_includes_first_course_day_and_cost_window(self):
        ex,b=account();r=report_window(ex,'2026-10-01','2026-10-05',b)
        self.assertAlmostEqual(r['metrics']['cumulative_return'],-.03)
        self.assertEqual(r['metrics']['trading_days'],3)
        self.assertEqual(r['metrics']['base_close_date'],'2026-09-30')
        self.assertAlmostEqual(r['stocks'].net_pnl.sum(),-3.)
        self.assertLess(abs(r['metrics']['active_reconciliation_error_pp']),1e-10)

    def test_cannot_report_a_future_missing_close(self):
        ex,b=account()
        with self.assertRaisesRegex(ValueError,'last test session missing'):
            report_window(ex,'2026-10-01','2026-10-20',b)

    def test_benchmark_must_have_every_exact_session(self):
        ex,b=account();b=b.drop(pd.Timestamp('2026-10-02'))
        with self.assertRaisesRegex(ValueError,'Missing exact benchmark'):
            report_window(ex,'2026-10-01','2026-10-05',b)

    def test_requires_opening_account_exposure(self):
        ex,b=account();ex['daily']=ex['daily'].iloc[1:]
        with self.assertRaisesRegex(ValueError,'previous-session close'):
            report_window(ex,'2026-10-01','2026-10-05',b)

    def test_rejects_unreconciled_stock_pnl(self):
        ex,b=account();ex['contributions'].loc[1,'contribution_amount']+=1
        with self.assertRaisesRegex(ValueError,'do not reconcile'):
            report_window(ex,'2026-10-01','2026-10-05',b)


if __name__=='__main__':unittest.main()
