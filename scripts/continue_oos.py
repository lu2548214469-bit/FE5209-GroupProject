"""Continue the frozen account with a complete updated data directory.

Original strategy and execution YAML files remain unchanged. This entry point
adds the next scheduled rebalance only when its actual weekly signal exists.
"""
from pathlib import Path
from datetime import timedelta
import argparse
import json
import sys
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from sgfactor.config import load_config
from sgfactor.data import load_universe, load_benchmark
from sgfactor.strategy import run_strategy
from sgfactor.backtest.live_window import live_schedule
from sgfactor.live import run_execution
from sgfactor.live.oos_report import report_window, save_report
from run_backtest import execution_targets


def prepare_config(data_dir: Path, end: str):
    if not '2026-10-01' <= end <= '2026-10-20':
        raise ValueError('This course continuation supports October 1 through October 20, 2026')
    cfg=load_config();ecfg=load_config(ROOT/'config/execution.yaml')
    cfg['data']['universe']=str((data_dir/'sg_universe_weekly.csv.gz').resolve())
    cfg['data']['benchmark']=str((data_dir/'sti_total_return_daily.csv').resolve())
    cfg['live_window']['prices']=str((data_dir/'prices_daily.csv.gz').resolve())
    cfg['live_window']['end']=end
    # Keep the group's special first course trade on October 1, then Mondays.
    scheduled=['2026-10-01','2026-10-05','2026-10-12','2026-10-19']
    cfg['live_window']['trade_dates']=[d for d in scheduled if d<=end]
    cfg['periods']['live'][1]='2026-10-16' if end>='2026-10-19' else '2026-10-09'
    for key,value in ecfg['data'].items():
        ecfg['data'][key]=str((data_dir/Path(value).name).resolve())
    ecfg['end']=end
    future=[];day=pd.Timestamp(end).date()
    while len(future)<2:
        day+=timedelta(days=1)
        if day.weekday()<5:future.append(day.isoformat())
    ecfg['settlement_calendar_extension']=future
    return cfg,ecfg


def check_inputs(data_dir: Path, end: str) -> dict:
    cfg,ecfg=prepare_config(data_dir,end)
    u=load_universe(cfg);b=load_benchmark(cfg)
    sessions=pd.DatetimeIndex(pd.read_csv(ecfg['data']['sessions'],parse_dates=['date']).date)
    prices=pd.read_csv(ecfg['data']['prices'],usecols=['date','ticker','close','volume'])
    fx=pd.read_csv(ecfg['data']['fx'])
    actions=pd.read_csv(ecfg['data']['corporate_actions'])
    errors=[]
    if prices.date.max()<end:errors.append(f"Daily prices end at {prices.date.max()}, before {end}")
    if pd.Timestamp(end) not in sessions:errors.append(f"No observed trading session for {end}")
    for date in ['2026-10-16','2026-10-19','2026-10-20']:
        if date>end:continue
        if pd.Timestamp(date) not in sessions:errors.append(f"Required continuation session {date} is absent")
        g=prices[prices.date.eq(date)]
        if g.volume.gt(0).sum()<50:errors.append(f"Insufficient observed market coverage at {date}")
    required_days=sessions[(sessions>='2026-10-01')&(sessions<=end)]
    missing=required_days.difference(b.dropna().index)
    if len(missing):errors.append('STI total-return levels missing on '+', '.join(missing.strftime('%Y-%m-%d')))
    if pd.Timestamp(end) not in b.dropna().index:errors.append(f"No exact STI total-return close for {end}; forward fill is prohibited")
    expected_signals=[s for s,t in [('2026-09-25','2026-10-01'),('2026-10-02','2026-10-05'),
                                   ('2026-10-09','2026-10-12'),('2026-10-16','2026-10-19')] if t<=end]
    available=set(u.signal_date)
    for signal in expected_signals:
        if signal not in available:errors.append(f"Weekly factor signal {signal} is missing; an older signal cannot replace it")
        else:
            g=u[u.signal_date.eq(signal)]
            if not np.isfinite(g[list(cfg['factors'].values())]).all().all():errors.append(f"Invalid factor values at {signal}")
            expected_trade={'2026-09-25':'2026-10-01','2026-10-02':'2026-10-05',
                            '2026-10-09':'2026-10-12','2026-10-16':'2026-10-19'}[signal]
            # September25's source weekly execution was September28. Its
            # special October1 course execution is assigned separately.
            if signal!='2026-09-25' and not g.execution_date.eq(expected_trade).all():
                errors.append(f"Wrong execution date for {signal}: expected {expected_trade}")
    if fx.date.max()<end:errors.append(f"FX ends at {fx.date.max()}, before {end}")
    for date in ['2026-10-16','2026-10-19','2026-10-20']:
        if date>end:continue
        g=fx[fx.date.eq(date)]
        if len(g)!=1 or not np.isfinite(g[['sgd_per_usd','sgd_per_eur']]).all().all() or not g[['sgd_per_usd','sgd_per_eur']].gt(0).all().all():
            errors.append(f"Exact positive USD/EUR FX observations missing for {date}")
    if end>='2026-10-12':
        event=actions[actions.date.eq('2026-10-12') & actions.ticker.eq('P9D.SI') & actions.action_type.eq('cash_dividend')]
        if event.empty or not event.dividend.gt(0).any():
            errors.append('Known Civmec 2026-10-12 dividend missing; original source ends on 2026-09-15')
    return dict(requested_end=end,latest_daily_price=prices.date.max(),latest_weekly_signal=u.signal_date.max(),
                latest_STI_TR=str(b.index.max().date()),latest_fx=fx.date.max(),passed=not errors,errors=errors)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--data-dir',type=Path,default=ROOT/'data')
    ap.add_argument('--end',default='2026-10-20')
    ap.add_argument('--test-start',default='2026-10-01')
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--check-only',action='store_true')
    args=ap.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    ready=check_inputs(args.data_dir,args.end)
    (args.out/'DATA_READINESS.json').write_text(json.dumps(ready,indent=2),encoding='utf-8')
    print(json.dumps(ready,indent=2),flush=True)
    if not ready['passed']:raise SystemExit(2)
    if args.check_only:return
    cfg,ecfg=prepare_config(args.data_dir,args.end)
    universe=load_universe(cfg);benchmark=load_benchmark(cfg)
    res=run_strategy(universe,cfg)
    schedule=live_schedule(universe.signal_date.unique(),cfg)
    # Require exactly the Friday source signal for each ordinary Monday trade.
    for signal,trade in schedule:
        if trade!='2026-10-01' and pd.Timestamp(signal).date()!=pd.Timestamp(trade).date()-timedelta(days=3):
            raise ValueError(f"Missing current Friday signal for {trade}: got {signal}")
    parts=[]
    for signal,trade in schedule:
        h=res['holdings'][res['holdings'].signal_date.eq(signal)][['ticker','weight']].copy()
        h['trade_date']=trade;parts.append(h)
    live={'schedule':schedule,'holdings':pd.concat(parts,ignore_index=True)}
    targets=execution_targets(res,live,cfg)
    ex=run_execution(targets,ecfg,ecfg['eval_end'],cfg['live_window']['trade_dates'][0],benchmark)
    folder=args.out/'execution';folder.mkdir(exist_ok=True)
    for key,value in ex.items():
        if isinstance(value,pd.DataFrame):value.to_csv(folder/f'{key}.csv',index=False)
    (folder/'audit.json').write_text(json.dumps(ex['audit'],indent=2,default=str),encoding='utf-8')
    (args.out/'EXECUTION_SUMMARY_LEGACY_WINDOWS.json').write_text(json.dumps(ex['summary'],indent=2,default=str),encoding='utf-8')
    save_report(report_window(ex,args.test_start,args.end,benchmark),args.out/'course_oos')
    res['decisions'].to_csv(args.out/'annual_decisions.csv',index=False)
    targets.to_csv(args.out/'execution_targets.csv',index=False)
    (args.out/'RUN_CONFIG.json').write_text(json.dumps(dict(strategy=cfg,execution=ecfg),indent=2),encoding='utf-8')


if __name__=='__main__':main()
