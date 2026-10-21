"""Final cross-file checks; source data and strategy remain read-only."""
from pathlib import Path
import json
import hashlib
import subprocess
import sys
from html.parser import HTMLParser
import base64
import pandas as pd

HERE=Path(__file__).resolve().parent
REPO=HERE.parent.parent if (HERE.parent.parent/'config/strategy.yaml').exists() else HERE.parent/'FE5209-GroupProject-attribution-review'
R=HERE/'results'
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

source=json.loads((HERE/'source_audit/source_files.json').read_text())
locked=[x for x in source if x['path'] not in ['README.md','GUIDE.md']]
assert all(digest(REPO/x['path'])==x['sha256'] for x in locked)
books=json.loads((HERE/'source_audit/workbooks.json').read_text(encoding='utf-8'))
book_status=[]
for b in books:
    p=Path(b['path'])
    if p.exists():
        assert digest(p)==b['sha256']
        book_status.append('original unchanged')
    else:book_status.append('original unavailable; frozen audit retained')

controls=pd.read_csv(R/'workbook_reconciliation.csv')
assert controls.loc[controls.required,'passed'].all()
assert controls.passed.sum()==17 and len(controls)==18
windows=json.loads((R/'account_window_summary.json').read_text())
checks=[]
for w in windows:
    prefix=w['window']
    for grouping in ['stock','sector','currency']:
        d=pd.read_csv(R/f'{prefix}_{grouping}.csv')
        error=abs(float(d.net_pnl.sum())-w['pnl_sgd'])
        assert error<1e-6
        assert abs(d.contribution_pp.sum()-100*w['cumulative_return'])<1e-7
        checks.append(dict(window=prefix,check=grouping,error_sgd=error))
    c=pd.read_csv(R/f'{prefix}_component.csv')
    assert abs(c.amount_sgd.sum()-w['pnl_sgd'])<1e-6
    dd=pd.read_csv(R/f'{prefix}_max_drawdown_stocks.csv')
    assert abs(dd.drawdown_contribution_pp.sum()+100*w['max_drawdown'])<1e-7
for name in ['brinson_EW_summary.csv','active_STI_summary.csv']:
    d=pd.read_csv(R/name)
    assert d.reconciliation_error.abs().max()<1e-8
weekly=json.loads((R/'weekly_attribution_summary.json').read_text())
assert all(abs(x['reconciliation_error'])<1e-8 for x in weekly)
test=subprocess.run([sys.executable,str(HERE/'test_attribution.py'),'-v'],capture_output=True,text=True)
(HERE/'source_audit/attribution_tests.txt').write_text(test.stdout+test.stderr,encoding='utf-8')
assert test.returncode==0

class Images(HTMLParser):
    def __init__(self):super().__init__();self.sources=[]
    def handle_starttag(self,tag,attrs):
        if tag=='img':self.sources.append(dict(attrs)['src'])
parser=Images();report=HERE/'report/SG_K3_ATTRIBUTION_ZH.html'
parser.feed(report.read_text(encoding='utf-8'))
assert len(parser.sources)==8
for src in parser.sources:
    assert src.startswith('data:image/png;base64,')
    assert base64.b64decode(src.split(',',1)[1]).startswith(b'\x89PNG\r\n\x1a\n')
status=subprocess.check_output(['git','status','--porcelain'],cwd=REPO,text=True,encoding='utf-8').strip()
# Other repository changes do not invalidate the hashed strategy/data checks.
qa=dict(passed=True,source_files_verified=len(locked),source_checkout_clean=not bool(status),strategy_and_inputs_unchanged=True,
    workbook_original_status=book_status,account_group_checks=checks,
    workbook_portfolio_controls_passed=17,workbook_benchmark_warning_retained=True,
    attribution_unit_tests_passed=4,embedded_PNGs=8,
    sector_labels_certified=False,source_dividend_coverage_through='2026-09-15',
    browser_layout_preview='Local-file preview blocked by browser protocol policy; figures visually inspected and standalone HTML structure checked')
(R/'final_delivery_QA.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in qa.items() if k!='account_group_checks'},ensure_ascii=False,indent=2))
