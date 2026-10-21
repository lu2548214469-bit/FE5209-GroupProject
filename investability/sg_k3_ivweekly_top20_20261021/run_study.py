"""Replay the frozen K3 strategy through the unchanged source execution engine.

Scenarios vary execution assumptions, never source factor scores or stock picks.
Every capital case grows/declines through its own share/cash/dividend path.
"""
from pathlib import Path
import sys,json,hashlib,time,copy,os
from concurrent.futures import ProcessPoolExecutor,as_completed
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
_candidates=([Path(os.environ['FE5209_SOURCE_REPO'])] if os.environ.get('FE5209_SOURCE_REPO') else
             [HERE.parent.parent,ROOT/'FE5209-GroupProject',ROOT/'FE5209-GroupProject-attribution-review'])
REPO=next((p for p in _candidates if (p/'config/strategy.yaml').exists() and (p/'src/sgfactor/live/engine.py').exists()),None)
if REPO is None:raise RuntimeError('Source repository not found; set FE5209_SOURCE_REPO to the FE5209-GroupProject checkout')
REFERENCE=REPO/'performance_attribution/sg_k3_ivweekly_top20_20261021/reproduced_main'
sys.path[:0]=[str(REPO),str(REPO/'src')]
from sgfactor.config import load_config
from sgfactor.live.run import load_execution_data
from sgfactor.live.engine import ExecutionConfig,simulate,plans_from_targets
from sgfactor.live.dividends import prepare_source_dividends

CTX=None
def input_bytes(path):
    p=Path(path);b=p.read_bytes()
    return b if p.suffix=='.gz' else b.replace(b'\r\n',b'\n')

def initialise():
    global CTX
    cfg=load_config();ecfg=load_config(REPO/'config/execution.yaml')
    data=load_execution_data(ecfg)
    h=pd.read_csv(REFERENCE/'03_target_holdings_weekly.csv')
    h=h[h.signal_date.between(*cfg['periods']['eval'])][['signal_date','execution_date','ticker','weight']]
    live=pd.read_csv(REFERENCE/'08_live_holdings.csv').rename(columns={'trade_date':'execution_date'})
    dates=dict(zip(cfg['live_window']['trade_dates'],['2026-09-25','2026-10-02','2026-10-09']))
    live['signal_date']=live.execution_date.map(dates)
    targets=pd.concat([h,live[h.columns]],ignore_index=True)
    for col in ['signal_date','execution_date']:targets[col]=pd.to_datetime(targets[col])
    end=pd.Timestamp(ecfg['end'])
    actions=prepare_source_dividends(data['actions'],targets,data['sessions'],end)
    paths=['config/strategy.yaml','config/execution.yaml','src/sgfactor/live/engine.py','src/sgfactor/live/run.py',
        'src/sgfactor/live/dividends.py','data/prices_daily.csv.gz','data/fx_daily.csv','data/corporate_actions.csv',
        'data/trading_sessions.csv','data/security_master.csv']
    digest=hashlib.sha256()
    for name in paths:digest.update(name.encode());digest.update(input_bytes(REPO/name))
    for name in ['03_target_holdings_weekly.csv','08_live_holdings.csv']:digest.update(input_bytes(REFERENCE/name))
    CTX=dict(cfg=cfg,ecfg=ecfg,data=data,targets=targets,actions=actions,inputs_fingerprint=digest.hexdigest())

def cache_key(case):
    return hashlib.sha256((CTX['inputs_fingerprint']+json.dumps(case,sort_keys=True)).encode()).hexdigest()

def measures(r,case,settings,start,end,initial,label):
    d=r['daily'].set_index('date');z=d[(d.index>start)&(d.index<=end)]
    if initial is None:initial=float(d.loc[:start].nav.iloc[-1])
    nav=np.r_[initial,z.nav.to_numpy()]
    ret=nav[1:]/nav[:-1]-1
    years=(end-start).days/365.25
    f=r['fills'];f=f[f.date.between(z.index.min(),z.index.max())]
    o=r['orders'];o=o[o.activation.between(z.index.min(),z.index.max())]
    last=r['daily'].set_index('date').loc[end]
    # Original requested notional and residual valued at the signal's sizing mark.
    prices=CTX['data']['prices'].pivot(index='date',columns='ticker',values='close').reindex(CTX['data']['sessions']).ffill()
    marks=np.array([prices.at[pd.Timestamp(s),t] for s,t in zip(o.signal_date,o.ticker)])
    requested=float(np.sum(abs(o.original_requested.to_numpy())*marks))
    residual=float(np.sum(abs(o.remaining.to_numpy())*marks))
    phase=pd.Series(CTX['data']['sessions'].get_indexer(f.date),index=f.index)-f.order_id.map(r['orders'].set_index('order_id').activation.map(lambda x:CTX['data']['sessions'].get_loc(x))) if len(f) else pd.Series(dtype=float)
    traded_ref=float((f.shares.abs()*f.reference_close).sum())
    row=dict(scenario=case['name'],family=case['family'],window=label,
        initial_cash=settings['initial_cash'],start_nav=initial,end_nav=float(z.nav.iloc[-1]),
        cumulative_return=float(nav[-1]/initial-1),cagr=float((nav[-1]/initial)**(1/years)-1) if years>1 else None,
        max_drawdown=float(np.max(1-nav/np.maximum.accumulate(nav))),
        daily_sharpe_rf0=float(ret.mean()/ret.std(ddof=1)*np.sqrt(252)),
        fills=len(f),orders=len(o),unfinished_orders=int(o.remaining.ne(0).sum()),
        requested_count_completion=float(o.remaining.eq(0).mean()) if len(o) else None,
        requested_value_completion=1-residual/requested if requested else None,
        requested_signal_notional=requested,residual_signal_notional=residual,
        fees=float(f.total_fee.sum()),commission=float(f.commission.sum()),market_fee=float(f.market_fee.sum()),tax=float(f.tax.sum()),
        shortfall=float(f.slippage_cost.sum()),traded_reference_notional=traded_ref,
        paid_cost_bps_of_traded_reference=10000*float(f.total_fee.sum()+f.slippage_cost.sum())/traded_ref if traded_ref else None,
        minimum_commission_fill_fraction=float((f.commission<=settings['minimum_commission']+1e-8).mean()) if len(f) else None,
        delayed_fill_fraction=float(phase.gt(0).mean()) if len(phase) else None,
        mean_fill_delay_sessions=float(phase.mean()) if len(phase) else None,
        max_fill_delay_sessions=float(phase.max()) if len(phase) else None,
        cash_fraction_mean=float((z.cash/z.nav).mean()),receivable_fraction_mean=float((z.receivable/z.nav).mean()),
        end_cash_fraction=float(last.cash/last.nav),dividend_income=float(z.action_income.sum()),
        participation=settings['participation'],volume_multiplier=case.get('volume_multiplier',1),
        slippage_bps=settings['slippage_bps'],impact_y=settings['impact_y'],lot=settings['default_lot'],
        max_order_sessions=settings['max_order_sessions'],minimum_commission=settings['minimum_commission'],
        fee_tax_rate=settings['fee_tax_rate'],max_accounting_error=r['audit']['max_accounting_error'])
    return row

def run_case(case):
    t0=time.monotonic();out=HERE/'scenarios'/case['name'];summary=out/'summary.json'
    if summary.exists():
        cached=json.loads(summary.read_text())
        if cached.get('cache_key')!=cache_key(case):raise ValueError('Cached case inputs differ; use a new study output directory: '+case['name'])
        return cached
    settings={**CTX['ecfg']['settings'],**case.get('settings',{})}
    data=CTX['data'];prices=data['prices']
    if case.get('volume_multiplier',1)!=1:
        prices=prices.copy();prices['volume']*=case['volume_multiplier']
    fresh=case.get('fresh',False)
    targets=CTX['targets'][CTX['targets'].signal_date.ge('2026-09-25')] if fresh else CTX['targets']
    actions=None if fresh else CTX['actions']
    if fresh:
        a=data['actions'];assert not a[a.ticker.isin(targets.ticker)&a.date.between('2026-09-25','2026-10-15')&a.action_type.eq('cash_dividend')].shape[0]
    rules=None
    if case.get('lot_revision'):
        # Actual announced initial 11 names, not retrospective price thresholds.
        tickers=['D05.SI','G07.SI','H02.SI','C07.SI','J36.SI','BN4.SI','O39.SI','K6S.SI','S68.SI','U11.SI','V03.SI']
        rules=pd.DataFrame(dict(ticker=tickers,effective_date=pd.Timestamp('2026-10-05'),lot_size=10,tick_size=0.,tradable=True))
    if case.get('tick_rounding'):
        # Only the current October window; no claim of historically unadjusted ticks.
        p=prices[prices.date.ge('2026-09-25')].copy()
        master=data['master'].set_index('ticker')
        raw=pd.read_csv(REPO/'data/prices_daily.csv.gz',usecols=['date','ticker','close'],parse_dates=['date'])
        p=p.merge(raw.rename(columns={'close':'native_close'}),on=['date','ticker'],validate='one_to_one')
        native_tick=np.select([p.native_close.lt(.2),p.native_close.lt(1)],[.001,.005],default=.01)
        p['tick_size']=native_tick*p.close/p.native_close
        p['effective_date']=p.date;p['lot_size']=100;p['tradable']=True
        rules=p[['ticker','effective_date','lot_size','tick_size','tradable']]
    r=simulate(prices,data['sessions'],plans_from_targets(targets),ExecutionConfig(**settings),
               actions=actions,actions_verified=False,rules=rules,end=CTX['ecfg']['end'])
    daily=r['daily'];f=r['fills']
    assert daily.cash.min()>=-1e-6
    if len(f):
        assert (f.shares.abs()<=settings['participation']*f.source_volume+1e-5).all()
        assert (f.shares.abs()*f.reference_close<=settings['participation']*f.lagged_adv+1e-5).all()
        assert (f.shares.abs()%f.lot_size==0).all()
    # Exact accounting bridge across the whole realised path.
    bridge=daily.price_pnl.sum()+daily.action_income.sum()-daily.fees.sum()-daily.slippage_cost.sum()
    assert abs(bridge-(daily.nav.iloc[-1]-settings['initial_cash']))<1e-5
    rows=[]
    if not fresh:
        rows.append(measures(r,case,settings,pd.Timestamp('2021-01-07'),pd.Timestamp('2026-09-30'),settings['initial_cash'],'EVAL'))
        rows.append(measures(r,case,settings,pd.Timestamp('2021-01-07'),pd.Timestamp('2026-10-15'),settings['initial_cash'],'WHOLE'))
    rows.append(measures(r,case,settings,pd.Timestamp('2026-10-01'),pd.Timestamp('2026-10-15'),None,'OCTOBER_CLOSE'))
    if fresh:rows.append(measures(r,case,settings,pd.Timestamp('2026-09-30'),pd.Timestamp('2026-10-15'),settings['initial_cash'],'OCTOBER_CASH'))
    out.mkdir(parents=True,exist_ok=True)
    for key in ['daily','holdings','orders','fills','attempts','signals','events','contributions']:
        r[key].to_csv(out/(key+'.csv.gz'),index=False,compression='gzip')
    audit={**r['audit'],'case':case,'runtime_seconds':time.monotonic()-t0,
        'source_cash_dividend_delay_days':14,'actual_corporate_action_coverage_verified':False,
        'strategy_target_mode':'frozen targets; no reselection; scenario orders reflect actual holdings'}
    (out/'audit.json').write_text(json.dumps(audit,indent=2,default=str),encoding='utf-8')
    result=dict(case=case,rows=rows,runtime_seconds=time.monotonic()-t0,cache_key=cache_key(case))
    summary.write_text(json.dumps(result,indent=2,allow_nan=False),encoding='utf-8')
    return result

def grid():
    cases=[]
    def add(name,family,changes=None,**kwargs):cases.append(dict(name=name,family=family,settings=changes or {},**kwargs))
    for aum in [25000,50000,100000,250000,500000,1000000,2000000,5000000]:
        add('capital_'+str(aum),'capital',{'initial_cash':aum})
    for aum in [100000,1000000]:
        for p in [.01,.05]:add(f'participation_{int(p*100)}pct_{aum}','participation',{'initial_cash':aum,'participation':p})
        add(f'volume_half_{aum}','volume',{'initial_cash':aum},volume_multiplier=.5)
        for days in [1,3]:add(f'life_{days}_{aum}','order_life',{'initial_cash':aum,'max_order_sessions':days})
        add(f'lot1_{aum}','lot_diagnostic',{'initial_cash':aum,'default_lot':1})
        add(f'lot_revision_{aum}','announced_lot_rules',{'initial_cash':aum},lot_revision=True)
        add(f'joint_adverse_{aum}','joint_stress',{'initial_cash':aum,'participation':.05,'slippage_bps':20,'impact_y':.5,'minimum_commission':10,'fee_tax_rate':.09},volume_multiplier=.5)
    for minimum in [0,1,10]:add(f'minimum_{minimum}','commission',{'minimum_commission':minimum})
    for bps in [0,5,20,50]:add(f'slippage_{bps}','slippage',{'slippage_bps':bps})
    for y in [.25,.5,1]:add('impact_'+str(y),'impact',{'impact_y':y})
    add('impact_0.5_1000000','impact',{'initial_cash':1000000,'impact_y':.5})
    add('fee_tax_9pct','tax_diagnostic',{'fee_tax_rate':.09})
    add('reserve_5pct','cash_reserve',{'reserve_fraction':.05})
    add('settlement_T0','settlement_diagnostic',{'settlement_sessions':0})
    for aum in [25000,50000,100000,250000,500000,1000000]:
        add(f'fresh_capital_{aum}','fresh_capital',{'initial_cash':aum},fresh=True)
    for aum in [100000,1000000]:
        add(f'fresh_tick_rounding_{aum}','tick_diagnostic',{'initial_cash':aum},fresh=True,tick_rounding=True)
    return cases

def main():
    HERE.mkdir(exist_ok=True);(HERE/'results').mkdir(exist_ok=True)
    initialise();cases=grid()
    (HERE/'scenario_grid.json').write_text(json.dumps(cases,indent=2))
    # Required control before stress cases: whole daily path must match the delivery.
    baseline=next(c for c in cases if c['name']=='capital_100000')
    first=run_case(baseline)
    actual=pd.read_csv(HERE/'scenarios/capital_100000/daily.csv.gz')
    expected=pd.read_csv(REFERENCE/'execution/daily.csv')
    assert actual.date.equals(expected.date)
    error=float(abs(actual.nav-expected.nav).max());assert error<1e-6
    (HERE/'results/baseline_reconciliation.json').write_text(json.dumps(dict(max_daily_nav_error_sgd=error,source_strategy_commit='abf1c66ffd82b03c6183ff3546a5eb30749db934',cases=len(cases),original_strategy_unchanged=True),indent=2))
    print('BASELINE VERIFIED',error,'; scenarios',len(cases),flush=True)
    results=[first]
    with ProcessPoolExecutor(max_workers=2,initializer=initialise) as pool:
        futures={pool.submit(run_case,c):c['name'] for c in cases if c!=baseline}
        for future in as_completed(futures):
            result=future.result();results.append(result)
            pd.DataFrame([row for item in results for row in item['rows']]).to_csv(HERE/'results/scenario_summary.csv',index=False)
            print('DONE',len(results),'/',len(cases),result['case']['name'],round(result['runtime_seconds'],2),'s',flush=True)
    print('ALL SCENARIOS COMPLETE',flush=True)

if __name__=='__main__':main()
