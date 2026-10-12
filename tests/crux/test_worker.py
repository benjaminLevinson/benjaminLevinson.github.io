import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from feed import reconcile
from test_feed import snapshot,NOW
import worker
class WorkerTests(unittest.TestCase):
    def test_missing_runtime_keeps_last_good_and_marks_failure(self):
        previous=reconcile(snapshot(),now=NOW)
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'bundle.json';p.write_text(json.dumps(previous))
            with patch.object(worker.subprocess,'run',side_effect=OSError('synthetic missing runtime')):
                result=worker.refresh(p)
            saved=json.loads(p.read_text())
            self.assertEqual(saved['calendar'],previous['calendar'])
            self.assertEqual(saved['state'],previous['state'])
            self.assertEqual(result['status']['refreshStatus'],'failed')
if __name__=='__main__':unittest.main()
