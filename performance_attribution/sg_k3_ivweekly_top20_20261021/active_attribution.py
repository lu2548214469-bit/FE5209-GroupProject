"""Exact relative-wealth attribution to STI using actual beginning exposures.

This subtracts the broad-market return from each actual asset exposure and
includes noninvested cash/receivables. It is not sector Brinson attribution;
no sector benchmark weights or sector index returns are fabricated.
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
OUT=HERE/'results'
REPO=HERE.parent.parent if (HERE.parent.parent/'config/strategy.yaml').exists() else HERE.parent/'FE5209-GroupProject-attribution-review'


def main():
    benchmark=pd.read_csv(REPO/'data/sti_total_return_daily.csv',parse_dates=['date']).set_index('date').sti_tr_level
    master=pd.read_csv(REPO/'data/security_master.csv')
    windows=json.loads((OUT/'account_window_summary.json').read_text())
    summaries=[]
    for w in windows:
        if w['benchmark_return'] is None:continue
        fresh=w['window'].startswith('fresh_')
        folder=HERE/'reproduced_fresh_live' if fresh else HERE/'reproduced_main/execution'
        daily=pd.read_csv(folder/'daily.csv',parse_dates=['date']).set_index('date')
        held=pd.read_csv(folder/'holdings.csv',parse_dates=['date'])
        c=pd.read_csv(OUT/('fresh_live_daily_stock_components.csv' if fresh else 'continuous_daily_stock_components.csv'),parse_dates=['date'])
        a,b=pd.Timestamp(w['start']),pd.Timestamp(w['end'])
        days=daily.index[(daily.index>a)&(daily.index<=b)]
        next_day=dict(zip(daily.index[:-1],daily.index[1:]))
        prior=held[['date','ticker','weight']].copy()
        prior['date']=prior.date.map(next_day)
        prior=prior.dropna().rename(columns={'weight':'begin_weight'})
        z=c[['date','ticker','net_pnl','fees','slippage_cost','price_pnl','action_income']].merge(prior,on=['date','ticker'],how='outer',validate='one_to_one')
        z=z[z.date.isin(days)].copy()
        for col in ['net_pnl','fees','slippage_cost','price_pnl','action_income','begin_weight']:z[col]=z[col].fillna(0)
        prev_nav=daily.nav.shift().fillna(100000.)
        p_prev=prev_nav.reindex(days)
        b_levels=benchmark.reindex(pd.DatetimeIndex([a]).append(days),method='ffill')
        rb=b_levels.pct_change().iloc[1:]
        future=b_levels.iloc[-1]/b_levels.iloc[1:]
        link=(p_prev/w['start_nav'])*future
        z['daily_net_return_component']=z.net_pnl/z.date.map(prev_nav)
        z['market_hurdle']=z.begin_weight*z.date.map(rb)
        z['daily_active_effect']=z.daily_net_return_component-z.market_hurdle
        z['linked_active_contribution']=z.daily_active_effect*z.date.map(link)
        prev_noninvested=(1-daily.market_value.shift()/prev_nav).fillna(1).reindex(days)
        cash=-prev_noninvested*rb*link
        stock=z.groupby('ticker').linked_active_contribution.sum().reset_index().merge(master,on='ticker',validate='one_to_one')
        stock['active_contribution_pp']=stock.linked_active_contribution*100
        stock=stock.sort_values('active_contribution_pp',ascending=False)
        sector=stock.groupby('six_sector').active_contribution_pp.sum().reset_index()
        sector=pd.concat([sector,pd.DataFrame([dict(six_sector='__CASH_AND_RECEIVABLES__',active_contribution_pp=float(cash.sum()*100))])])
        expected=w['cumulative_return']-w['benchmark_return']
        total=float(z.linked_active_contribution.sum()+cash.sum())
        assert abs(total-expected)<1e-9
        # Per-day active-effect identity is independently checked before linking.
        active=z.groupby('date').daily_active_effect.sum().reindex(days)-prev_noninvested*rb
        realized=daily.net_return.reindex(days)-rb
        assert float((active-realized).abs().max())<1e-9
        stock.to_csv(OUT/(w['window']+'_active_STI_stocks.csv'),index=False)
        sector.to_csv(OUT/(w['window']+'_active_STI_sectors_and_cash.csv'),index=False)
        z.to_csv(OUT/(w['window']+'_active_STI_daily_detail.csv'),index=False)
        summaries.append(dict(window=w['window'],active_cumulative_return=expected,
            linked_stock_active_effect=float(z.linked_active_contribution.sum()),
            cash_and_receivable_effect=float(cash.sum()),reconciliation_error=total-expected,
            method='actual beginning exposures versus broad STI return; benchmark-compounded active-wealth linking; not sector Brinson'))
    pd.DataFrame(summaries).to_csv(OUT/'active_STI_summary.csv',index=False)
    print(pd.DataFrame(summaries)[['window','active_cumulative_return','linked_stock_active_effect','cash_and_receivable_effect']].to_string(index=False))


if __name__=='__main__':main()
