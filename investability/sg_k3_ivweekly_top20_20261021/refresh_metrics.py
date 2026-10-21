"""Refresh summaries from saved paths after metric-only fixes; no resimulation."""
import json
import hashlib
import pandas as pd
import run_study as study
from diagnostics import load_case

study.initialise();rows=[]
manifest=json.loads((study.HERE/'source_manifest.json').read_text())['files']
assert all(hashlib.sha256(study.input_bytes(study.REPO/x['path'])).hexdigest()==x.get('sha256_lf_normalized',x['sha256']) for x in manifest)
for case in study.grid():
    r=load_case(case['name']);settings={**study.CTX['ecfg']['settings'],**case['settings']}
    windows=[]
    if not case.get('fresh'):
        windows.extend([('EVAL','2021-01-07','2026-09-30',settings['initial_cash']),('WHOLE','2021-01-07','2026-10-15',settings['initial_cash'])])
    windows.append(('OCTOBER_CLOSE','2026-10-01','2026-10-15',None))
    if case.get('fresh'):windows.append(('OCTOBER_CASH','2026-09-30','2026-10-15',settings['initial_cash']))
    updated=[study.measures(r,case,settings,pd.Timestamp(a),pd.Timestamp(b),base,label) for label,a,b,base in windows]
    p=study.HERE/'scenarios'/case['name']/'summary.json';original=json.loads(p.read_text());original['rows']=updated
    assert original['case']==case
    original['cache_key']=study.cache_key(case)
    p.write_text(json.dumps(original,indent=2,allow_nan=False))
    rows.extend(updated)
pd.DataFrame(rows).to_csv(study.HERE/'results/scenario_summary.csv',index=False)
print('Refreshed',len(rows),'window summaries from',len(study.grid()),'saved account paths')
