"""A visible end date cannot conceal missing signals or FX observations."""
from pathlib import Path
import sys
import tempfile
import unittest
import pandas as pd

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from scripts.continue_oos import check_inputs


def bundle(path):
    dates=['2026-10-16','2026-10-19','2026-10-20']
    pd.DataFrame({'date':dates}).to_csv(path/'trading_sessions.csv',index=False)
    pd.DataFrame([dict(date=d,ticker=f'A{i}.SI',close=1.,volume=10000) for d in dates for i in range(50)]).to_csv(path/'prices_daily.csv.gz',index=False,compression='gzip')
    pd.DataFrame({'date':dates,'sti_tr_level':[100.,101.,102.]}).to_csv(path/'sti_total_return_daily.csv',index=False)
    pd.DataFrame({'date':dates,'sgd_per_usd':1.3,'sgd_per_eur':1.5}).to_csv(path/'fx_daily.csv',index=False)
    pd.DataFrame([dict(date='2026-10-12',ticker='P9D.SI',action_type='cash_dividend',dividend=.03,split_ratio=1.)]).to_csv(path/'corporate_actions.csv',index=False)
    rows=[]
    for signal,trade in [('2026-09-25','2026-09-28'),('2026-10-02','2026-10-05'),('2026-10-09','2026-10-12'),('2026-10-16','2026-10-19')]:
        rows.append(dict(signal_date=signal,execution_date=trade,ticker='A0.SI',**{f'{f}_score':1. for f in ['quality','momentum','low_risk','investment','size','value']}))
    pd.DataFrame(rows).to_csv(path/'sg_universe_weekly.csv.gz',index=False,compression='gzip')


class TestReadiness(unittest.TestCase):
    def test_old_signal_cannot_substitute_for_the_new_friday(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);bundle(p)
            u=pd.read_csv(p/'sg_universe_weekly.csv.gz');u=u[u.signal_date.ne('2026-10-16')]
            u.to_csv(p/'sg_universe_weekly.csv.gz',index=False,compression='gzip')
            r=check_inputs(p,'2026-10-20')
            self.assertFalse(r['passed'])
            self.assertTrue(any('2026-10-16 is missing' in e for e in r['errors']))

    def test_last_fx_date_does_not_hide_a_missing_middle_date(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);bundle(p)
            f=pd.read_csv(p/'fx_daily.csv');f=f[f.date.ne('2026-10-19')];f.to_csv(p/'fx_daily.csv',index=False)
            r=check_inputs(p,'2026-10-20')
            self.assertFalse(r['passed'])
            self.assertTrue(any('FX observations missing for 2026-10-19' in e for e in r['errors']))

    def test_verified_missing_dividend_must_be_supplied(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);bundle(p)
            a=pd.read_csv(p/'corporate_actions.csv');a.iloc[:0].to_csv(p/'corporate_actions.csv',index=False)
            r=check_inputs(p,'2026-10-20')
            self.assertFalse(r['passed'])
            self.assertTrue(any('Civmec' in e for e in r['errors']))


if __name__=='__main__':unittest.main()
