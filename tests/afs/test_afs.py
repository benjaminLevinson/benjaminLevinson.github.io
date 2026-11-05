import copy
import json
import tempfile
import unittest
from datetime import datetime,timedelta,timezone,date
from pathlib import Path
from unittest.mock import patch
from icalendar import Calendar
import feed
import source
import worker
import stage
import publisher

URL=source.ORIGIN+'/screening/white-nights/'
HTML=(Path(__file__).parent/'fixtures/white-nights.html').read_text()
NOW=datetime(2026,11,5,23,tzinfo=timezone.utc)

def snapshot(events=None,now=NOW):
    return {'events':source.parse_film(HTML,URL) if events is None else events,'pages':[URL],
            'coverageStart':'2026-11-01','coverageEnd':'2026-12-31','collectedAt':source.iso(now)}
def bundle(): return feed.reconcile(snapshot(),now=NOW)

class Parsing(unittest.TestCase):
    def test_designated_date_not_all_showings(self):
        events=source.parse_film(HTML,URL)
        self.assertEqual(len(events),1)
        self.assertEqual(events[0]['id'],'a3CUQ00000ZjWvd2AF')
        self.assertEqual(events[0]['start'],'2026-11-17T01:00:00Z')
        self.assertEqual(events[0]['end'],'2026-11-17T02:41:00Z')
    def test_ordinary_membership_pricing_not_included(self):
        self.assertEqual(source.parse_film(HTML.replace('Free Member Monday','Free for LOVE members'),URL),[])
    def test_designation_requires_date(self):
        with self.assertRaises(source.SourceError):source.parse_film(HTML.replace('Monday, November 16','members'),URL)
    def test_unknown_markup_fails(self):
        with self.assertRaises(source.SourceError):source.parse_film('<html>Denied</html>',URL)
    def test_cancellation_not_sold_out(self):
        html=HTML.replace('Free Member Monday','Cancelled: Free Member Monday')
        self.assertEqual(source.parse_film(html,URL)[0]['status'],'cancelled')
        html=HTML.replace('Free Member Monday','Sold out: Free Member Monday')
        self.assertEqual(source.parse_film(html,URL)[0]['status'],'active')
    def test_explicit_cancellation_retains_removed_ticket_id(self):
        known=source.parse_film(HTML,URL)
        html=HTML.replace('Free Member Monday','Cancelled: Free Member Monday').replace('7:00 PM','Tickets removed')
        result=source.parse_film(html,URL,known)
        self.assertEqual(result,[{**known[0],'status':'cancelled'}])
    def test_daylight_savings(self):
        summer=HTML.replace('20261116','20260706').replace('November 16','July 6')
        self.assertEqual(source.parse_film(summer,URL)[0]['start'],'2026-07-07T00:00:00Z')
    def test_runtime_unknown_omits_end(self):
        self.assertIsNone(source.parse_film(HTML.replace('1h 41min','runtime TBA'),URL)[0]['end'])
    def test_unknown_ticket_url_rejected(self):
        with self.assertRaises(source.SourceError):source.parse_film(HTML.replace('austinfilmsociety.my.salesforce-sites.com','other.example'),URL)
    def test_calendar_shape_and_source_url(self):
        html=f'<td id="20261105" class="c-calendar__day"><a class="afs_screening_link" href="{URL}">film</a></td>'
        self.assertEqual(source.inventory(html,date(2026,11,5))[0],[URL])
        with self.assertRaises(source.SourceError):source.inventory(html,date(2026,12,1))
        with self.assertRaises(source.SourceError):source.inventory(html.replace(URL,'https://other.example/'),date(2026,11,5))

class State(unittest.TestCase):
    def test_real_ics_parser(self):
        c=Calendar.from_ical(bundle()['calendar']);events=c.walk('VEVENT')
        self.assertEqual(len(events),1)
        self.assertEqual(str(events[0]['UID']),'afs-a3CUQ00000ZjWvd2AF@blev.dev')
        self.assertEqual(events[0].decoded('DTSTART'),datetime(2026,11,17,1,tzinfo=timezone.utc))
    def test_unchanged_event_keeps_sequence_and_calendar(self):
        b=bundle();later=NOW+timedelta(hours=7)
        self.assertEqual(feed.reconcile(snapshot(now=later),b,later)['calendar'],b['calendar'])
    def test_reschedule_keeps_uid_increments_sequence(self):
        b=bundle();s=snapshot();s['events'][0]['start']='2026-11-17T02:00:00Z';s['events'][0]['end']='2026-11-17T03:41:00Z'
        c=Calendar.from_ical(feed.reconcile(s,b,NOW)['calendar']).walk('VEVENT')[0]
        self.assertEqual(str(c['UID']),'afs-a3CUQ00000ZjWvd2AF@blev.dev');self.assertEqual(int(c['SEQUENCE']),1)
    def test_cancellation_and_reactivation(self):
        b=bundle();s=snapshot();s['events'][0]['status']='cancelled'
        cancelled=feed.reconcile(s,b,NOW)
        self.assertIn('STATUS:CANCELLED',cancelled['calendar'])
        active=feed.reconcile(snapshot(),cancelled,NOW)
        self.assertIn('STATUS:CONFIRMED',active['calendar']);self.assertIn('SEQUENCE:2',active['calendar'])
    def test_two_separated_complete_checks_for_removal(self):
        b=bundle();s=snapshot([]);one=feed.reconcile(s,b,NOW)
        self.assertIn('STATUS:CONFIRMED',one['calendar'])
        two=feed.reconcile(s,one,NOW);self.assertIn('STATUS:CONFIRMED',two['calendar'])
        later=NOW+timedelta(hours=6);two=feed.reconcile(snapshot([],later),two,later)
        self.assertIn('STATUS:CANCELLED',two['calendar']);self.assertIn('SEQUENCE:1',two['calendar'])
    def test_absence_outside_coverage_or_unfetched_page_preserved(self):
        for kind in ('window','page'):
            b=bundle();s=snapshot([])
            if kind=='window':s['coverageEnd']='2026-11-10'
            else:s['pages']=['https://www.austinfilm.org/screening/another/']
            one=feed.reconcile(s,b,NOW);later=NOW+timedelta(hours=7);s['collectedAt']=source.iso(later)
            self.assertIn('STATUS:CONFIRMED',feed.reconcile(s,one,later)['calendar'])
    def test_failure_preserves_calendar_and_success(self):
        b=bundle();f=feed.failure(b,'source_http',NOW+timedelta(hours=1))
        self.assertEqual(b['state'],f['state']);self.assertEqual(b['calendar'],f['calendar']);self.assertEqual(f['status']['refreshStatus'],'failed')
    def test_empty_verified_schedule_valid(self):
        b=feed.reconcile(snapshot([]),now=NOW);self.assertEqual(Calendar.from_ical(b['calendar']).walk('VEVENT'),[])
    def test_duplicate_id_and_tamper_rejected(self):
        s=snapshot();s['events']*=2
        with self.assertRaises(ValueError):feed.reconcile(s,now=NOW)
        b=bundle();b['calendar']+='BEGIN:VEVENT'
        with self.assertRaises(ValueError):feed.validate_bundle(b)
    def test_unicode_and_ics_folding(self):
        s=snapshot();s['events'][0]['title']='Été; test, 漢字 '*30
        b=feed.reconcile(s,now=NOW)
        self.assertTrue(all(len(l.encode())<=75 for l in b['calendar'].split('\r\n')))
        self.assertIn(s['events'][0]['title'],str(Calendar.from_ical(b['calendar']).walk('VEVENT')[0]['SUMMARY']))

class Operation(unittest.TestCase):
    def test_worker_partial_failure_is_atomic(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'bundle.json';feed.atomic(p,json.dumps(bundle()))
            def failed(_):raise source.SourceError('source_http')
            b=worker.refresh(p,collector=failed)
            self.assertEqual(b['calendar'],bundle()['calendar']);self.assertEqual(feed.load(p),b)
    def test_stage_falls_back_to_last_good(self):
        with tempfile.TemporaryDirectory() as d,patch.object(stage,'fetch',side_effect=[ValueError(),bundle()]) as f:
            stage.stage(d)
            self.assertEqual(f.call_count,2)
            self.assertEqual((Path(d)/'calendar.ics').read_bytes(),bundle()['calendar'].encode())
    def test_stage_fails_closed(self):
        with tempfile.TemporaryDirectory() as d,patch.object(stage,'fetch',side_effect=ValueError()):
            with self.assertRaises(RuntimeError):stage.stage(d)
            self.assertEqual(list(Path(d).iterdir()),[])
    def test_publisher_bounded_target_and_no_redirect(self):
        self.assertEqual(publisher.BRANCH,'afs-data')
        self.assertEqual(publisher.ENDPOINT,'https://api.github.com/repos/benjaminLevinson/benjaminLevinson.github.io/contents/bundle.json')
        self.assertIsNone(publisher.NoRedirect().redirect_request(None,None,None,None,None,None))

if __name__=='__main__':unittest.main()
