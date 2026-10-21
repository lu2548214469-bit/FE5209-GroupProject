"""Observed future-day sell-down scenario, separate from strategy performance.

Starts with actual shares. No new purchases. Tracks net sale proceeds and T+2,
not total portfolio NAV; existing cash/dividend receivables are not sale proceeds.
"""
from pathlib import Path
import json,math
import numpy as np
import pandas as pd
import run_study as study
from diagnostics import load_case

HERE=Path(__file__).resolve().parent;OUT=HERE/'results'

def replay(r,date,volume_multiplier,data,days=10):
    cal=data['sessions'];date=pd.Timestamp(date)
    h=r['holdings'][r['holdings'].date.eq(date)].set_index('ticker')
    if h.empty:raise ValueError('No actual starting shares')
    p=data['prices'].pivot(index='date',columns='ticker',values='close').reindex(cal)
    v=data['prices'].pivot(index='date',columns='ticker',values='volume').reindex(cal)*volume_multiplier
    a=(p*v).rolling(20,min_periods=20).mean().shift(1)
    observed=cal[(cal>date)&(cal<=p.dropna(how='all').index[-1])][:days]
    q=h.shares.astype(int).to_dict();initial_value=float((h.shares*h.mark).sum())
    initial_shares=sum(q.values());receipts=[];cash=0.;cost=0.;records=[];fills=[]
    buys=r['fills'];buys=buys[buys.shares.gt(0)&buys.date.le(date)&buys.settlement_date.gt(date)]
    blocked=[dict(ticker=x.ticker,shares=int(x.shares),settlement=x.settlement_date) for x in buys.itertuples()]
    first_full=None
    for step,d in enumerate(observed,1):
        for item in list(receipts):
            if item['due']<=d:cash+=item['amount'];receipts.remove(item)
        for ticker in sorted(q):
            if q[ticker]<=0:continue
            price=p.at[d,ticker];vol=v.at[d,ticker];adv=a.at[d,ticker]
            if not np.isfinite([price,vol,adv]).all() or vol<=0 or adv<=0:continue
            un=sum(b['shares'] for b in blocked if b['ticker']==ticker and b['settlement']>d)
            available=max(0,q[ticker]-un)
            shares=int(min(available,math.floor(min(.1*vol,.1*adv/price)/100)*100))
            if shares<=0:continue
            px=price*(1-.001);notional=shares*px;fee=max(5.,notional*.0005)+notional*.0004
            if notional<fee:continue
            q[ticker]-=shares;net=notional-fee;due=cal[cal.get_loc(d)+2]
            receipts.append(dict(due=due,amount=net));cost+=fee+shares*(price-px)
            fills.append(dict(date=d,ticker=ticker,shares=shares,reference_price=price,price=px,fee=fee,net_proceeds=net,settlement_date=due,source_volume=vol,lagged_adv=adv))
        remaining=sum(q.values())
        if remaining==0 and first_full is None:first_full=step
        # Use the date's carried mark for an exposure diagnostic, not a return claim.
        marks=p.loc[:d].ffill().loc[d]
        remaining_value=sum(q[t]*marks[t] for t in q)
        records.append(dict(date=d,trade_session=step,remaining_names=sum(x>0 for x in q.values()),
            remaining_shares=remaining,remaining_market_value=remaining_value,
            settled_sale_proceeds=cash,unsettled_sale_proceeds=sum(x['amount'] for x in receipts)))
    last=records[-1]
    summary=dict(snapshot=str(date.date()),volume_multiplier=volume_multiplier,
        horizon_sessions=len(observed),initial_market_value=initial_value,
        remaining_names=last['remaining_names'],remaining_market_value=last['remaining_market_value'],
        residual_value_fraction_initial_market_value=last['remaining_market_value']/initial_value,
        fully_liquidated_session=first_full,
        sale_proceeds_settled=last['settled_sale_proceeds'],sale_proceeds_receivable=last['unsettled_sale_proceeds'],
        fees_and_shortfall=cost,
        scope='observed-close sale/settlement proxy, not total-return NAV; no old cash/receivables, dividends, or price impact')
    assert all(x>=0 for x in q.values())
    if fills:
        f=pd.DataFrame(fills)
        assert (f.shares<=f.source_volume*.1+1e-6).all()
        assert (f.shares*f.reference_price<=f.lagged_adv*.1+1e-6).all()
        assert abs(f.net_proceeds.sum()-cash-sum(x['amount'] for x in receipts))<1e-6
    return summary,pd.DataFrame(records),pd.DataFrame(fills)

def main():
    study.initialise();q=pd.read_csv(OUT/'liquidation_by_snapshot.csv')
    dates={pd.Timestamp('2026-09-30')}
    for name in ['capital_100000','capital_1000000']:
        a=q[q.scenario.eq(name)&q.volume_multiplier.eq(1)&q.date.le('2026-09-30')]
        dates.add(pd.Timestamp(a.sort_values(['max_days','date'],ascending=[False,True]).iloc[0].date))
    summaries=[];records=[];fills=[]
    for name in ['capital_100000','capital_1000000']:
        r=load_case(name)
        for date in sorted(dates):
            for multiplier in [1.,.5]:
                s,d,f=replay(r,date,multiplier,study.CTX['data']);s['account']=name
                for df in [d,f]:
                    df['account']=name;df['snapshot']=str(date.date());df['volume_multiplier']=multiplier
                summaries.append(s);records.append(d);fills.append(f)
    pd.DataFrame(summaries).to_csv(OUT/'exit_replay_summary.csv',index=False)
    pd.concat(records).to_csv(OUT/'exit_replay_daily.csv',index=False)
    pd.concat(fills).to_csv(OUT/'exit_replay_fills.csv',index=False)
    print(pd.DataFrame(summaries)[['account','snapshot','volume_multiplier','fully_liquidated_session','remaining_names','residual_value_fraction_initial_market_value']].to_string(index=False))

if __name__=='__main__':main()
