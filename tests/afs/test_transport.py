import subprocess
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from source import Fetcher,SourceError,ORIGIN

class TransportTests(unittest.TestCase):
    @patch('source.time.sleep')
    @patch('source.subprocess.run')
    def test_plain_curl_success_no_custom_headers_or_redirects(self,run,sleep):
        run.return_value=SimpleNamespace(returncode=0,stdout=b'User-agent: *\nCrawl-delay: 12\n\n200')
        f=Fetcher();f.start()
        self.assertEqual(f.delay,12)
        command=run.call_args.args[0]
        self.assertEqual(command[0],'curl');self.assertEqual(command[-1],ORIGIN+'/robots.txt')
        for forbidden in ('-A','--user-agent','-H','--header','-L','--location','--cookie','--retry'):
            self.assertNotIn(forbidden,command)
    @patch('source.time.sleep')
    @patch('source.subprocess.run')
    def test_http_denial_aborts_without_retry(self,run,sleep):
        run.return_value=SimpleNamespace(returncode=22,stdout=b'\n403')
        with self.assertRaisesRegex(SourceError,'source_http'):Fetcher().start()
        self.assertEqual(run.call_count,1)
    @patch('source.time.sleep')
    @patch('source.subprocess.run')
    def test_redirect_rejected(self,run,sleep):
        run.return_value=SimpleNamespace(returncode=0,stdout=b'Redirect\n301')
        with self.assertRaisesRegex(SourceError,'source_http'):Fetcher().start()
    @patch('source.time.sleep')
    @patch('source.subprocess.run')
    def test_robots_denial_prevents_fetch(self,run,sleep):
        run.return_value=SimpleNamespace(returncode=0,stdout=b'User-agent: *\nDisallow: /calendar/\n\n200')
        f=Fetcher();f.start()
        with self.assertRaisesRegex(SourceError,'robots_denied'):f.get(ORIGIN+'/calendar/')
        self.assertEqual(run.call_count,1)
    def test_unknown_url_rejected_before_fetch(self):
        with self.assertRaises(SourceError):Fetcher().get('https://example.com/')
