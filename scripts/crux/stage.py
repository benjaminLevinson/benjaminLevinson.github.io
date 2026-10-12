"""Stage public data into Hugo's full-site build; never execute data-branch code."""
import argparse
import json
from pathlib import Path
from urllib.request import urlopen
from feed import validate_bundle, export, atomic
SOURCE='https://raw.githubusercontent.com/benjaminLevinson/benjaminLevinson.github.io/refs/heads/crux-data/bundle.json'
LAST_GOOD='https://blev.dev/crux/bundle.json'

def fetch(url):
    with urlopen(url,timeout=30) as r:
        data=r.read(10_000_001)
    if len(data)>10_000_000:raise ValueError('oversized_bundle')
    return validate_bundle(json.loads(data))

def stage(output,local=None):
    if local:
        b=validate_bundle(json.loads(Path(local).read_text()))
    else:
        b=None
        for url in (SOURCE,LAST_GOOD):
            try:b=fetch(url);break
            except Exception:continue
        if b is None:raise RuntimeError('No validated feed available; preserving existing deployed site.')
    export(b,output)
    atomic(Path(output)/'bundle.json',json.dumps(b,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'result':'staged','count':b['status']['feedCount'],'lastSuccess':b['status']['lastSuccess'],'refreshStatus':b['status']['refreshStatus']}))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',default='static/crux');p.add_argument('--local-bundle');a=p.parse_args()
    stage(a.output,a.local_bundle)
