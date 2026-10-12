"""Public-only Crux feed state, validation, and RFC 5545 serialization."""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

UTC = timezone.utc
CATEGORIES = [1, 2, 4, 5, 8, 9, 10, 11, 16]
SCOPE = {'locationId': 2, 'categoryIds': CATEGORIES, 'timeZone': 'America/Chicago'}
LOCATION = 'Crux Central, 6015 Dillard Circle Unit B, Austin, TX 78752'
ERRORS = {'captcha', 'browser_error', 'source_http', 'schema_error', 'incomplete', 'unexpected_empty', 'mass_removal', 'timeout'}


def timestamp(s):
    if not isinstance(s, str) or len(s) > 40:
        raise ValueError('invalid_timestamp')
    d = datetime.fromisoformat(s.replace('Z', '+00:00'))
    if d.tzinfo is None:
        raise ValueError('missing_offset')
    return d.astimezone(UTC)


def iso(d):
    return d.astimezone(UTC).isoformat(timespec='seconds').replace('+00:00', 'Z')


def digest(x):
    return hashlib.sha256(json.dumps(x, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def validate_occurrence(x):
    if set(x) != {'id', 'eventId', 'title', 'start', 'end', 'status', 'timeZone'}:
        raise ValueError('occurrence_schema')
    if any(type(x[k]) is not int or not 0 < x[k] <= 9007199254740991 for k in ('id', 'eventId')):
        raise ValueError('invalid_id')
    if not isinstance(x['title'], str) or not x['title'].strip() or len(x['title']) > 1000:
        raise ValueError('invalid_title')
    if any(ord(c)<32 and c not in '\t\r\n' or ord(c)==127 for c in x['title']):
        raise ValueError('title_control_character')
    if x['status'] not in {'active', 'cancelled'} or x['timeZone'] != SCOPE['timeZone']:
        raise ValueError('unknown_status_or_timezone')
    start, end = timestamp(x['start']), timestamp(x['end'])
    if not timedelta(0) < end-start <= timedelta(days=7):
        raise ValueError('invalid_duration')
    return {**x, 'start': iso(start), 'end': iso(end)}


def validate_snapshot(s):
    if set(s) != {'schemaVersion', 'collectedAt', 'scope', 'windowStart', 'windowEnd', 'pagination', 'occurrences'}:
        raise ValueError('snapshot_schema')
    if s['schemaVersion'] != 1 or s['scope'] != SCOPE:
        raise ValueError('scope_changed')
    timestamp(s['collectedAt'])
    start, end = timestamp(s['windowStart']), timestamp(s['windowEnd'])
    if not timedelta(days=27) <= end-start <= timedelta(days=33):
        raise ValueError('unexpected_window')
    pg = s['pagination']
    if set(pg) != {'pageCount', 'rowCount', 'pages'} or type(pg['pageCount']) is not int or not 1 <= pg['pageCount'] <= 100:
        raise ValueError('pagination_schema')
    if pg['pages'] != list(range(1, pg['pageCount']+1)) or type(pg['rowCount']) is not int:
        raise ValueError('incomplete')
    rows = [validate_occurrence(x) for x in s['occurrences']]
    if not rows:
        raise ValueError('unexpected_empty')
    if len(rows) != pg['rowCount'] or len({r['id'] for r in rows}) != len(rows):
        raise ValueError('count_or_duplicate_mismatch')
    if any(not start <= timestamp(r['start']) < end for r in rows):
        raise ValueError('occurrence_outside_window')
    return {**s, 'occurrences': rows}


def reconcile(snapshot, previous=None, now=None):
    s = validate_snapshot(snapshot)
    now = now or datetime.now(UTC)
    if abs(now-timestamp(s['collectedAt'])) > timedelta(hours=1):
        raise ValueError('stale_snapshot')
    if previous:
        validate_bundle(previous)
    old = copy.deepcopy(previous['state']['events']) if previous else {}
    start, end = timestamp(s['windowStart']), timestamp(s['windowEnd'])
    incoming = {str(x['id']): x for x in s['occurrences']}
    eligible = {k for k,v in old.items() if v['event']['status'] == 'active'
                and max(start, now) <= timestamp(v['event']['start']) < end}
    missing = eligible-incoming.keys()
    if len(missing) >= 10 and len(missing) > len(eligible)*0.25:
        raise ValueError('mass_removal')
    for key, event in incoming.items():
        prev = old.get(key)
        fingerprint = digest(event)
        reason = 'Source marked cancelled' if event['status'] == 'cancelled' else None
        changed = not prev or prev['fingerprint'] != fingerprint or prev.get('cancellationReason') != reason
        old[key] = {'event': event, 'fingerprint': fingerprint,
                    'sequence': prev['sequence'] + int(changed) if prev else 0,
                    'created': prev['created'] if prev else iso(now),
                    'modified': iso(now) if changed else prev['modified'],
                    'missingSince': None, 'missingCount': 0, 'lastMissingCheck': None,
                    'cancellationReason': reason}
    for key in missing:
        record = old[key]
        last = record.get('lastMissingCheck')
        if last is None or now-timestamp(last) >= timedelta(minutes=30):
            record['missingCount'] += 1
            record['missingSince'] = record['missingSince'] or iso(now)
            record['lastMissingCheck'] = iso(now)
        if record['missingCount'] >= 2:
            record['event']['status'] = 'cancelled'
            record['fingerprint'] = digest(record['event'])
            record['sequence'] += 1
            record['modified'] = iso(now)
            record['cancellationReason'] = 'No longer listed in two complete source snapshots; verify with Crux'
    for key in list(old):
        record = old[key]
        retention = 90 if record['event']['status'] == 'cancelled' else 30
        if timestamp(record['event']['end']) < now-timedelta(days=retention):
            del old[key]
    state = {'schemaVersion': 1, 'scope': SCOPE, 'events': old,
             'coverage': {'start': s['windowStart'], 'end': s['windowEnd']},
             'lastSuccess': iso(now)}
    status = {'schemaVersion': 1, 'lastAttempt': iso(now), 'lastSuccess': iso(now),
              'refreshStatus': 'ok', 'error': None, 'coverage': state['coverage'],
              'sourceCount': len(incoming), 'feedCount': len(old), 'staleAfterHours': 6}
    return {'schemaVersion': 1, 'state': state, 'status': status, 'calendar': calendar(state)}


def failure(previous, reason, now=None):
    if reason not in ERRORS:
        reason = 'schema_error'
    if previous is None:
        raise ValueError('no_last_good_feed')
    validate_bundle(previous)
    result = copy.deepcopy(previous)
    result['status'].update(lastAttempt=iso(now or datetime.now(UTC)), refreshStatus='failed', error=reason)
    return result


def escape(s):
    return s.replace('\\', '\\\\').replace('\r\n', '\n').replace('\r', '\n').replace('\n', '\\n').replace(';', '\\;').replace(',', '\\,')


def fold(line):
    pieces, current = [], ''
    for char in line:
        if len((current+char).encode('utf-8')) > 75:
            pieces.append(current)
            current = ' '
        current += char
    pieces.append(current)
    return '\r\n'.join(pieces)


def icsdate(s):
    return timestamp(s).strftime('%Y%m%dT%H%M%SZ')


def calendar(state):
    lines = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//blev.dev//Crux Central public calendar//EN',
             'CALSCALE:GREGORIAN', 'X-WR-CALNAME:Crux Central — classes and events', 'X-WR-TIMEZONE:America/Chicago',
             'REFRESH-INTERVAL;VALUE=DURATION:PT1H', 'X-PUBLISHED-TTL:PT1H']
    for key, r in sorted(state['events'].items(), key=lambda item:(item[1]['event']['start'],int(item[0]))):
        e = r['event']
        url = f"https://crux.portal.approach.app/event/{e['eventId']}/booking/{e['id']}"
        description = 'Public Crux schedule. Availability and booking requirements: see the source link.'
        if r.get('cancellationReason'):
            description += '\n'+r['cancellationReason']
        lines += ['BEGIN:VEVENT', f"UID:crux-central-booking{e['id']}@blev.dev", f"SEQUENCE:{r['sequence']}",
                  'DTSTAMP:'+icsdate(r['modified']), 'CREATED:'+icsdate(r['created']),
                  'LAST-MODIFIED:'+icsdate(r['modified']), 'DTSTART:'+icsdate(e['start']), 'DTEND:'+icsdate(e['end']),
                  'SUMMARY:'+escape(e['title']), 'LOCATION:'+escape(LOCATION), 'URL:'+url,
                  'DESCRIPTION:'+escape(description), 'STATUS:'+('CANCELLED' if e['status']=='cancelled' else 'CONFIRMED'),
                  'TRANSP:TRANSPARENT', 'END:VEVENT']
    return '\r\n'.join(fold(line) for line in lines+['END:VCALENDAR'])+'\r\n'


def validate_bundle(b):
    if not isinstance(b, dict) or set(b) != {'schemaVersion','state','status','calendar'} or b['schemaVersion'] != 1:
        raise ValueError('bundle_schema')
    s = b['state']
    if set(s) != {'schemaVersion','scope','events','coverage','lastSuccess'} or s['scope'] != SCOPE or s['schemaVersion'] != 1:
        raise ValueError('state_schema')
    if not 1 <= len(s['events']) <= 15000:
        raise ValueError('state_size')
    timestamp(s['lastSuccess'])
    if set(s['coverage']) != {'start','end'} or timestamp(s['coverage']['start']) >= timestamp(s['coverage']['end']):
        raise ValueError('coverage_schema')
    for k,r in s['events'].items():
        if set(r) != {'event','fingerprint','sequence','created','modified','missingSince','missingCount','lastMissingCheck','cancellationReason'}:
            raise ValueError('record_schema')
        e = validate_occurrence(r['event'])
        if k != str(e['id']) or r['fingerprint'] != digest(e) or type(r['sequence']) is not int or r['sequence'] < 0:
            raise ValueError('record_integrity')
        timestamp(r['created']); timestamp(r['modified'])
        if type(r['missingCount']) is not int or not 0 <= r['missingCount'] <= 2:
            raise ValueError('missing_count')
        for field in ('missingSince','lastMissingCheck'):
            if r[field] is not None: timestamp(r[field])
        if r['cancellationReason'] not in {None,'Source marked cancelled','No longer listed in two complete source snapshots; verify with Crux'}:
            raise ValueError('cancellation_reason')
    st = b['status']
    if set(st) != {'schemaVersion','lastAttempt','lastSuccess','refreshStatus','error','coverage','sourceCount','feedCount','staleAfterHours'}:
        raise ValueError('status_schema')
    if st['lastSuccess'] != s['lastSuccess'] or st['coverage'] != s['coverage'] or st['feedCount'] != len(s['events']):
        raise ValueError('status_integrity')
    if st['refreshStatus'] not in {'ok','failed'} or st['error'] not in ERRORS | {None}:
        raise ValueError('status_value')
    if st['schemaVersion'] != 1 or st['staleAfterHours'] != 6 or type(st['sourceCount']) is not int or not 1 <= st['sourceCount'] <= 15000:
        raise ValueError('status_fields')
    if (st['refreshStatus']=='ok') != (st['error'] is None):
        raise ValueError('status_error')
    timestamp(st['lastAttempt'])
    if b['calendar'] != calendar(s):
        raise ValueError('calendar_integrity')
    return b


def load(path):
    p=Path(path)
    if p.stat().st_size > 10_000_000:
        raise ValueError('oversized_input')
    return json.loads(p.read_text())


def atomic(path, text):
    path=Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    fd,tmp=tempfile.mkstemp(dir=path.parent, prefix='.'+path.name)
    try:
        with os.fdopen(fd,'w') as f:
            f.write(text); f.flush(); os.fsync(f.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)


def export(b, directory):
    validate_bundle(b)
    p=Path(directory)
    atomic(p/'calendar.ics', b['calendar'])
    for name in ('state','status'):
        atomic(p/(name+'.json'), json.dumps(b[name],ensure_ascii=False,indent=2)+'\n')


if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('action',choices=['update','fail','export'])
    parser.add_argument('--bundle',required=True); parser.add_argument('--snapshot'); parser.add_argument('--reason'); parser.add_argument('--output')
    args=parser.parse_args(); previous=load(args.bundle) if Path(args.bundle).exists() else None
    if args.action=='export': export(previous,args.output)
    else:
        result=reconcile(load(args.snapshot),previous) if args.action=='update' else failure(previous,args.reason)
        validate_bundle(result); atomic(args.bundle,json.dumps(result,ensure_ascii=False,indent=2)+'\n')
