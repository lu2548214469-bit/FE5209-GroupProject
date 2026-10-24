"""Compare a downloaded supplement with the frozen source. No data are patched."""
from datetime import datetime
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo
import argparse
import json
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--raw-dir',type=Path,required=True)
    ap.add_argument('--source-data',type=Path,default=ROOT/'data')
    ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    manifest=json.loads((args.raw_dir/'download_manifest.json').read_text())
    old=pd.read_csv(args.source_data/'prices_daily.csv.gz')
    old=old[old.date.between(manifest['requested_start'],manifest['requested_end'])]
    rows=[];actions=[]
    for record in manifest['records']:
        if record['status']!='downloaded':continue
        filename=quote(record['symbol'],safe='._-')+'.json'
        r=json.loads((args.raw_dir/filename).read_text())['chart']['result'][0]
        q=r['indicators']['quote'][0];tz=ZoneInfo(r['meta']['exchangeTimezoneName'])
        public=pd.DataFrame(dict(date=[datetime.fromtimestamp(t,tz).strftime('%Y-%m-%d') for t in r.get('timestamp',[])],
                                 close=q['close'],volume=q['volume']))
        z=public.merge(old[old.ticker.eq(record['symbol'])],on='date',suffixes=('_public','_source'))
        if len(z):
            rows.append(dict(symbol=record['symbol'],overlap_days=len(z),
                             max_relative_price_error=float((z.close_public/z.close_source-1).abs().max()),
                             volume_mismatches=int((z.volume_public-z.volume_source).abs().gt(.1).sum())))
        for kind,events in r.get('events',{}).items():
            for event in events.values():
                actions.append(dict(symbol=record['symbol'],kind=kind,
                                    date=datetime.fromtimestamp(event['date'],tz).strftime('%Y-%m-%d'),
                                    amount=event.get('amount'),public_quote_currency=r['meta'].get('currency')))
    pd.DataFrame(rows).to_csv(args.out/'quote_overlap.csv',index=False)
    pd.DataFrame(actions).to_csv(args.out/'public_corporate_actions.csv',index=False)
    (args.out/'SCOPE.json').write_text(json.dumps(dict(status='AUDIT_ONLY',
        warning='Price overlap does not verify factor scores, dividend currency conversions, FX fixing or STI total return. No source input has been overwritten.'),indent=2),encoding='utf-8')
    print(f'Audited {len(rows)} equity overlaps and {len(actions)} public corporate events. No source files changed.')

if __name__=='__main__':main()
