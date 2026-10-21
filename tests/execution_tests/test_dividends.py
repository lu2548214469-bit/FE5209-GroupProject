# Ported from fangling114514, Backtest-Framework-Top4 (commit 4faa7f2), tests/test_final_preset.py.
# Kept: the dividend-policy tests. Dropped: the check of the old repository's preset files.
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from sgfactor.live.dividends import prepare_source_dividends  # noqa: E402
from sgfactor.live.engine import ExecutionConfig, Rebalance, simulate  # noqa: E402


class DividendPolicyTests(unittest.TestCase):
    def setUp(self):
        self.cal = pd.bdate_range('2024-01-02', periods=30).difference(pd.DatetimeIndex(['2024-01-19']))
        self.targets = pd.DataFrame([dict(signal_date=pd.Timestamp('2024-01-03'),
            execution_date=pd.Timestamp('2024-01-04'), ticker='A', weight=1.)])
        self.source = pd.DataFrame([dict(date='2024-01-05', ticker='A',
            action_type='cash_dividend', dividend=1., split_ratio=np.nan)])

    def prepare(self, source=None):
        return prepare_source_dividends(self.source if source is None else source,
                                        self.targets, self.cal, pd.Timestamp('2024-01-23'))

    def test_fourteen_calendar_days_and_no_cash_before_payment_session(self):
        actions = self.prepare()
        self.assertEqual(actions.pay_date.iloc[0], pd.Timestamp('2024-01-19'))
        self.assertTrue(actions.payment_date_is_assumed.all())
        bars = pd.DataFrame(dict(date=self.cal, ticker='A', close=10., volume=10000.))
        bars.loc[bars.date.ge('2024-01-05'),'close'] = 9.
        cfg = ExecutionConfig(initial_cash=1000, default_lot=10, reserve_fraction=0,
            participation=1, adv_window=2, minimum_commission=0, broker_bps=0,
            market_bps=0, slippage_bps=0, settlement_sessions=0, action_policy='price_only_diagnostic')
        r = simulate(bars,self.cal,[Rebalance(pd.Timestamp('2024-01-03'),pd.Timestamp('2024-01-04'),{'A':1.})],
                     cfg,actions=actions,actions_verified=False,end='2024-01-23')
        daily = r['daily'].set_index('date')
        self.assertEqual(daily.loc['2024-01-18','cash'],0)
        self.assertEqual(daily.loc['2024-01-18','receivable'],100)
        self.assertEqual(daily.loc['2024-01-22','cash'],100)
        self.assertEqual(daily.loc['2024-01-22','receivable'],0)
        np.testing.assert_allclose(daily.nav,1000)
        self.assertFalse(r['audit']['corporate_action_coverage_verified'])

    def test_source_split_and_unselected_events_are_not_added_again(self):
        split = dict(date='2024-01-08',ticker='A',action_type='split_or_reverse_split',dividend=np.nan,split_ratio=2.)
        other = dict(date='2024-01-05',ticker='B',action_type='cash_dividend',dividend=5.,split_ratio=np.nan)
        a = self.prepare(pd.concat([self.source,pd.DataFrame([split,other])],ignore_index=True))
        self.assertEqual(len(a),1)
        self.assertEqual(a.kind.iloc[0],'dividend')
        self.assertEqual(a.value.iloc[0],1.)

    def test_missing_duplicate_negative_or_off_calendar_events_rejected(self):
        with self.assertRaises(ValueError):
            prepare_source_dividends(None,self.targets,self.cal,'2024-01-23')
        with self.assertRaises(ValueError):
            self.prepare(pd.concat([self.source,self.source]))
        with self.assertRaises(ValueError):
            self.prepare(self.source.assign(dividend=-1.))
        with self.assertRaises(ValueError):
            self.prepare(self.source.assign(date='2024-01-06'))

    def test_unpaid_end_of_sample_dividend_remains_receivable(self):
        actions = self.prepare()
        bars = pd.DataFrame(dict(date=self.cal,ticker='A',close=10.,volume=10000.))
        bars.loc[bars.date.ge('2024-01-05'),'close'] = 9.
        cfg = ExecutionConfig(initial_cash=1000,default_lot=10,reserve_fraction=0,
            participation=1,adv_window=2,minimum_commission=0,broker_bps=0,market_bps=0,
            slippage_bps=0,settlement_sessions=0,action_policy='price_only_diagnostic')
        r = simulate(bars,self.cal,[Rebalance(pd.Timestamp('2024-01-03'),pd.Timestamp('2024-01-04'),{'A':1.})],
                     cfg,actions=actions,actions_verified=False,end='2024-01-12')
        self.assertEqual(r['daily'].receivable.iloc[-1],100)
        self.assertEqual(r['daily'].cash.iloc[-1],0)
        self.assertEqual(r['daily'].nav.iloc[-1],1000)


if __name__ == '__main__':
    unittest.main()
