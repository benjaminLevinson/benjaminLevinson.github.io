"""Versioned public AFS state and RFC 5545 output; no private member data."""
from __future__ import annotations
import copy
import hashlib
import json
import os
import re
import tempfile
from datetime import datetime,timedelta,timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from source import source_url,iso
UTC=timezone.utc
ERRORS={'source_http','source_schema','robots_denied','refresh_error'}

def timestamp(s):
    if not isinstance(s,str) or len(s)>40: raise ValueError('timestamp')
    d=datetime.fromisoformat(s.replace('Z','+00:00'))
    if d.tzinfo is None: raise ValueError('timestamp_zone')
    return d.astimezone(UTC)

def digest(e): return hashlib.sha256(json.dumps(e,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
def text(s,maximum=1000):
    if not isinstance(s,str) or not s.strip() or len(s)>maximum or any(ord(c)<32 or ord(c)==127 for c in s):
        raise ValueError('text')

def validate_event(e):
    if set(e)!={'id','title','start','end','source','ticket','location','status'}: raise ValueError('event_schema')
    if not re.fullmatch('[A-Za-z0-9]{15,18}',e['id']): raise ValueError('id')
    text(e['title']); text(e['location'])
    start=timestamp(e['start'])
    if e['end'] is not None and not timedelta(0)<timestamp(e['end'])-start<=timedelta(hours=10): raise ValueError('duration')
    if e['status'] not in {'active','cancelled'} or not source_url(e['source']): raise ValueError('event_status_source')
    if not re.fullmatch(r'https://austinfilmsociety\.(?:my\.salesforce-sites\.com|my\.site\.com)/ticket/#/instances/'+e['id'],e['ticket']): raise ValueError('ticket_url')
    return e

def reconcile(snapshot,previous=None,now=None):
    now=now or datetime.now(UTC)
    if previous: validate_bundle(previous)
    if abs(timestamp(snapshot['collectedAt'])-now)>timedelta(hours=1): raise ValueError('stale_snapshot')
    incoming={e['id']:validate_event(e) for e in snapshot['events']}
    if len(incoming)!=len(snapshot['events']): raise ValueError('duplicate_id')
    records=copy.deepcopy(previous['state']['events']) if previous else {}
    for key,event in incoming.items():
        prior=records.get(key); fp=digest(event)
        changed=prior is None or fp!=prior['fingerprint'] or prior['removalReason'] is not None
        records[key]={'event':event,'fingerprint':fp,'sequence':prior['sequence']+int(changed) if prior else 0,
                      'created':prior['created'] if prior else iso(now),'modified':iso(now) if changed else prior['modified'],
                      'missingSince':None,'lastMissingCheck':None,'missingCount':0,'removalReason':None}
    for key,record in records.items():
        e=record['event']
        if key in incoming or e['status']=='cancelled' or timestamp(e['start'])<now: continue
        local_date=timestamp(e['start']).astimezone(ZoneInfo('America/Chicago')).date().isoformat()
        if e['source'] not in snapshot['pages'] or not snapshot['coverageStart']<=local_date<=snapshot['coverageEnd']: continue
        last=record['lastMissingCheck']
        if last is None or now-timestamp(last)>=timedelta(hours=6):
            record['missingSince']=record['missingSince'] or iso(now)
            record['lastMissingCheck']=iso(now); record['missingCount']+=1
        if record['missingCount']>=2:
            e['status']='cancelled';record['fingerprint']=digest(e);record['sequence']+=1;record['modified']=iso(now)
            record['removalReason']='No longer listed in two complete checks at least six hours apart; confirm with AFS.'
    records={k:r for k,r in records.items() if timestamp(r['event']['end'] or r['event']['start'])>=now-timedelta(days=90)}
    status={'lastAttempt':iso(now),'lastSuccess':iso(now),'refreshStatus':'ok','error':None,
            'sourceCount':len(incoming),'feedCount':len(records),'pagesChecked':len(snapshot['pages']),
            'coverageStart':snapshot['coverageStart'],'coverageEnd':snapshot['coverageEnd'],'staleAfterHours':14}
    state={'events':records,'lastSuccess':iso(now)}
    return validate_bundle({'schemaVersion':1,'state':state,'status':status,'calendar':calendar(state)})

def escape(s): return s.replace('\\','\\\\').replace('\n','\\n').replace(';','\\;').replace(',','\\,')
def fold(line):
    pieces=[];piece=''
    for char in line:
        if len((piece+char).encode())>75: pieces.append(piece);piece=' '
        piece+=char
    return '\r\n'.join(pieces+[piece])
def icsdate(s): return timestamp(s).strftime('%Y%m%dT%H%M%SZ')
def calendar(state):
    lines=['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//blev.dev//AFS Member Mondays//EN','CALSCALE:GREGORIAN',
           'X-WR-CALNAME:AFS Member Mondays','X-WR-TIMEZONE:America/Chicago','REFRESH-INTERVAL;VALUE=DURATION:PT6H','X-PUBLISHED-TTL:PT6H']
    for key,r in sorted(state['events'].items(),key=lambda item:(item[1]['event']['start'],item[0])):
        e=r['event']
        description='Designated Member Monday. Free admission for AFS members; reserve through AFS. Check the source for availability and changes.'
        if e['end']: description+=' End time is estimated from the film runtime; introductions and Q&A may extend it.'
        if r['removalReason']: description+='\n'+r['removalReason']
        description+='\nTickets: '+e['ticket']
        lines+=['BEGIN:VEVENT','UID:afs-'+key+'@blev.dev','SEQUENCE:'+str(r['sequence']),
                'DTSTAMP:'+icsdate(r['modified']),'CREATED:'+icsdate(r['created']),'LAST-MODIFIED:'+icsdate(r['modified']),
                'DTSTART:'+icsdate(e['start'])]
        if e['end']: lines+=['DTEND:'+icsdate(e['end'])]
        lines+=['SUMMARY:'+escape('AFS Member Monday: '+e['title']),'LOCATION:'+escape(e['location']),
                'URL:'+e['source'],'DESCRIPTION:'+escape(description),
                'STATUS:'+('CANCELLED' if e['status']=='cancelled' else 'CONFIRMED'),'TRANSP:TRANSPARENT','END:VEVENT']
    return '\r\n'.join(fold(line) for line in lines+['END:VCALENDAR'])+'\r\n'

def validate_bundle(b):
    if not isinstance(b,dict) or set(b)!={'schemaVersion','state','status','calendar'} or b['schemaVersion']!=1: raise ValueError('bundle_schema')
    s=b['state'];st=b['status']
    if set(s)!={'events','lastSuccess'} or not isinstance(s['events'],dict) or len(s['events'])>1000: raise ValueError('state_schema')
    timestamp(s['lastSuccess'])
    for key,r in s['events'].items():
        if set(r)!={'event','fingerprint','sequence','created','modified','missingSince','lastMissingCheck','missingCount','removalReason'}: raise ValueError('record_schema')
        e=validate_event(r['event'])
        if key!=e['id'] or r['fingerprint']!=digest(e) or type(r['sequence']) is not int or r['sequence']<0: raise ValueError('record_integrity')
        timestamp(r['created']);timestamp(r['modified'])
        if r['missingSince'] is not None: timestamp(r['missingSince'])
        if r['lastMissingCheck'] is not None: timestamp(r['lastMissingCheck'])
        if type(r['missingCount']) is not int or not 0<=r['missingCount']<=2: raise ValueError('missing_count')
        if r['removalReason'] not in {None,'No longer listed in two complete checks at least six hours apart; confirm with AFS.'}: raise ValueError('removal_reason')
    if set(st)!={'lastAttempt','lastSuccess','refreshStatus','error','sourceCount','feedCount','pagesChecked','coverageStart','coverageEnd','staleAfterHours'}: raise ValueError('status_schema')
    timestamp(st['lastAttempt'])
    if st['lastSuccess']!=s['lastSuccess'] or st['feedCount']!=len(s['events']): raise ValueError('status_integrity')
    if st['refreshStatus'] not in {'ok','failed'} or st['error'] not in ERRORS|{None} or (st['error'] is None)!=(st['refreshStatus']=='ok'): raise ValueError('refresh_status')
    if st['staleAfterHours']!=14 or type(st['sourceCount']) is not int or not 0<=st['sourceCount']<=1000 or type(st['pagesChecked']) is not int or not 1<=st['pagesChecked']<=500: raise ValueError('status_counts')
    for field in ('coverageStart','coverageEnd'): datetime.strptime(st[field],'%Y-%m-%d')
    if st['coverageStart']>st['coverageEnd'] or b['calendar']!=calendar(s): raise ValueError('calendar_integrity')
    return b

def failure(previous,error,now=None):
    b=copy.deepcopy(validate_bundle(previous))
    b['status'].update(lastAttempt=iso(now or datetime.now(UTC)),refreshStatus='failed',error=error if error in ERRORS else 'source_schema')
    return validate_bundle(b)

def load(path):
    p=Path(path)
    if p.stat().st_size>5_000_000: raise ValueError('bundle_size')
    return validate_bundle(json.loads(p.read_text()))

def atomic(path,value):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    fd,temp=tempfile.mkstemp(dir=p.parent,prefix='.'+p.name)
    try:
        with os.fdopen(fd,'w',newline='',encoding='utf-8') as f: f.write(value);f.flush();os.fsync(f.fileno())
        os.replace(temp,p)
    finally:
        if os.path.exists(temp): os.unlink(temp)

def export(b,output):
    validate_bundle(b);p=Path(output)
    atomic(p/'calendar.ics',b['calendar'])
    atomic(p/'status.json',json.dumps(b['status'],indent=2)+'\n')
    atomic(p/'bundle.json',json.dumps(b,ensure_ascii=False,indent=2)+'\n')
