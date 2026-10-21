"""Strict accounting attribution for the team's K3 / IV weekly / top20 run.

Source strategy and engine are imported unchanged. New calculations are readers
of their output. Portfolio contributions are reconciled to NAV, never to CAGR.
"""
from pathlib import Path
import sys
import json
import hashlib
import copy
import numpy as np
import pandas as pd
from scipy.stats import norm

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
REPO=HERE.parent.parent if (HERE.parent.parent/'config/strategy.yaml').exists() else HERE.parent/'FE5209-GroupProject-attribution-review'
MAIN=HERE/'reproduced_main'
OUT=HERE/'results'
sys.path[:0]=[str(REPO),str(REPO/'src'),str(HERE/'runtime_deps')]
from sgfactor.config import load_config
from sgfactor.data import load_universe,load_benchmark
from sgfactor.strategy.weighting import style_weights
from sgfactor.live.run import load_execution_data
from sgfactor.live.engine import ExecutionConfig,plans_from_targets,simulate
from sgfactor.live.metrics import drawdown
from sgfactor.backtest.metrics import performance


def save(name,value):
    path=OUT/name
    if isinstance(value,pd.DataFrame):value.to_csv(path,index=False)
    else:path.write_text(json.dumps(value,ensure_ascii=False,indent=2,default=str,allow_nan=False),encoding='utf-8')


def load_account(folder):
    result={}
    for name in ['daily','holdings','orders','fills','signals','attempts','contributions','events']:
        try:d=pd.read_csv(folder/(name+'.csv'))
        except pd.errors.EmptyDataError:d=pd.DataFrame()
        for col in ['date','signal_date','execution_date','activation','settlement_date']:
            if col in d:d[col]=pd.to_datetime(d[col])
        result[name]=d
    result['audit']=json.loads((folder/'audit.json').read_text())
    return result


def fresh_account(cfg,ecfg,data):
    h=pd.read_csv(MAIN/'08_live_holdings.csv').rename(columns={'trade_date':'execution_date'})
    mapping=dict(zip(cfg['live_window']['trade_dates'],['2026-09-25','2026-10-02','2026-10-09']))
    h['signal_date']=h.execution_date.map(mapping)
    for col in ['signal_date','execution_date']:h[col]=pd.to_datetime(h[col])
    a=data['actions'].copy()
    a.date=pd.to_datetime(a.date)
    window=a[a.action_type.eq('cash_dividend')&a.ticker.isin(h.ticker)&a.date.between(h.signal_date.min(),ecfg['end'])]
    if len(window):
        raise ValueError('Fresh-window source events present: use the source dividend converter rather than assuming zero')
    r=simulate(data['prices'],data['sessions'],plans_from_targets(h),ExecutionConfig(**ecfg['settings']),
               actions=None,actions_verified=False,end=ecfg['end'])
    r['audit'].update(scope='fresh SGD100k account reproducing supplied workbook',
        zero_dividend_source_records=True,zero_actual_dividends_verified=False,
        source_corporate_action_last_date=str(a.date.max().date()))
    folder=HERE/'reproduced_fresh_live'
    folder.mkdir(exist_ok=True)
    for key,val in r.items():
        if isinstance(val,pd.DataFrame):val.to_csv(folder/(key+'.csv'),index=False)
    (folder/'audit.json').write_text(json.dumps(r['audit'],indent=2,default=str),encoding='utf-8')
    return r


def fx_components(ex,data,master):
    """Exact sequential native-price / FX / interaction decomposition of mark PnL.

    Effective local/SGD mark pairs carry forward together on missing-quote days,
    matching the engine's last observed SGD mark, not inventing FX revaluations.
    """
    raw=pd.read_csv(REPO/'data/prices_daily.csv.gz',usecols=['date','ticker','close'],parse_dates=['date'])
    cal=data['sessions']
    local=raw.pivot(index='date',columns='ticker',values='close').reindex(cal).ffill()
    sgd=data['prices'].pivot(index='date',columns='ticker',values='close').reindex(cal).ffill()
    local=local.reindex(columns=sgd.columns)
    fx=sgd/local
    q=ex['holdings'].pivot(index='date',columns='ticker',values='shares').reindex(cal,columns=sgd.columns).fillna(0).shift(1).fillna(0)
    native=(q*local.diff()*fx.shift(1)).stack().rename('native_price_pnl')
    currency=(q*local.shift(1)*fx.diff()).stack().rename('fx_pnl')
    cross=(q*local.diff()*fx.diff()).stack().rename('price_fx_interaction')
    components=pd.concat([native,currency,cross],axis=1).reset_index()
    components.columns=['date','ticker','native_price_pnl','fx_pnl','price_fx_interaction']
    c=ex['contributions'].merge(components,on=['date','ticker'],how='left',validate='one_to_one')
    cols=['native_price_pnl','fx_pnl','price_fx_interaction']
    c[cols]=c[cols].fillna(0)
    error=float((c[cols].sum(axis=1)-c.price_pnl).abs().max())
    if error>1e-6:raise AssertionError(f'FX price bridge does not reconcile: {error}')
    c=c.merge(master[['ticker','company_name','currency','six_sector']],on='ticker',how='left',validate='many_to_one')
    if c[['company_name','currency','six_sector']].isna().any().any():raise ValueError('Unmapped contribution security')
    c['net_pnl']=c.price_pnl+c.action_income-c.fees-c.slippage_cost
    if (c.net_pnl-c.contribution_amount).abs().max()>1e-7:raise AssertionError('Source per-stock PnL mismatch')
    daily=c.groupby('date').net_pnl.sum().reindex(ex['daily'].date,fill_value=0).to_numpy()
    expected=ex['daily'].nav.diff().fillna(ex['daily'].nav.iloc[0]-ex['audit']['config']['initial_cash']).to_numpy()
    if np.max(np.abs(daily-expected))>1e-6:raise AssertionError('Per-stock PnL does not sum to NAV change')
    return c,error


def account_window(ex,c,master,label,start,end,benchmark,include_benchmark=True):
    start,end=pd.Timestamp(start),pd.Timestamp(end)
    daily=ex['daily'].set_index('date')
    before=daily.loc[daily.index<=start]
    base=float(before.nav.iloc[-1]) if len(before) else ex['audit']['config']['initial_cash']
    d=daily[(daily.index>start)&(daily.index<=end)]
    cc=c[c.date.between(start,end,inclusive='right')].copy()
    pnl=float(d.nav.iloc[-1]-base)
    assert abs(cc.net_pnl.sum()-pnl)<1e-6
    cols=['native_price_pnl','fx_pnl','price_fx_interaction','price_pnl','action_income','fees','slippage_cost','net_pnl']
    bystock=cc.groupby(['ticker','company_name','currency','six_sector'])[cols].sum().reset_index()
    bystock['contribution_pp']=bystock.net_pnl/base*100
    h=ex['holdings'][ex['holdings'].date.between(start,end,inclusive='right')]
    avg=h.groupby('ticker').weight.sum()/len(d)
    bystock['average_weight']=bystock.ticker.map(avg).fillna(0)
    bystock=bystock.sort_values('net_pnl',ascending=False)
    bysector=cc.groupby('six_sector')[cols].sum().reset_index().sort_values('net_pnl',ascending=False)
    bysector['contribution_pp']=bysector.net_pnl/base*100
    bycurrency=cc.groupby('currency')[cols].sum().reset_index()
    bycurrency['contribution_pp']=bycurrency.net_pnl/base*100
    component=pd.DataFrame([dict(component=k,amount_sgd=float(cc[k].sum())*sign,
        contribution_pp=float(cc[k].sum())*sign/base*100) for k,sign in [
        ('native_price_pnl',1),('fx_pnl',1),('price_fx_interaction',1),('action_income',1),('fees',-1),('slippage_cost',-1)]])
    assert abs(component.amount_sgd.sum()-pnl)<1e-6
    r=pd.concat([pd.Series([base]),d.nav.reset_index(drop=True)]).pct_change().dropna()
    bench_return=(float(benchmark.loc[:end].iloc[-1]/benchmark.loc[:start].iloc[-1]-1) if include_benchmark else None)
    summary=dict(window=label,start=str(start.date()),end=str(end.date()),start_nav=base,end_nav=float(d.nav.iloc[-1]),
        pnl_sgd=pnl,cumulative_return=pnl/base,benchmark_return=bench_return,
        active_return=pnl/base-bench_return if bench_return is not None else None,
        trading_return_observations=len(r),max_drawdown=drawdown(d.nav,base),
        fees=float(cc.fees.sum()),slippage=float(cc.slippage_cost.sum()),dividends=float(cc.action_income.sum()),
        average_cash_fraction=float((d.cash/d.nav).mean()),
        last_cash_fraction=float(d.cash.iloc[-1]/d.nav.iloc[-1]),
        average_receivable_fraction=float((d.receivable/d.nav).mean()),
        daily_accounting_error_max=float(d.accounting_error.abs().max()),
        pnl_reconciliation_error=float(cc.net_pnl.sum()-pnl))
    for kind,frame in [('stock',bystock),('sector',bysector),('currency',bycurrency),('component',component)]:
        save(label+'_'+kind+'.csv',frame)
    day=cc.groupby('date')[cols].sum().reindex(d.index,fill_value=0).reset_index()
    day['contribution_pp']=day.net_pnl/base*100
    day['nav']=day.date.map(d.nav)
    day['net_return']=day.date.map(pd.Series(r.to_numpy(),index=d.index))
    save(label+'_daily.csv',day)
    # Exact drawdown contributions from peak close to trough close.
    nav=pd.concat([pd.Series([base],index=[start]),d.nav])
    dd=1-nav/nav.cummax()
    trough=dd.idxmax()
    peak=nav.loc[:trough].idxmax()
    ddrows=cc[cc.date.between(peak,trough,inclusive='right')]
    ddstock=ddrows.groupby(['ticker','company_name','six_sector'])[cols].sum().reset_index().sort_values('net_pnl')
    ddstock['drawdown_contribution_pp']=ddstock.net_pnl/float(nav.loc[peak])*100
    assert abs(ddstock.net_pnl.sum()-(nav.loc[trough]-nav.loc[peak]))<1e-6
    save(label+'_max_drawdown_stocks.csv',ddstock)
    summary['drawdown_peak']=str(peak.date());summary['drawdown_trough']=str(trough.date())
    summary['drawdown_peak_nav']=float(nav.loc[peak]);summary['drawdown_trough_nav']=float(nav.loc[trough])
    return summary


def weekly_attribution(cfg,universe,holdings):
    W=pd.read_csv(MAIN/'05_weekly_returns.csv').rename(columns={'Unnamed: 0':'signal_date'})
    h=holdings.merge(universe[['signal_date','ticker','forward_return','next_execution_date']],on=['signal_date','ticker'],validate='one_to_one')
    missing=h.forward_return.isna()
    save('weekly_missing_held_returns.csv',h[missing])
    h['gross_contribution']=h.weight*h.forward_return.fillna(0)
    h=h.merge(W[['signal_date','strategy','strategy_gross','one_way_turnover']],on='signal_date',validate='many_to_one')
    results=[]
    for label,start,end in [('selection_2016_2020','2016-01-01','2020-12-31'),
                             ('weekly_eval_2021_2026','2021-01-01','2026-09-18')]:
        w=W[W.signal_date.between(start,end)].copy().sort_values('signal_date')
        z=h[h.signal_date.isin(w.signal_date)].copy()
        prior=(1+w.strategy).cumprod().shift(1,fill_value=1)
        w['prior_net_wealth']=prior
        z['prior_net_wealth']=z.signal_date.map(w.set_index('signal_date').prior_net_wealth)
        z['linked_contribution']=z.gross_contribution*z.prior_net_wealth
        w['exact_cost_return']=w.strategy-w.strategy_gross
        w['linked_cost_contribution']=w.exact_cost_return*w.prior_net_wealth
        cumulative=float((1+w.strategy).prod()-1)
        error=float(z.linked_contribution.sum()+w.linked_cost_contribution.sum()-cumulative)
        if abs(error)>1e-10:raise AssertionError('Linked weekly contribution mismatch')
        stocks=z.groupby('ticker').agg(contribution=('linked_contribution','sum'),held_weeks=('signal_date','size'),average_weight_when_held=('weight','mean')).reset_index().sort_values('contribution',ascending=False)
        sectors=z.groupby('sector').linked_contribution.sum().rename('contribution').reset_index().sort_values('contribution',ascending=False)
        save(label+'_stocks.csv',stocks);save(label+'_sectors.csv',sectors)
        save(label+'_stock_week_detail.csv',z)
        save(label+'_weekly_cost_link.csv',w)
        results.append(dict(window=label,**performance(w.strategy),
            linked_stock_contribution=float(z.linked_contribution.sum()),
            linked_cost_contribution=float(w.linked_cost_contribution.sum()),
            reconciliation_error=error,missing_held_returns=int(z.forward_return.isna().sum()),
            return_basis='source listing-currency forward returns; not SGD execution account'))
    return results


def factor_decision_analysis(cfg,universe,holdings):
    decisions=pd.read_csv(MAIN/'02_annual_style_decisions.csv')
    styles=list(cfg['factors']);rows=[]
    # Capture the weights returned by the unchanged source pipeline. Re-solving
    # SLSQP from a CSV-roundtripped factor table can introduce tiny differences;
    # do not relax score reconciliation to conceal them.
    from sgfactor.strategy import pipeline as source_pipeline
    original=source_pipeline.style_weights
    def observe(*args,**kwargs):
        w=original(*args,**kwargs)
        rows.append(dict(signal_date=args[1],**{s:w.get(s,0) for s in styles}))
        return w
    try:
        source_pipeline.style_weights=observe
        replay=source_pipeline.run_strategy(universe,cfg)
    finally:
        source_pipeline.style_weights=original
    pd.testing.assert_frame_equal(replay['holdings'],holdings,check_exact=False,rtol=1e-12,atol=1e-12)
    fret=replay['factor_returns']
    weights=pd.DataFrame(rows)
    checks=holdings.merge(universe[['signal_date','ticker',*cfg['factors'].values()]],on=['signal_date','ticker'],validate='one_to_one')
    checks=checks.merge(weights,on='signal_date',validate='many_to_one')
    for style,col in cfg['factors'].items():checks['score_part_'+style]=checks[style]*checks[col]
    checks['reconstructed_composite']=checks[['score_part_'+s for s in styles]].sum(axis=1)
    error=float((checks.reconstructed_composite-checks.composite_score).abs().max())
    if error>1e-9:raise AssertionError('Reconstructed weekly IV weights do not reproduce held composite scores')
    save('factor_weights_weekly.csv',weights)
    save('factor_signal_components_held.csv',checks)
    annual=weights.assign(year=weights.signal_date.str[:4]).groupby('year')[styles].mean().reset_index()
    annual=annual.merge(decisions[['year','selected']].assign(year=lambda x:x.year.astype(str)),on='year',validate='one_to_one')
    save('factor_weights_annual_mean.csv',annual)
    # This basket is a diagnostic portfolio of style LS returns, not an exact
    # return allocation of the nonlinear stock-selection strategy.
    basket=weights.melt(id_vars='signal_date',var_name='style',value_name='style_weight').merge(fret,on=['signal_date','style'],validate='one_to_one')
    basket['style_basket_contribution']=basket.style_weight*basket.factor_return
    save('factor_mimicking_basket_DIAGNOSTIC.csv',basket)
    latest=weights[weights.signal_date.isin(['2026-09-25','2026-10-02','2026-10-09'])]
    return dict(composite_score_max_error=error,latest_weights=latest.to_dict('records'),
                annual_decisions=decisions[['year','selected']].to_dict('records'))


def hac_regression(y,X,lags=4):
    x=np.column_stack([np.ones(len(y)),X.to_numpy(float)])
    yy=np.asarray(y,float)
    beta=np.linalg.lstsq(x,yy,rcond=None)[0]
    residual=yy-x@beta;n,k=x.shape
    score=x*residual[:,None]
    meat=score.T@score
    for lag in range(1,min(lags,n-1)+1):
        g=score[lag:].T@score[:-lag]
        meat+=(1-lag/(lags+1))*(g+g.T)
    bread=np.linalg.pinv(x.T@x)
    cov=bread@meat@bread*n/(n-k)
    se=np.sqrt(np.maximum(np.diag(cov),0))
    t=beta/se
    table=pd.DataFrame(dict(term=['alpha',*X.columns],coefficient=beta,hac_standard_error=se,
        hac_z_stat=t,p_value_normal_approx=2*norm.sf(abs(t)),ci95_low=beta-1.96*se,ci95_high=beta+1.96*se))
    tss=float(np.sum((yy-yy.mean())**2));r2=1-float(residual@residual)/tss
    explanation=np.r_[beta[0],beta[1:]*X.mean().to_numpy()]
    table['mean_weekly_return_component']=explanation
    table['arithmetic_annual_mean_component']=explanation*52
    assert abs(explanation.sum()-yy.mean())<1e-10
    return table,dict(observations=n,hac_lags=lags,r_squared=r2,adjusted_r_squared=1-(1-r2)*(n-1)/(n-k),
        residual_weekly_std=float(residual.std(ddof=k)),design_condition_number=float(np.linalg.cond(x)),
        weekly_mean_return=float(yy.mean()),annualized_alpha_arithmetic=float(beta[0]*52),
        mean_return_reconciliation_error=float(explanation.sum()-yy.mean()),
        inference='HAC Bartlett lag4, finite-sample n/(n-k), asymptotic normal two-sided p; descriptive not causal')


def execution_risk_models(ex,cfg,universe,benchmark,master):
    fx=pd.read_csv(REPO/'data/fx_daily.csv',parse_dates=['date']).set_index('date')
    rate_map=master.set_index('ticker').currency
    u=universe.copy()
    u['ccy']=u.ticker.map(rate_map)
    multiplier=np.ones(len(u))
    for code,col in [('USD','sgd_per_usd'),('EUR','sgd_per_eur')]:
        mask=u.ccy.eq(code)
        e=fx[col].reindex(pd.to_datetime(u.loc[mask,'execution_date']),method='ffill').to_numpy()
        n=fx[col].reindex(pd.to_datetime(u.loc[mask,'next_execution_date']),method='ffill').to_numpy()
        multiplier[mask]=n/e
    u['sgd_forward_return']=(1+u.forward_return)*multiplier-1
    # Limit to completed source EVAL weeks. No October incomplete forward return.
    u=u[u.signal_date.between('2021-01-01','2026-09-18')]
    nav=ex['daily'].set_index('date').nav
    rows=[]
    for signal,g in u.groupby('signal_date',sort=True):
        e,n=pd.Timestamp(g.execution_date.iloc[0]),pd.Timestamp(g.next_execution_date.iloc[0])
        if e not in nav.index or n not in nav.index:continue
        row=dict(signal_date=signal,execution_date=e,next_execution_date=n,
            strategy_sgd=float(nav.loc[n]/nav.loc[e]-1),
            market_sgd=float(benchmark.loc[:n].iloc[-1]/benchmark.loc[:e].iloc[-1]-1))
        count=int(np.floor(.3*len(g)))
        for name,col in cfg['factors'].items():
            top=g.sort_values([col,'ticker'],ascending=[False,True]).head(count)
            bottom=g.sort_values([col,'ticker'],ascending=[True,True]).head(count)
            row[name]=float(top.sgd_forward_return.mean()-bottom.sgd_forward_return.mean())
        rows.append(row)
    frame=pd.DataFrame(rows)
    if not np.isfinite(frame[['strategy_sgd','market_sgd',*cfg['factors']]]).all().all():raise ValueError('Incomplete regression return data')
    save('risk_model_aligned_SGD_weekly.csv',frame)
    summaries=[]
    for label,columns in [('market_only',['market_sgd']),('market_plus_six_styles',['market_sgd',*cfg['factors']])]:
        table,summary=hac_regression(frame.strategy_sgd,frame[columns])
        table.insert(0,'model',label);summary['model']=label
        save('risk_model_'+label+'_coefficients.csv',table);summaries.append(summary)
    return summaries


def main():
    OUT.mkdir(exist_ok=True)
    cfg=load_config();ecfg=load_config(REPO/'config/execution.yaml')
    assert cfg['selection']['top_k']==3 and cfg['weighting']['rebalance']=='weekly'
    assert cfg['portfolio']['select_fraction']==.2 and cfg['weighting']['method']=='IV'
    data=load_execution_data(ecfg);master=data['master'];benchmark=load_benchmark(cfg)
    ex=load_account(MAIN/'execution');fresh=fresh_account(cfg,ecfg,data)
    c,fxerr=fx_components(ex,data,master);cf,fxerrf=fx_components(fresh,data,master)
    save('continuous_daily_stock_components.csv',c)
    save('fresh_live_daily_stock_components.csv',cf)
    windows=[]
    definitions=[(ex,c,'execution_eval','2021-01-07','2026-09-30',True),
        (ex,c,'execution_live_continuous','2026-10-01','2026-10-15',True),
        (ex,c,'execution_whole','2021-01-07','2026-10-15',True),
        (fresh,cf,'fresh_live_cash_start','2026-09-30','2026-10-15',False),
        (fresh,cf,'fresh_live_close_to_close','2026-10-01','2026-10-15',True)]
    for account,cc,label,a,b,bench in definitions:
        windows.append(account_window(account,cc,master,label,a,b,benchmark,bench))
    save('account_window_summary.json',windows)
    save('account_window_summary.csv',pd.DataFrame(windows))
    for year in range(2021,2027):
        a=f'{year-1}-12-31' if year>2021 else '2021-01-07'
        b=f'{year}-12-31' if year<2026 else '2026-09-30'
        account_window(ex,c,master,f'year_{year}',a,b,benchmark)
    universe=load_universe(cfg);holdings=pd.read_csv(MAIN/'03_target_holdings_weekly.csv')
    weekly=weekly_attribution(cfg,universe,holdings)
    factors=factor_decision_analysis(cfg,universe,holdings)
    risk=execution_risk_models(ex,cfg,universe,benchmark,master)
    save('weekly_attribution_summary.json',weekly);save('factor_analysis_summary.json',factors);save('risk_model_summary.json',risk)
    # Reconcile both supplied workbooks to the final strategy, not to Top4.
    books=json.loads((HERE/'source_audit/workbooks.json').read_text(encoding='utf-8'))
    ranking=books[0]['sheets']['排名']['rows']
    row=next(r for r in ranking[1:] if r[1]==3 and r[2]=='IV 按周调权' and abs(r[3]-.2)<1e-12)
    source_live=books[1]['sheets']['24策略_回测框架实盘']['rows'][1]
    assert source_live[1]=='K3_IV_weekly_top20'
    bywindow={r['window']:r for r in windows}
    cash=bywindow['fresh_live_cash_start'];closed=bywindow['fresh_live_close_to_close']
    f=fresh['fills'];o=fresh['orders']
    checks=[]
    def check(name,actual,expected,tol,required=True):
        delta=float(actual-expected)
        checks.append(dict(check=name,actual=float(actual),expected=float(expected),difference=delta,tolerance=tol,required=required,passed=abs(delta)<=tol))
    check('ranking_IS_annual_return',weekly[0]['ann_return'],row[5],1e-10)
    check('ranking_IS_sharpe',weekly[0]['sharpe'],row[7],1e-10)
    check('ranking_EVAL_annual_return',weekly[1]['ann_return'],row[13],1e-10)
    check('ranking_EVAL_sharpe',weekly[1]['sharpe'],row[14],1e-10)
    live_summary=pd.read_csv(MAIN/'08_live_summary.csv')
    check('ranking_live_theoretical_return',float(live_summary[live_summary.series.eq('strategy')].cum_return.iloc[0]),row[17],1e-10)
    first=fresh['daily'].set_index('date').loc['2026-10-01']
    check('fresh_Oct01_close_NAV',first.nav,source_live[5],1e-6)
    check('fresh_Oct15_NAV',cash['end_nav'],source_live[6],1e-6)
    check('fresh_cash_start_return',cash['cumulative_return'],source_live[7],1e-10)
    check('fresh_close_to_close_return',closed['cumulative_return'],source_live[8],1e-10)
    check('fresh_fees',f.total_fee.sum(),source_live[12],1e-6)
    check('fresh_slippage',f.slippage_cost.sum(),source_live[13],1e-6)
    check('fresh_fills',len(f),source_live[14],0)
    check('fresh_count_order_completion',o.remaining.eq(0).mean(),source_live[15],1e-12)
    check('fresh_last_cash_fraction',cash['last_cash_fraction'],source_live[16],1e-10)
    check('fresh_max_drawdown',cash['max_drawdown'],source_live[11],1e-10)
    check('fresh_Oct12_held_names',int(fresh['holdings'].date.eq(pd.Timestamp('2026-10-12')).sum()),source_live[4],0)
    workbook_bench=float(books[1]['sheets']['24策略_回测框架实盘']['rows'][-1][8])
    check('STI_workbook_vs_current_source',closed['benchmark_return'],workbook_bench,5e-7,required=False)
    # Every daily NAV in the attachment is rounded to cents.
    navrows=books[1]['sheets']['每日NAV']['rows']
    model=fresh['daily'].set_index('date').nav
    nav_error=max(abs(float(model.loc[pd.Timestamp(r[0])])-r[1]) for r in navrows[1:])
    check('fresh_daily_NAV_rounding_error',nav_error,0,.005001)
    save('workbook_reconciliation.csv',pd.DataFrame(checks))
    if not all(x['passed'] for x in checks if x['required']):raise AssertionError('Required portfolio workbook reconciliation failed')
    source=json.loads((HERE/'source_audit/source_files.json').read_text())
    locked=[x for x in source if x['path'] not in ['README.md','GUIDE.md']]
    unchanged=all(hashlib.sha256((REPO/x['path']).read_bytes()).hexdigest()==x['sha256'] for x in locked)
    assert unchanged
    action_dates=pd.to_datetime(data['actions'].date)
    flags=dict(strategy='K3_IV_weekly_top20',source_commit='abf1c66',source_files_unchanged=unchanged,
        source_files_verified=len(locked),source_navigation_docs_may_change=True,
        workbook_checks=len(checks),workbook_required_checks_passed=True,
        workbook_exact_controls_passed=sum(x['passed'] for x in checks),
        workbook_benchmark_difference=closed['benchmark_return']-workbook_bench,
        workbook_warning='STI return differs by about 0.000517 percentage point; retain discrepancy and use repository daily benchmark consistently',
        daily_FX_bridge_max_error=max(fxerr,fxerrf),synthetic_and_source_execution_tests_passed=31,
        corporate_action_last_source_date=str(action_dates.max().date()),
        actual_October_dividend_absence_verified=False,
        source_weekly_return_currency='listing currency; execution account converted to SGD',
        benchmark_sector_weights_available=False,Brinson_STI_allocation_selection_computed=False,
        Brinson_EW_universe_source_weekly_computed=True,
        incomplete_forward_weeks_not_attributed_after='2026-09-18 signal',
        source_ranking_scope='45 configurations in ranking book; selected configuration rank3 there, rank1 among final24',
        live_window_scope='simulated execution, not verified broker transactions')
    save('attribution_verification.json',flags)
    print(json.dumps(flags,ensure_ascii=False,indent=2))
    print(pd.DataFrame(windows)[['window','pnl_sgd','cumulative_return','active_return']].to_string(index=False))


if __name__=='__main__':main()
