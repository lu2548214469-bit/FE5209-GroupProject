"""Signal-time capacity, actual fills, tracking, stale marks and liquidation."""
from pathlib import Path
import sys,json,hashlib
import numpy as np
import pandas as pd
import run_study as study

HERE=Path(__file__).resolve().parent
OUT=HERE/'results'

def save(name,d):d.to_csv(OUT/name,index=False)
def load_case(name):
    r={'audit':json.loads((HERE/'scenarios'/name/'audit.json').read_text())}
    for key in ['daily','holdings','orders','fills','attempts','signals','events','contributions']:
        try:d=pd.read_csv(HERE/'scenarios'/name/(key+'.csv.gz'))
        except pd.errors.EmptyDataError:d=pd.DataFrame()
        for col in ['date','signal_date','activation','execution_date','settlement_date','sizing_price_date']:
            if col in d:d[col]=pd.to_datetime(d[col])
        r[key]=d
    return r

def detail(r,data):
    cal=data['sessions'];prices=data['prices'];master=data['master']
    p=prices.pivot(index='date',columns='ticker',values='close').reindex(cal)
    v=prices.pivot(index='date',columns='ticker',values='volume').reindex(cal)
    mark=p.ffill();value=p*v
    adv20=value.rolling(20,min_periods=20).mean();adv60=value.rolling(60,min_periods=60).mean()
    med60=value.rolling(60,min_periods=60).median()
    sigma=p.pct_change(fill_method=None).rolling(20,min_periods=20).std()
    o=r['orders'].copy();daily=r['daily'].set_index('date')
    held=r['holdings'].pivot(index='date',columns='ticker',values='shares').reindex(cal,columns=p.columns).fillna(0)
    sig=r['signals'].copy();o=o.merge(master,on='ticker',how='left',validate='many_to_one')
    def at(frame,dates,tickers):return np.array([frame.at[d,t] if d in frame.index and t in frame else np.nan for d,t in zip(dates,tickers)])
    o['signal_price']=at(mark,o.signal_date,o.ticker)
    o['signal_nav']=daily.nav.reindex(o.signal_date).to_numpy()
    o['requested_notional_signal']=o.original_requested.abs()*o.signal_price
    o['residual_notional_signal']=o.remaining.abs()*o.signal_price
    o['request_fraction_nav']=o.requested_notional_signal/o.signal_nav
    o['adv20_signal']=at(adv20,o.signal_date,o.ticker)
    o['adv60_signal']=at(adv60,o.signal_date,o.ticker)
    o['median60_signal']=at(med60,o.signal_date,o.ticker)
    o['activation_volume']=at(v,o.activation,o.ticker)
    o['activation_close']=at(p,o.activation,o.ticker)
    o['before_activation_shares']=at(held.shift(1),o.activation,o.ticker)
    o['order_type']=np.select([o.before_activation_shares.eq(0)&o.original_requested.gt(0),o.original_requested.lt(0)&o.original_requested.abs().ge(o.before_activation_shares)],['ENTRY','EXIT'],default='REBALANCE')
    o['first_session_zero_volume']=o.activation_volume.eq(0)
    o['first_session_missing_volume']=o.activation_volume.isna()
    o['first_session_volume_participation_required']=o.original_requested.abs()/o.activation_volume.replace(0,np.nan)
    o['lagged_signal_turnover_participation_required']=o.requested_notional_signal/o.adv20_signal.replace(0,np.nan)
    f=r['fills'].copy();f['reference_notional']=f.shares.abs()*f.reference_close
    f['ADV_participation']=f.reference_notional/f.lagged_adv
    f['volume_participation']=f.shares.abs()/f.source_volume
    f['delay_sessions']=cal.get_indexer(f.date)-f.order_id.map(o.set_index('order_id').activation.map(cal.get_loc)).to_numpy()
    f['shortfall_bps']=f.slippage_cost/f.reference_notional*10000
    f['total_friction_bps']=(f.total_fee+f.slippage_cost)/f.reference_notional*10000
    f['minimum_commission_binding']=f.commission.le(5+1e-8)
    ag=f.groupby('order_id').agg(first_fill=('date','min'),last_fill=('date','max'),fill_days=('date','nunique'),filled_shares=('shares',lambda x:abs(x).sum()),fees=('total_fee','sum'),shortfall=('slippage_cost','sum'))
    o=o.merge(ag,on='order_id',how='left',validate='one_to_one')
    o['first_fill_delay_sessions']=cal.get_indexer(o.first_fill)-cal.get_indexer(o.activation)
    o.loc[o.first_fill.isna(),'first_fill_delay_sessions']=np.nan
    o['last_fill_delay_sessions']=cal.get_indexer(o.last_fill)-cal.get_indexer(o.activation)
    o.loc[o.last_fill.isna(),'last_fill_delay_sessions']=np.nan
    o['filled_original_day']=o.remaining.eq(0)&o.last_fill.eq(o.activation)
    o['filled_later']=o.remaining.eq(0)&o.last_fill.gt(o.activation)
    save('baseline_order_detail.csv',o);save('baseline_fill_detail.csv',f)
    save('zero_or_missing_volume_initial_orders.csv',o[o.first_session_zero_volume|o.first_session_missing_volume])
    save('unfinished_orders.csv',o[o.remaining.ne(0)])
    reasons=r['attempts'].groupby('reason').agg(attempt_rows=('order_id','size'),affected_orders=('order_id','nunique')).reset_index()
    save('attempt_reasons.csv',reasons)
    save('order_type_summary.csv',o.groupby('order_type').agg(orders=('order_id','size'),requested_notional=('requested_notional_signal','sum'),residual_notional=('residual_notional_signal','sum'),fully_filled=('remaining',lambda x:x.eq(0).sum()),first_day_zero_volume=('first_session_zero_volume','sum')).reset_index())
    save('fill_cost_by_order_type.csv',f.merge(o[['order_id','order_type']],on='order_id').groupby('order_type').agg(fill_tickets=('order_id','size'),reference_notional=('reference_notional','sum'),commission=('commission','sum'),fees=('total_fee','sum'),shortfall=('slippage_cost','sum')).reset_index())
    # Board-lot loss exists before the order denominator; do not hide it in fill rate.
    sig['ideal_target_notional']=sig.signal_nav*.99*sig.target_weight
    sig['lot_rounded_target_notional']=sig.target_shares*sig.sizing_price
    sig['rounding_gap']=sig.ideal_target_notional-sig.lot_rounded_target_notional
    sig['rounding_gap_fraction_nav']=sig.rounding_gap/sig.signal_nav
    sig['fractional_lots_lost']=sig.rounding_gap/(100*sig.sizing_price)
    assert sig.rounding_gap.ge(-1e-6).all()
    save('board_lot_signal_stock.csv',sig)
    save('board_lot_by_signal.csv',sig.groupby('signal_date').agg(nav=('signal_nav','first'),rounding_gap=('rounding_gap','sum'),rounding_gap_fraction_nav=('rounding_gap_fraction_nav','sum'),names=('ticker','size')).reset_index())
    # Current 11-name board-lot revision cannot be extrapolated by price backwards.
    revised={'D05.SI','G07.SI','H02.SI','C07.SI','J36.SI','BN4.SI','O39.SI','K6S.SI','S68.SI','U11.SI','V03.SI'}
    save('announced_lot_rule_affected_signals.csv',sig[sig.execution_date.ge('2026-10-05')&sig.ticker.isin(revised)])
    zero=r['holdings'][r['holdings'].source_zero_volume].copy()
    stale=r['holdings'][r['holdings'].missing_mark_sessions.gt(0)].copy()
    save('held_zero_volume_days.csv',zero);save('stale_held_marks.csv',stale)
    # Whole-day turnover is not closing-auction volume or an order-book measure.
    capacities=[];weekly=[]
    for basis in ['adv20_signal','adv60_signal','median60_signal']:
        for participation in [.01,.05,.1]:
            for days in [1,3,5]:
                x=o.copy();valid=x[basis].notna()&x[basis].ge(0)
                x['nav_capacity']=participation*days*x[basis]/x.request_fraction_nav
                for date,g in x.groupby('signal_date'):
                    ok=bool(valid.loc[g.index].all());bottleneck=g.loc[g.nav_capacity.idxmin()] if ok else None
                    cap=float(g.nav_capacity.min()) if ok else np.nan
                    weekly.append(dict(signal_date=date,basis=basis,participation=participation,days=days,
                        capacity_nav=cap,status='OBSERVED_PROXY' if ok else 'MISSING_INPUT',
                        limiting_ticker=bottleneck.ticker if ok else '',baseline_signal_nav=g.signal_nav.iloc[0],
                        capacity_initial_scaled_base_path=cap/(g.signal_nav.iloc[0]/100000) if ok else np.nan))
    w=pd.DataFrame(weekly);save('signal_capacity_scenarios.csv',w)
    for keys,g in w.groupby(['basis','participation','days']):
        capacities.append(dict(zip(['basis','participation','days'],keys),valid_weeks=g.capacity_nav.notna().sum(),missing_weeks=g.capacity_nav.isna().sum(),
            min_capacity_nav=g.capacity_nav.min(),p05_capacity_nav=g.capacity_nav.quantile(.05),median_capacity_nav=g.capacity_nav.median(),
            baseline_weeks_within_capacity=g.baseline_signal_nav.le(g.capacity_nav).mean(),
            scaled_initial_min=g.capacity_initial_scaled_base_path.min()))
    save('capacity_summary.csv',pd.DataFrame(capacities))
    save('capacity_bottleneck_stock_frequency.csv',w[(w.basis=='adv20_signal')&(w.participation==.1)&(w.days==1)].groupby('limiting_ticker').agg(weeks=('signal_date','size'),minimum_nav_capacity=('capacity_nav','min')).reset_index().sort_values('weeks',ascending=False))
    # Target distance combines drift, rounding, cash, receivables and partial fills.
    t=study.CTX['targets'].pivot(index='execution_date',columns='ticker',values='weight').fillna(0)
    t=t.reindex(daily.index,method='ffill').fillna(0)*.99
    actual=r['holdings'].pivot(index='date',columns='ticker',values='weight').reindex(daily.index).fillna(0)
    columns=t.columns.union(actual.columns);t=t.reindex(columns=columns,fill_value=0);actual=actual.reindex(columns=columns,fill_value=0)
    distance=(actual-t).abs().sum(axis=1)+((1-actual.sum(axis=1))-(1-t.sum(axis=1))).abs()
    tracking=pd.DataFrame(dict(date=daily.index,l1_exposure_distance=distance.to_numpy(),half_l1=distance.to_numpy()/2,
        cash_fraction=daily.cash/daily.nav,receivable_fraction=daily.receivable/daily.nav))
    save('daily_target_distance.csv',tracking)
    # Frozen hypothetical full-position sale, using only liquidity known at that date.
    liq=[]
    sample=set(sig.signal_date)|{pd.Timestamp('2026-09-30'),pd.Timestamp('2026-10-15')}
    for aum_case in ['capital_100000','capital_1000000','fresh_capital_100000','fresh_capital_1000000']:
        cr=r if aum_case=='capital_100000' else load_case(aum_case)
        h=cr['holdings'];h=h[h.date.isin(sample)].copy()
        h['adv20']=at(adv20,h.date,h.ticker);h['base_shares_per_day']=.1*h.adv20/h.mark
        for multiplier in [1.,.5]:
            rate=np.floor(h.base_shares_per_day*multiplier/100)*100
            z=h.copy();z['scenario']=aum_case;z['volume_multiplier']=multiplier
            z['daily_share_capacity']=rate
            z['liquidation_days_proxy']=np.where(rate.gt(0),np.ceil(z.shares/rate),np.inf)
            z['zero_one_lot_capacity']=rate.eq(0)
            liq.append(z)
    liq=pd.concat(liq,ignore_index=True);save('liquidation_full_position_detail.csv',liq)
    q=liq.groupby(['scenario','date','volume_multiplier']).agg(max_days=('liquidation_days_proxy','max'),blocked_names=('zero_one_lot_capacity','sum'),
        names=('ticker','size'),weight_need_over5days=('weight',lambda x:float(x[liq.loc[x.index,'liquidation_days_proxy'].gt(5)].sum()))).reset_index()
    save('liquidation_by_snapshot.csv',q)
    summary=dict(orders=len(o),fills=len(f),signals=o.signal_date.nunique(),zero_volume_initial_orders=int(o.first_session_zero_volume.sum()),
        zero_volume_entry_orders=int(o[o.order_type.eq('ENTRY')].first_session_zero_volume.sum()),
        missing_volume_initial_orders=int(o.first_session_missing_volume.sum()),
        fully_same_day=int(o.filled_original_day.sum()),fully_later=int(o.filled_later.sum()),unfinished=int(o.remaining.ne(0).sum()),
        fees=float(f.total_fee.sum()),slippage=float(f.slippage_cost.sum()),
        min_commission_fraction=float(f.minimum_commission_binding.mean()),
        delayed_ticket_fraction=float(f.delay_sessions.gt(0).mean()),
        max_fill_adv_participation=float(f.ADV_participation.max()),max_fill_day_volume_participation=float(f.volume_participation.max()),
        stock_days_zero_volume=len(zero),stock_days_stale=len(stale),
        mean_rounding_gap_fraction=float(sig.groupby('signal_date').rounding_gap_fraction_nav.sum().mean()),
        max_rounding_gap_fraction=float(sig.groupby('signal_date').rounding_gap_fraction_nav.sum().max()),
        mean_half_l1_target_distance=float(tracking.half_l1.mean()),
        october_announced_lot_rule_affected_targets=int(len(sig[sig.execution_date.ge('2026-10-05')&sig.ticker.isin(revised)])),
        signal_time_liquidity_missing=int(o.adv20_signal.isna().sum()))
    (OUT/'diagnostics_summary.json').write_text(json.dumps(summary,indent=2,allow_nan=False))
    print(json.dumps(summary,indent=2))

def main():
    study.initialise();r=load_case('capital_100000');detail(r,study.CTX['data'])

if __name__=='__main__':main()
