import copy
import unittest
from datetime import datetime,timedelta,timezone
from zoneinfo import ZoneInfo
from feed import SCOPE,reconcile,failure,calendar,validate_bundle,validate_snapshot,fold,timestamp
UTC=timezone.utc
NOW=datetime(2026,10,12,13,tzinfo=UTC)

def row(i=1,start='2026-10-15T00:00:00Z',end='2026-10-15T02:00:00Z',**kw):
    return dict(id=i,eventId=222,title='Beta, babes; climb \\ together',start=start,end=end,status='active',timeZone='America/Chicago',**kw)

def snapshot(rows=None,now=NOW):
    rows=rows if rows is not None else [row()]
    return {'schemaVersion':1,'collectedAt':now.isoformat(),'scope':copy.deepcopy(SCOPE),
            'windowStart':'2026-10-12T05:00:00Z','windowEnd':'2026-11-13T06:00:00Z',
            'pagination':{'pageCount':1,'rowCount':len(rows),'pages':[1]},'occurrences':rows}

class FeedTests(unittest.TestCase):
    def test_unchanged_ics_sequence_and_dtstamp(self):
        a=reconcile(snapshot(),now=NOW);b=reconcile(snapshot(now=NOW+timedelta(hours=1)),a,now=NOW+timedelta(hours=1))
        self.assertEqual(a['calendar'],b['calendar']);self.assertEqual(b['state']['events']['1']['sequence'],0)
    def test_move_preserves_uid_and_increments_sequence(self):
        a=reconcile(snapshot(),now=NOW);r=row();r['start']='2026-10-16T00:00:00Z';r['end']='2026-10-16T02:00:00Z'
        b=reconcile(snapshot([r]),a,now=NOW)
        self.assertEqual(b['state']['events']['1']['sequence'],1)
        self.assertIn('UID:crux-central-booking1@blev.dev',b['calendar'])
        self.assertEqual(a['state']['events']['1']['created'],b['state']['events']['1']['created'])
    def test_explicit_cancellation_and_reappearance(self):
        a=reconcile(snapshot(),now=NOW);r=row();r['status']='cancelled';b=reconcile(snapshot([r]),a,now=NOW)
        self.assertIn('STATUS:CANCELLED',b['calendar'])
        c=reconcile(snapshot(),b,now=NOW);self.assertEqual(c['state']['events']['1']['sequence'],2)
        self.assertIn('STATUS:CONFIRMED',c['calendar'])
    def test_two_missing_snapshots_are_time_separated(self):
        a=reconcile(snapshot([row(),row(2)]),now=NOW);b=reconcile(snapshot([row(2)]),a,now=NOW)
        c=reconcile(snapshot([row(2)]),b,now=NOW)
        self.assertEqual(c['state']['events']['1']['event']['status'],'active')
        later=NOW+timedelta(hours=1)
        d=reconcile(snapshot([row(2)],later),c,now=later)
        self.assertEqual(d['state']['events']['1']['event']['status'],'cancelled')
    def test_no_cancellation_outside_coverage(self):
        a=reconcile(snapshot([row(),row(2)]),now=NOW)
        s=snapshot([row(2)]);s['windowStart']='2026-10-15T05:00:00Z';s['windowEnd']='2026-11-16T06:00:00Z'
        s['occurrences'][0].update(start='2026-10-16T00:00:00Z',end='2026-10-16T02:00:00Z')
        b=reconcile(s,a,now=NOW);self.assertEqual(b['state']['events']['1']['missingCount'],0)
    def test_failure_preserves_calendar_and_success(self):
        a=reconcile(snapshot(),now=NOW)
        for reason in ['captcha','source_http','incomplete','timeout']:
            b=failure(a,reason,now=NOW+timedelta(hours=3))
            self.assertEqual(a['calendar'],b['calendar']);self.assertEqual(a['state'],b['state'])
            self.assertEqual(b['status']['refreshStatus'],'failed');validate_bundle(b)
    def test_empty_does_not_erase_previous(self):
        with self.assertRaisesRegex(ValueError,'unexpected_empty'):reconcile(snapshot([]),now=NOW)
    def test_incomplete_and_duplicates_rejected(self):
        s=snapshot();s['pagination'].update(pageCount=2,pages=[1])
        with self.assertRaisesRegex(ValueError,'incomplete'):validate_snapshot(s)
        with self.assertRaisesRegex(ValueError,'duplicate'):validate_snapshot(snapshot([row(),row()]))
    def test_mass_removal_rejected(self):
        a=reconcile(snapshot([row(i) for i in range(1,21)]),now=NOW)
        with self.assertRaisesRegex(ValueError,'mass_removal'):reconcile(snapshot([row()]),a,now=NOW)
    def test_scope_change_and_unknown_status_rejected(self):
        s=snapshot();s['scope']['categoryIds']=[4]
        with self.assertRaises(ValueError):validate_snapshot(s)
        r=row();r['status']='mystery'
        with self.assertRaises(ValueError):validate_snapshot(snapshot([r]))
    def test_offset_required(self):
        r=row();r['start']='2026-10-15T00:00:00'
        with self.assertRaisesRegex(ValueError,'missing_offset'):validate_snapshot(snapshot([r]))
    def test_dst_spring_and_fall_are_distinct_instants(self):
        z=ZoneInfo('America/Chicago')
        self.assertEqual(timestamp('2026-11-01T06:30:00Z').astimezone(z).hour,1)
        self.assertEqual(timestamp('2026-11-01T07:30:00Z').astimezone(z).hour,1)
        self.assertNotEqual(timestamp('2026-11-01T06:30:00Z').astimezone(z).utcoffset(),timestamp('2026-11-01T07:30:00Z').astimezone(z).utcoffset())
        self.assertEqual(timestamp('2026-03-08T07:30:00Z').astimezone(z).hour,1)
        self.assertEqual(timestamp('2026-03-08T08:30:00Z').astimezone(z).hour,3)
    def test_utf8_octet_folding_and_injection_escaping(self):
        r=row();r['title']='🧗 café, x; y '+('é'*100)+'\nEND:VEVENT'
        b=reconcile(snapshot([r]),now=NOW)
        self.assertTrue(all(len(x.encode())<=75 for x in b['calendar'].split('\r\n')))
        self.assertEqual(b['calendar'].count('\r\nEND:VEVENT\r\n'),1)
        self.assertIn('\\nEND:VEVENT',b['calendar'].replace('\r\n ',''))
    def test_sold_out_still_scheduled(self):
        # Availability does not enter normalized event status; active is preserved.
        b=reconcile(snapshot(),now=NOW);self.assertIn('STATUS:CONFIRMED',b['calendar'])
    def test_independent_parser_roundtrip(self):
        import icalendar
        b=reconcile(snapshot(),now=NOW);parsed=icalendar.Calendar.from_ical(b['calendar'])
        events=parsed.walk('VEVENT');self.assertEqual(len(events),1)
        self.assertEqual(str(events[0]['SUMMARY']),row()['title'])
        self.assertEqual(events[0].decoded('DTSTART'),timestamp(row()['start']))
        self.assertEqual(str(events[0]['UID']),'crux-central-booking1@blev.dev')
    def test_bundle_tampering_rejected(self):
        b=reconcile(snapshot(),now=NOW);b['calendar']+='garbage'
        with self.assertRaisesRegex(ValueError,'calendar_integrity'):validate_bundle(b)

if __name__=='__main__':unittest.main()
