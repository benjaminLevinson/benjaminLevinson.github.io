"""Six-hour public collector. Any partial scan preserves the last good ICS."""
import argparse
import json
import sys
import time
from pathlib import Path
from source import collect,SourceError
from feed import load,reconcile,failure,atomic

def refresh(path,bootstrap=False,collector=collect):
    previous=load(path) if Path(path).exists() else None
    if previous is None and not bootstrap: raise ValueError('seed_required')
    try: result=reconcile(collector(previous),previous)
    except Exception as e:
        if previous is None: raise
        reason=str(e) if isinstance(e,SourceError) else 'refresh_error'
        result=failure(previous,reason)
    atomic(path,json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result['status']),flush=True)
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--bundle',default='/data/bundle.json');p.add_argument('--once',action='store_true');p.add_argument('--bootstrap',action='store_true');a=p.parse_args()
    if a.bootstrap and not a.once: p.error('bootstrap requires --once')
    while True:
        code=0
        try:
            result=refresh(a.bundle,a.bootstrap)
            if result['status']['refreshStatus']!='ok': code=2
        except Exception as e: print(json.dumps({'refreshStatus':'failed','error_type':type(e).__name__}),flush=True);code=2
        if a.once: sys.exit(code)
        time.sleep(6*3600)
