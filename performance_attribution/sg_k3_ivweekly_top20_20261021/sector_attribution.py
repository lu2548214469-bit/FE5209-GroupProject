"""Sector Brinson-Fachler relative to the supplied EW universe, NOT to STI.

Uses the source weekly local-return convention, not the SGD execution account.
Active effects link by P_wealth_before * B_wealth_after_week_to_end so that they
sum exactly to terminal strategy wealth minus benchmark wealth.
"""
from pathlib import Path
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
REPO=HERE.parent.parent if (HERE.parent.parent/'config/strategy.yaml').exists() else HERE.parent/'FE5209-GroupProject-attribution-review'
MAIN=HERE/'reproduced_main'
OUT=HERE/'results'


def effects(wp,wb,rp,rb):
    market=float(np.dot(wb,rb))
    allocation=(wp-wb)*(rb-market)
    selection=wb*(rp-rb)
    interaction=(wp-wb)*(rp-rb)
    assert abs(np.sum(allocation+selection+interaction)-(np.dot(wp,rp)-market))<1e-11
    return allocation,selection,interaction


def main():
    universe=pd.read_csv(REPO/'data/sg_universe_weekly.csv.gz')
    h=pd.read_csv(MAIN/'03_target_holdings_weekly.csv').merge(universe[['signal_date','ticker','forward_return']],on=['signal_date','ticker'],validate='one_to_one')
    W=pd.read_csv(MAIN/'05_weekly_returns.csv').rename(columns={'Unnamed: 0':'signal_date'})
    summaries=[]
    for label,start,end in [('selection_2016_2020','2016-01-01','2020-12-31'),('weekly_eval_2021_2026','2021-01-01','2026-09-18')]:
        w=W[W.signal_date.between(start,end)].copy().sort_values('signal_date')
        records=[]
        for row in w.itertuples():
            u=universe[universe.signal_date.eq(row.signal_date)]
            p=h[h.signal_date.eq(row.signal_date)]
            sectors=sorted(set(u.sector)|set(p.sector))+['__CASH__']
            wp=[];wb=[];rp=[];rb=[];empty=[]
            for sector in sectors:
                if sector=='__CASH__':
                    wp.append(max(0.,1-p.weight.sum()));wb.append(0.);rp.append(0.);rb.append(0.);empty.append(False)
                else:
                    up=u[u.sector.eq(sector)];pp=p[p.sector.eq(sector)]
                    bw=len(up)/len(u);pw=float(pp.weight.sum());br=float(up.forward_return.mean())
                    pr=float(np.dot(pp.weight,pp.forward_return.fillna(0))/pw) if pw else br
                    wp.append(pw);wb.append(bw);rp.append(pr);rb.append(br);empty.append(pw==0)
            wp,wb,rp,rb=map(np.asarray,[wp,wb,rp,rb])
            A,S,I=effects(wp,wb,rp,rb)
            assert abs(float(wp@rp)-row.strategy_gross)<1e-10
            assert abs(float(wb@rb)-row.EW_universe)<1e-10
            for j,sector in enumerate(sectors):
                records.append(dict(signal_date=row.signal_date,sector=sector,portfolio_weight=wp[j],benchmark_weight=wb[j],
                    portfolio_sector_return=rp[j],benchmark_sector_return=rb[j],no_portfolio_holdings_neutral_return=empty[j],
                    allocation=A[j],selection=S[j],interaction=I[j]))
            records.append(dict(signal_date=row.signal_date,sector='__COST__',portfolio_weight=0.,benchmark_weight=0.,
                portfolio_sector_return=0.,benchmark_sector_return=0.,no_portfolio_holdings_neutral_return=False,
                allocation=0.,selection=0.,interaction=0.,cost=row.strategy-row.strategy_gross))
        z=pd.DataFrame(records).fillna({'cost':0.})
        p_before=(1+w.strategy).cumprod().shift(1,fill_value=1)
        b_after=(1+w.EW_universe).iloc[::-1].cumprod().iloc[::-1]/(1+w.EW_universe)
        link=pd.Series((p_before*b_after).to_numpy(),index=w.signal_date)
        z['active_wealth_link']=z.signal_date.map(link)
        for col in ['allocation','selection','interaction','cost']:
            z['linked_'+col]=z[col]*z.active_wealth_link
        linked=['linked_allocation','linked_selection','linked_interaction','linked_cost']
        total=float(z[linked].sum().sum())
        active=float((1+w.strategy).prod()-(1+w.EW_universe).prod())
        assert abs(total-active)<1e-10
        bysector=z.groupby('sector')[linked].sum().reset_index()
        bysector['total_active_contribution']=bysector[linked].sum(axis=1)
        bysector.sort_values('total_active_contribution',ascending=False).to_csv(OUT/(label+'_brinson_EW_sectors.csv'),index=False)
        z.to_csv(OUT/(label+'_brinson_EW_detail.csv'),index=False)
        summaries.append(dict(window=label,benchmark='equal-weight eligible universe',
            strategy_cumulative_return=float((1+w.strategy).prod()-1),benchmark_cumulative_return=float((1+w.EW_universe).prod()-1),
            active_cumulative_return=active,allocation=float(z.linked_allocation.sum()),selection=float(z.linked_selection.sum()),
            interaction=float(z.linked_interaction.sum()),cost=float(z.linked_cost.sum()),reconciliation_error=total-active))
    pd.DataFrame(summaries).to_csv(OUT/'brinson_EW_summary.csv',index=False)
    print(pd.DataFrame(summaries).to_string(index=False))


if __name__=='__main__':main()
