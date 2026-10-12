import base64
import json
import tempfile
import unittest
from pathlib import Path
from datetime import timedelta
from unittest.mock import patch
from feed import reconcile,failure
from test_feed import snapshot,NOW
import publisher
class Response:
    status=200
    def __init__(self,body):self.body=body
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def read(self,*args):return json.dumps(self.body).encode()
class FakeOpener:
    def __init__(self,previous):self.previous=previous;self.requests=[]
    def open(self,request,**kwargs):
        self.requests.append(request)
        if request.get_method()=='GET':return Response({'sha':'known-current-blob','content':base64.b64encode(json.dumps(self.previous).encode()).decode()})
        return Response({})
class PublisherTests(unittest.TestCase):
    def setup_files(self,d,b):
        p=Path(d);(p/'bundle').write_text(json.dumps(b));(p/'token').write_text('test-placeholder-not-a-credential');return p/'bundle',p/'token'
    def test_only_fixed_data_path_and_branch_with_conflict_sha(self):
        old=reconcile(snapshot(),now=NOW);new=failure(old,'captcha',NOW+timedelta(hours=1));op=FakeOpener(old)
        with tempfile.TemporaryDirectory() as d,patch.object(publisher,'build_opener',return_value=op):
            paths=self.setup_files(d,new);self.assertEqual(publisher.publish(*paths),'published')
        self.assertEqual(len(op.requests),2)
        request=op.requests[1];body=json.loads(request.data)
        self.assertEqual(request.full_url,publisher.ENDPOINT)
        self.assertEqual(body['branch'],'crux-data');self.assertEqual(body['sha'],'known-current-blob')
        self.assertNotIn('test-placeholder',request.data.decode())
        self.assertEqual(json.loads(base64.b64decode(body['content'])),new)
    def test_regression_rejected_without_put(self):
        old=reconcile(snapshot(),now=NOW);new=failure(old,'captcha',NOW+timedelta(hours=1));op=FakeOpener(new)
        with tempfile.TemporaryDirectory() as d,patch.object(publisher,'build_opener',return_value=op):
            with self.assertRaisesRegex(ValueError,'regression'):publisher.publish(*self.setup_files(d,old))
        self.assertEqual(len(op.requests),1)
    def test_unchanged_bundle_no_commit(self):
        b=reconcile(snapshot(),now=NOW);op=FakeOpener(b)
        with tempfile.TemporaryDirectory() as d,patch.object(publisher,'build_opener',return_value=op):
            self.assertEqual(publisher.publish(*self.setup_files(d,b)),'unchanged')
        self.assertEqual(len(op.requests),1)
    def test_missing_token_no_network(self):
        b=reconcile(snapshot(),now=NOW)
        with tempfile.TemporaryDirectory() as d,patch.object(publisher,'build_opener') as builder:
            bundle,token=self.setup_files(d,b);token.unlink()
            with self.assertRaises(FileNotFoundError):publisher.publish(bundle,token)
            builder.assert_not_called()
    def test_authenticated_redirect_not_followed(self):
        self.assertIsNone(publisher.NoRedirect().redirect_request(None,None,None,None,None,None))
if __name__=='__main__':unittest.main()
