"""Content checks independent of Git's Windows CRLF conversion.

Raw original hashes remain in the audit. Normalised hashes ignore CRLF/LF
differences in text only; compressed inputs remain byte-for-byte checked.
"""
from pathlib import Path
import hashlib


def content_digest(path):
    p=Path(path)
    data=p.read_bytes()
    if p.suffix in {'.py','.yaml','.yml','.md','.csv','.txt','.json'}:
        data=data.replace(b'\r\n',b'\n')
    return hashlib.sha256(data).hexdigest()


def source_matches(root,records):
    for record in records:
        p=Path(root)/record['path']
        if 'sha256_lf_normalized' in record:
            actual=content_digest(p);expected=record['sha256_lf_normalized']
        else:
            actual=hashlib.sha256(p.read_bytes()).hexdigest();expected=record['sha256']
        if actual!=expected:return False
    return True
