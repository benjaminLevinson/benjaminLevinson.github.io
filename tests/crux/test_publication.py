import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from feed import reconcile,validate_bundle
from test_feed import snapshot,NOW
import stage

class PublicationTests(unittest.TestCase):
    def test_data_failure_uses_validated_last_good(self):
        b=reconcile(snapshot(),now=NOW)
        with tempfile.TemporaryDirectory() as d,patch.object(stage,'fetch',side_effect=[ValueError('bad'),b]) as fetch:
            stage.stage(d)
            self.assertEqual((Path(d)/'calendar.ics').read_bytes(),b['calendar'].encode())
            self.assertEqual(fetch.call_count,2)
            validate_bundle(json.loads((Path(d)/'bundle.json').read_text()))
    def test_no_valid_bundle_aborts_without_writing(self):
        with tempfile.TemporaryDirectory() as d,patch.object(stage,'fetch',side_effect=ValueError('bad')):
            with self.assertRaisesRegex(RuntimeError,'No validated feed'):stage.stage(d)
            self.assertEqual(list(Path(d).iterdir()),[])
    def test_local_bundle_requires_integrity(self):
        b=reconcile(snapshot(),now=NOW);b['status']['feedCount']=500
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'bad.json';p.write_text(json.dumps(b))
            with self.assertRaises(ValueError):stage.stage(Path(d)/'out',p)
            self.assertFalse((Path(d)/'out').exists())
    def test_workflow_candidate_preserves_full_site_and_newsletter_guard(self):
        text=Path(__file__).resolve().parents[2].joinpath('deploy/crux/hugo-workflow.proposed.yml').read_text()
        self.assertIn('path: ./public',text)
        self.assertIn("if: github.event_name == 'push' && github.ref == 'refs/heads/main'",text)
        self.assertLess(text.index('Stage validated Crux feed'),text.index('name: Build the site'))
        self.assertNotIn('contents: write',text)
        self.assertIn('group: pages',text)

if __name__=='__main__':unittest.main()
