"""Package only this completed delivery; keep dependencies and Git outside."""
from pathlib import Path
import json
import hashlib
import zipfile

HERE=Path(__file__).resolve().parent
dest=HERE/'SG_K3_ATTRIBUTION_20261021.zip'
manifest=HERE/'DELIVERY_MANIFEST.json'
def include(p):
    rel=p.relative_to(HERE)
    return p.is_file() and not {'runtime_deps','__pycache__'}.intersection(rel.parts) and p not in [dest,manifest] and p.suffix!='.pyc'
paths=sorted(p for p in HERE.rglob('*') if include(p))
records=[dict(path=p.relative_to(HERE).as_posix(),bytes=p.stat().st_size,
              sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in paths]
manifest.write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
with zipfile.ZipFile(dest,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for p in paths+[manifest]:z.write(p,arcname=(Path(HERE.name)/p.relative_to(HERE)).as_posix())
with zipfile.ZipFile(dest) as z:assert z.testzip() is None
print(json.dumps(dict(path=str(dest),files=len(paths)+1,MB=dest.stat().st_size/1024**2,
    sha256=hashlib.sha256(dest.read_bytes()).hexdigest()),ensure_ascii=False,indent=2))
