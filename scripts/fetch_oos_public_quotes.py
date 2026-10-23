"""Download an auditable public quote supplement without editing source data."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
import argparse
import csv
import hashlib
import json

ROOT=Path(__file__).resolve().parents[1]

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--master',type=Path,default=ROOT/'data/security_master.csv')
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--start',default='2026-09-25')
    ap.add_argument('--end',default='2026-10-20')
    args=ap.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    start=datetime.fromisoformat(args.start).replace(tzinfo=timezone.utc)
    end=datetime.fromisoformat(args.end).replace(tzinfo=timezone.utc)+timedelta(days=1)
    if start>=end:raise ValueError('Invalid quote date interval')
    with args.master.open(encoding='utf-8-sig',newline='') as f:
        symbols=sorted({r['ticker'] for r in csv.DictReader(f)})
    symbols+=['SGD=X','EURSGD=X','AUDSGD=X','^STI']
    query=urlencode(dict(period1=int(start.timestamp()),period2=int(end.timestamp()),interval='1d',events='div,splits'))
    def fetch(symbol):
        url=f'https://query1.finance.yahoo.com/v8/finance/chart/{quote(symbol,safe="")}?{query}'
        try:
            with urlopen(Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=25) as response:
                raw=response.read()
            p=json.loads(raw)['chart']
            if p.get('error') or not p.get('result'):raise ValueError(str(p.get('error')))
            filename=quote(symbol,safe='._-')+'.json'
            (args.out/filename).write_bytes(raw)
            return dict(symbol=symbol,status='downloaded',filename=filename,url=url,sha256=hashlib.sha256(raw).hexdigest(),
                        observations=len(p['result'][0].get('timestamp',[])))
        except Exception as e:
            return dict(symbol=symbol,status='unavailable',url=url,error=f'{type(e).__name__}: {e}')
    rows=[]
    with ThreadPoolExecutor(max_workers=2) as pool:
        for job in as_completed([pool.submit(fetch,s) for s in symbols]):rows.append(job.result())
    result=dict(source='Yahoo public chart observations',requested_start=args.start,requested_end=args.end,
                retrieved_at_utc=datetime.now(timezone.utc).isoformat(),
                benchmark_warning='^STI is a price index and is NOT a replacement for the LSEG .TRISTI total-return series',
                records=sorted(rows,key=lambda r:r['symbol']))
    (args.out/'download_manifest.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    count=sum(r['status']=='downloaded' for r in rows)
    print(f'{count}/{len(symbols)} series downloaded. Original data unchanged. ^STI is price-only.')
    if count!=len(symbols):raise SystemExit(2)

if __name__=='__main__':main()
