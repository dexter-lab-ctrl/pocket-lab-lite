#!/usr/bin/env python3
"""Normalize third-party supply-chain JSON into a bounded redacted summary.

Raw input stays transient. This script intentionally emits counts/classifications and a digest,
not raw findings, paths, host identifiers, package registry credentials or secret matches.
"""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
import jsonschema
ROOT=Path(__file__).resolve().parents[3]
SCHEMA=ROOT/'schemas/documentation/supply-chain-normalized.schema.json'

def count(value):
    if isinstance(value,list): return len(value)
    if isinstance(value,dict): return len(value)
    return 0

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--tool',required=True); ap.add_argument('--input',required=True); ap.add_argument('--output',required=True); a=ap.parse_args()
    src=Path(a.input); raw=src.read_bytes(); data=json.loads(raw)
    keys=sorted(data) if isinstance(data,dict) else []
    summary={'top_level_keys':keys[:32],'record_count':count(data),'finding_like_counts':{}}
    if isinstance(data,dict):
        for key in keys:
            low=key.lower()
            if any(x in low for x in ['vulnerab','match','finding','secret','license','package','result']): summary['finding_like_counts'][key]=count(data[key])
    out={'schema_version':'1.0.0','tool':a.tool,'source_digest':hashlib.sha256(raw).hexdigest(),'summary':summary,'redacted':True}
    jsonschema.validate(out,json.loads(SCHEMA.read_text()))
    dest=Path(a.output); dest.parent.mkdir(parents=True,exist_ok=True); dest.write_text(json.dumps(out,sort_keys=True,indent=2)+'\n')
    print(f'PASS normalized {a.tool} evidence without raw findings')
if __name__=='__main__': main()
