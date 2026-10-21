"""Capital tracking, cost budgets, minimum-quote checks and source manifest."""
from pathlib import Path
import json,hashlib,subprocess
import numpy as np
import pandas as pd
import run_study as study
from diagnostics import load_case

HERE=Path(__file__).resolve().parent;OUT=HERE/'results'
study.initialise();rows=[];years=[]
for aum in [25000,50000,100000,250000,500000,1000000,2000000,5000000]:
    name='capital_'+str(aum);r=load_case(name)
    daily=r['daily'].set_index('date');ev=daily[daily.index<='2026-09-30']
    t=study.CTX['targets'].pivot(index='execution_date',columns='ticker',values='weight').fillna(0)
    t=t.reindex(ev.index,method='ffill').fillna(0)*.99
    h=r['holdings'].pivot(index='date',columns='ticker',values='weight').reindex(ev.index).fillna(0)
    cols=t.columns.union(h.columns);t=t.reindex(columns=cols,fill_value=0);h=h.reindex(columns=cols,fill_value=0)
    half=((h-t).abs().sum(axis=1)+(h.sum(axis=1)-t.sum(axis=1)).abs())/2
    rows.append(dict(initial_cash=aum,mean_half_l1_target_distance=half.mean(),p95_half_l1_target_distance=half.quantile(.95),max_half_l1_target_distance=half.max(),
        mean_cash_fraction=(ev.cash/ev.nav).mean(),mean_receivable_fraction=(ev.receivable/ev.nav).mean()))
    for year in range(2021,2027):
        d=ev[ev.index.year==year];before=ev[ev.index<d.index.min()]
        base=float(before.nav.iloc[-1]) if len(before) else aum
        f=r['fills'];f=f[f.date.isin(d.index)]
        years.append(dict(initial_cash=aum,year=year,partial_year=year==2026,start_nav=base,end_nav=d.nav.iloc[-1],period_return=d.nav.iloc[-1]/base-1,
            fees=f.total_fee.sum(),shortfall=f.slippage_cost.sum(),fills=len(f),friction_fraction_start_nav=(f.total_fee.sum()+f.slippage_cost.sum())/base))
pd.DataFrame(rows).to_csv(OUT/'capital_tracking_summary.csv',index=False)
pd.DataFrame(years).to_csv(OUT/'capital_year_results.csv',index=False)

raw=pd.read_csv(study.REPO/'data/prices_daily.csv.gz',parse_dates=['date'])
base=load_case('fresh_capital_100000');f=base['fills'].merge(raw[['date','ticker','close']],on=['date','ticker'],validate='many_to_one')
f['native_tick']=np.select([f.close.lt(.2),f.close.lt(1)],[.001,.005],default=.01)
f['half_tick_bps']=.5*f.native_tick/f.close*10000
f['one_tick_bps']=f.native_tick/f.close*10000
f['off_native_tick_grid']=abs(f.close/f.native_tick-np.round(f.close/f.native_tick)).gt(1e-5)
f.to_csv(OUT/'october_tick_illustrations.csv',index=False)
tick=dict(fill_tickets=len(f),off_native_tick_grid_tickets=int(f.off_native_tick_grid.sum()),
    weighted_half_tick_bps=float(np.average(f.half_tick_bps,weights=f.shares.abs()*f.reference_close)),
    note='half-tick is a mechanical quote-grid illustration, not an observed spread; price/share adjustment basis remains unverified')
(OUT/'tick_summary.json').write_text(json.dumps(tick,indent=2))
original=json.loads((study.REPO/'performance_attribution/sg_k3_ivweekly_top20_20261021/source_audit/source_files.json').read_text())
records=[]
for x in original:
    if x['path'] in ['README.md','GUIDE.md']:continue
    p=study.REPO/x['path'];sha=hashlib.sha256(p.read_bytes()).hexdigest()
    canonical=hashlib.sha256(study.input_bytes(p)).hexdigest()
    assert canonical==x.get('sha256_lf_normalized',x['sha256'])
    records.append(dict(path=x['path'],bytes=p.stat().st_size,sha256=sha,sha256_lf_normalized=canonical))
(HERE/'source_manifest.json').write_text(json.dumps(dict(source_main_commit=subprocess.check_output(['git','rev-parse','origin/main'],cwd=study.REPO,text=True).strip(),
    frozen_strategy_commit='abf1c66ffd82b03c6183ff3546a5eb30749db934',files=records),indent=2))
print(pd.DataFrame(rows).to_string(index=False));print(json.dumps(tick,indent=2))
