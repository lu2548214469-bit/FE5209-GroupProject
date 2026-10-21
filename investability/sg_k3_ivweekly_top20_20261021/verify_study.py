"""Cross-ledger validation of every saved scenario and isolated exit tests."""
from pathlib import Path
import json,hashlib,unittest
import numpy as np
import pandas as pd
import run_study as study
from diagnostics import load_case
from exit_replay import replay

HERE=Path(__file__).resolve().parent;OUT=HERE/'results'

class ExitLedgerChecks(unittest.TestCase):
    def sample(self):
        cal=pd.bdate_range('2021-01-01',periods=45);start=cal[25]
        prices=pd.DataFrame(dict(date=cal,ticker='SYNTH',close=1.,volume=1000.))
        r=dict(holdings=pd.DataFrame([dict(date=start,ticker='SYNTH',shares=300,mark=1.)]),
               fills=pd.DataFrame([dict(date=start,ticker='SYNTH',shares=300,settlement_date=cal[27])]))
        return r,start,dict(sessions=cal,prices=prices)
    def test_unsettled_shares_and_receipts_are_not_immediately_available(self):
        r,start,data=self.sample();s,d,f=replay(r,start,1.,data,days=6)
        self.assertEqual(f.date.iloc[0],data['sessions'][27])
        self.assertEqual(s['fully_liquidated_session'],4)
        self.assertEqual(d.settled_sale_proceeds.iloc[1],0)
        self.assertGreater(d.settled_sale_proceeds.iloc[3],0)
        self.assertAlmostEqual(f.net_proceeds.sum(),s['sale_proceeds_settled']+s['sale_proceeds_receivable'])
    def test_zero_volume_delays_exit_and_cannot_create_sale_proceeds(self):
        r,start,data=self.sample();data['prices']['volume']=2000.
        data['prices'].loc[data['prices'].date.eq(data['sessions'][27]),'volume']=0.
        s,d,f=replay(r,start,1.,data,days=6)
        self.assertEqual(f.date.iloc[0],data['sessions'][28])
        self.assertEqual(s['fully_liquidated_session'],5)
        self.assertTrue((f.source_volume>0).all())
    def test_zero_day_can_reduce_lagged_ADV_below_one_lot(self):
        r,start,data=self.sample();data['prices'].loc[data['prices'].date.eq(data['sessions'][27]),'volume']=0.
        s,d,f=replay(r,start,1.,data,days=6)
        self.assertTrue(f.empty)
        self.assertIsNone(s['fully_liquidated_session'])
        self.assertEqual(d.remaining_shares.iloc[-1],300)
        self.assertEqual(s['sale_proceeds_settled'],0.)

def main():
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(ExitLedgerChecks)
    import io
    log=io.StringIO();test=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
    (OUT/'exit_ledger_tests.txt').write_text(log.getvalue(),encoding='utf-8');assert test.wasSuccessful()
    study.initialise();cases=study.grid();names=[x['name'] for x in cases]+['feedback_actual_holdings_100000','feedback_actual_holdings_1000000']
    checks=[]
    for name in names:
        r=load_case(name);d=r['daily'];f=r['fills'];o=r['orders'];c=r['contributions']
        initial=r['audit']['config']['initial_cash'];p=r['audit']['config']['participation']
        assert d.cash.min()>=-1e-6 and d.nav.min()>0
        error=abs(float(c.contribution_amount.sum())-float(d.nav.iloc[-1]-initial));assert error<1e-5
        filled=f.groupby('order_id').shares.sum().reindex(o.order_id,fill_value=0).to_numpy()
        assert np.max(abs(o.original_requested.to_numpy()-filled-o.remaining.to_numpy()))<1e-8
        assert (f.shares.abs()<=p*f.source_volume+1e-5).all()
        assert (f.shares.abs()*f.reference_close<=p*f.lagged_adv+1e-5).all()
        assert (f.shares.abs()%f.lot_size==0).all()
        assert (f.date>f.order_id.map(o.set_index('order_id').signal_date)).all()
        checks.append(dict(scenario=name,accounting_error=error,orders=len(o),fills=len(f)))
    # Algebraically identical caps must produce the same path, not merely similar CAGR.
    for aum in [100000,1000000]:
        a=load_case(f'participation_5pct_{aum}')['daily'];b=load_case(f'volume_half_{aum}')['daily']
        np.testing.assert_allclose(a.nav,b.nav,atol=1e-6,rtol=0)
        a=load_case(f'capital_{aum}')['daily'];b=load_case(f'lot_revision_{aum}')['daily']
        np.testing.assert_allclose(a.nav,b.nav,atol=1e-6,rtol=0)
    a=load_case('capital_100000')['daily'];b=load_case('feedback_actual_holdings_100000')['daily']
    np.testing.assert_allclose(a.nav,b.nav,atol=1e-6,rtol=0)
    original=pd.read_csv(study.REFERENCE/'execution/daily.csv')
    np.testing.assert_allclose(a.nav,original.nav,atol=1e-6,rtol=0)
    fresh=load_case('fresh_capital_100000')['daily']
    original_fresh=pd.read_csv(study.REPO/'performance_attribution/sg_k3_ivweekly_top20_20261021/reproduced_fresh_live/daily.csv')
    np.testing.assert_allclose(fresh.nav,original_fresh.nav,atol=1e-6,rtol=0)
    hashes=json.loads((HERE/'source_manifest.json').read_text())['files']
    assert all(hashlib.sha256(study.input_bytes(study.REPO/x['path'])).hexdigest()==x.get('sha256_lf_normalized',x['sha256']) for x in hashes)
    w=pd.read_csv(OUT/'signal_capacity_scenarios.csv');assert w.status.eq('OBSERVED_PROXY').all()
    summary=dict(passed=True,account_paths=len(names),frozen_target_scenarios=len(cases),feedback_scenarios=2,
        synthetic_exit_ledger_tests=3,source_files_unchanged=len(hashes),
        formal_daily_nav_reproduced=True,fresh_october_daily_nav_reproduced=True,
        order_share_conservation=True,lot_and_participation_caps_respected=True,
        future_fill_date_after_signal=True,known_lot_revision_no_current_target_impact=True,
        actual_holdings_feedback_same_for_100k=True,
        metadata='All account arithmetic/caps checked; no claim of exchange-certified fills or complete corporate actions')
    pd.DataFrame(checks).to_csv(OUT/'account_path_verification.csv',index=False)
    (OUT/'verification.json').write_text(json.dumps(summary,indent=2))
    print(log.getvalue());print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
