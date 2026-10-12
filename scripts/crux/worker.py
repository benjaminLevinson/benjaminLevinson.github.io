"""Hourly normal-browser collector with atomic last-good bundle retention."""
import argparse
import json
import os
import subprocess
import time
import sys
from pathlib import Path
from feed import load,reconcile,failure,validate_bundle,atomic,ERRORS
BASE=Path(__file__).resolve().parent

def refresh(bundle_path,bootstrap=False):
    p=Path(bundle_path);p.parent.mkdir(parents=True,exist_ok=True)
    previous=validate_bundle(load(p)) if p.exists() else None
    if previous is None and not bootstrap:raise ValueError('seed_state_required')
    source=p.parent/'source-snapshot.json'
    try:
        run=subprocess.run(['timeout','240','xvfb-run','-a','node',str(BASE/'collector.cjs'),str(source)],capture_output=True,text=True,timeout=260)
        outcome=json.loads(run.stdout.strip().splitlines()[-1]) if run.stdout.strip() else {'error':'browser_error'}
        if run.returncode or outcome.get('result')!='ok':
            reason=outcome.get('error','browser_error')
            result=failure(previous,reason)
        else:result=reconcile(load(source),previous)
    except subprocess.TimeoutExpired:result=failure(previous,'timeout')
    except ValueError as e:
        result=failure(previous,str(e) if str(e) in ERRORS else 'schema_error')
    except Exception:
        result=failure(previous,'browser_error')
    validate_bundle(result)
    atomic(p,json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result['status']),flush=True)
    return result
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--bundle',default='/data/bundle.json');parser.add_argument('--once',action='store_true');parser.add_argument('--bootstrap',action='store_true');args=parser.parse_args()
    if args.bootstrap and not args.once:raise SystemExit('Bootstrap is a one-time operator action.')
    while True:
        code=0
        try:
            result=refresh(args.bundle,args.bootstrap)
            code=0 if result['status']['refreshStatus']=='ok' else 2
        except Exception as e:
            print(json.dumps({'refreshStatus':'failed','error_type':type(e).__name__}),flush=True);code=2
        if args.once:sys.exit(code)
        time.sleep(3600)
