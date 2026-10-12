"""Separate publisher: one validated public file, one fixed repository/branch.

Requires separately approved repository-scoped Contents-write credential.
Never run in the browser collector container or mount its token there.
"""
import argparse
import base64
import json
import time
import sys
from pathlib import Path
from urllib.request import Request, build_opener, HTTPRedirectHandler
from feed import load,validate_bundle,timestamp
ENDPOINT='https://api.github.com/repos/benjaminLevinson/benjaminLevinson.github.io/contents/bundle.json'
BRANCH='crux-data'
class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None

def publish(bundle_path,token_path):
    b=validate_bundle(load(bundle_path));token=Path(token_path).read_text().strip()
    if not token or '\n' in token:raise ValueError('missing_token')
    opener=build_opener(NoRedirect)
    headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2026-03-10','Content-Type':'application/json'}
    with opener.open(Request(ENDPOINT+'?ref='+BRANCH,headers=headers),timeout=30) as r:
        current=json.loads(r.read(15_000_000))
    previous=validate_bundle(json.loads(base64.b64decode(current['content'])))
    if timestamp(b['status']['lastAttempt'])<timestamp(previous['status']['lastAttempt']) or timestamp(b['state']['lastSuccess'])<timestamp(previous['state']['lastSuccess']):
        raise ValueError('refuse_state_regression')
    content=json.dumps(b,ensure_ascii=False,indent=2)+'\n'
    if json.loads(base64.b64decode(current['content']))==b:return 'unchanged'
    body={'branch':BRANCH,'sha':current['sha'],'message':'Refresh public Crux calendar and source status','content':base64.b64encode(content.encode()).decode()}
    with opener.open(Request(ENDPOINT,data=json.dumps(body).encode(),headers=headers,method='PUT'),timeout=30) as r:
        if r.status!=200:raise ValueError('unexpected_publish_response')
    return 'published'
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--bundle',default='/data/bundle.json');p.add_argument('--token-file',default='/run/secrets/crux_github_token');p.add_argument('--once',action='store_true');a=p.parse_args()
    while True:
        code=0
        try:print(json.dumps({'publication':publish(a.bundle,a.token_file)}),flush=True)
        except Exception as e:
            print(json.dumps({'publication':'failed','error_type':type(e).__name__}),flush=True);code=2
        if a.once:sys.exit(code)
        time.sleep(300)
