"""Supplement: same buffer rule receives actual held names, not paper targets.

The first target is fixed to the formal run to isolate subsequent state feedback.
This does not replace the official target-replay results or select a new model.
"""
import json
import pandas as pd
import run_study as study
from sgfactor.data import load_universe
from sgfactor.strategy.pipeline import run_strategy
from sgfactor.strategy.portfolio import _one_week
from sgfactor.live.engine import simulate,plans_from_targets,ExecutionConfig
from sgfactor.live.dividends import prepare_source_dividends

def main():
    study.initialise();ctx=study.CTX;cfg=ctx['cfg'];data=ctx['data']
    strategy=run_strategy(load_universe(cfg),cfg)
    expected=pd.read_csv(study.REFERENCE/'03_target_holdings_weekly.csv')
    assert strategy['holdings'][['signal_date','ticker']].astype(str).reset_index(drop=True).equals(expected[['signal_date','ticker']].astype(str).reset_index(drop=True))
    blocks={pd.Timestamp(d):g for d,g in strategy['composite'].groupby('signal_date')}
    source=ctx['targets'];first=source.signal_date.min()
    all_names=pd.DataFrame(dict(ticker=strategy['composite'].ticker.unique(),signal_date=first))
    actions=prepare_source_dividends(data['actions'],all_names,data['sessions'],ctx['ecfg']['end'])
    selected=[];outrows=[]
    for aum in [100000,1000000]:
        log=[]
        def selector(date,actual_held):
            if date==first:
                weights=source[source.signal_date.eq(date)].set_index('ticker').weight.to_dict()
            else:
                pcfg=cfg['portfolio']
                h=_one_week(blocks[date],actual_held,pcfg['select_fraction'],pcfg['exit_fraction'],pcfg['sector_cap'],True)
                weights=h.set_index('ticker').weight.to_dict()
            old=set(source[source.signal_date.eq(date)].ticker)
            log.append(dict(signal_date=str(date.date()),actual_held_count=len(actual_held),target_names=len(weights),symmetric_difference_names=len(old^set(weights))))
            return weights
        settings={**ctx['ecfg']['settings'],'initial_cash':aum}
        r=simulate(data['prices'],data['sessions'],plans_from_targets(source),ExecutionConfig(**settings),selector=selector,actions=actions,actions_verified=False,end=ctx['ecfg']['end'])
        name='feedback_actual_holdings_'+str(aum);folder=study.HERE/'scenarios'/name;folder.mkdir(exist_ok=True)
        case=dict(name=name,family='feedback_diagnostic',settings={'initial_cash':aum})
        r['audit']['description']='Same rule, first target fixed, subsequent buffer uses actual held names; formal result not replaced'
        for key in ['daily','holdings','orders','fills','attempts','signals','events','contributions']:
            r[key].to_csv(folder/(key+'.csv.gz'),index=False,compression='gzip')
        (folder/'audit.json').write_text(json.dumps(r['audit'],indent=2))
        row=study.measures(r,case,settings,pd.Timestamp('2021-01-07'),pd.Timestamp('2026-09-30'),aum,'EVAL')
        row['signals_with_different_target_set']=sum(x['symmetric_difference_names']>0 for x in log)
        row['signals']=len(log);outrows.append(row)
        selected.extend([dict(initial_cash=aum,**x) for x in log])
    pd.DataFrame(outrows).to_csv(study.HERE/'results/feedback_summary.csv',index=False)
    pd.DataFrame(selected).to_csv(study.HERE/'results/feedback_target_differences.csv',index=False)
    print(pd.DataFrame(outrows)[['initial_cash','cagr','requested_value_completion','signals_with_different_target_set','signals']].to_string(index=False))

if __name__=='__main__':main()
