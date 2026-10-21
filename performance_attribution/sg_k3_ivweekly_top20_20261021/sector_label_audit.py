"""Source group consistency and a disclosure-only label sensitivity.

No source, signal, holding, trade, or account result is changed. This does not
rerun sector constraints or factor neutralisation with a corrected mapping.
"""
from pathlib import Path
import json
import pandas as pd

HERE=Path(__file__).resolve().parent
REPO=HERE.parent.parent if (HERE.parent.parent/'config/strategy.yaml').exists() else HERE.parent/'FE5209-GroupProject-attribution-review'
OUT=HERE/'results'
master=pd.read_csv(REPO/'data/security_master.csv')
u=pd.read_csv(REPO/'data/sg_universe_weekly.csv.gz',usecols=['ticker','sector'])
joined=u.merge(master[['ticker','six_sector']],on='ticker',validate='many_to_one')
dif=joined[joined.sector.ne(joined.six_sector)]
dif.to_csv(OUT/'source_sector_mapping_inconsistency.csv',index=False)
rows=[]
for window in ['execution_eval','fresh_live_close_to_close']:
    stock=pd.read_csv(OUT/(window+'_stock.csv'))
    cnmc=stock[stock.ticker.eq('5TP.SI')].iloc[0]
    for sector in ['technology & communications','other']:
        original=stock.loc[stock.six_sector.eq(sector),'net_pnl'].sum()
        change=(-1 if sector=='technology & communications' else 1)*cnmc.net_pnl
        rows.append(dict(window=window,sector=sector,source_group_pnl=original,
                         illustration_reclass_CNMC_pnl=original+change,
                         change_sgd=change,
                         basis='display-only: move CNMC to other; no strategy rerun'))
pd.DataFrame(rows).to_csv(OUT/'sector_label_CNMC_display_sensitivity.csv',index=False)
finding=dict(ticker='5TP.SI',company_name='CNMC Goldmine Holdings Limited',
    source_six_sector='technology & communications',
    official_business='gold exploration, mining and ore processing',
    provider_grouping_definition_verified=False,
    universe_vs_security_master_mismatched_stock_weeks=int(len(dif)),
    official_sources=['https://www.cnmc.com.hk/about_us.html',
        'https://investorrelations.sgx.com/news-releases/news-release-details/cnmc-goldmine-lists-catalist-expanding-sgx-commodities-resource'],
    implication='source sector results describe original research groups; labels are not certified industry classes; original grouping affects source sector-neutral scores and portfolio caps if used upstream',
    display_reclassification_is_corrected_strategy_backtest=False)
(OUT/'sector_label_audit.json').write_text(json.dumps(finding,ensure_ascii=False,indent=2),encoding='utf-8')
print(pd.DataFrame(rows).to_string(index=False))
