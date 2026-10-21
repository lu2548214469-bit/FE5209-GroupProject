from pathlib import Path
import json,hashlib,zipfile,sys
HERE=Path(__file__).resolve().parent
dest=HERE/'SG_K3_INVESTABILITY_20261021.zip'
manifest=HERE/'DELIVERY_MANIFEST.json'
files=sorted(p for p in HERE.rglob('*') if p.is_file() and p not in [dest,manifest] and '__pycache__' not in p.parts and p.suffix!='.pyc')
records=[]
for p in files:
    data=p.read_bytes()
    canonical=data.replace(b'\r\n',b'\n') if p.suffix in {'.py','.mjs','.json','.md','.txt','.csv','.html'} else data
    records.append(dict(path=p.relative_to(HERE).as_posix(),bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),sha256_lf_normalized=hashlib.sha256(canonical).hexdigest()))
manifest.write_text(json.dumps(records,indent=2),encoding='utf-8')
if '--manifest-only' in sys.argv:
    print(json.dumps(dict(manifest=str(manifest),files=len(files)),ensure_ascii=False))
    raise SystemExit(0)
with zipfile.ZipFile(dest,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for p in files+[manifest]:z.write(p,arcname=(Path(HERE.name)/p.relative_to(HERE)).as_posix())
with zipfile.ZipFile(dest) as z:assert z.testzip() is None
print(json.dumps(dict(path=str(dest),files=len(files)+1,MB=dest.stat().st_size/1024**2),ensure_ascii=False))
