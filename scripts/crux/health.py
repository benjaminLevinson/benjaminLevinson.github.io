from datetime import datetime,timedelta,timezone
from feed import load,validate_bundle,timestamp
b=validate_bundle(load('/data/bundle.json'))
now=datetime.now(timezone.utc)
assert now-timestamp(b['status']['lastAttempt'])<timedelta(hours=3)
assert now-timestamp(b['status']['lastSuccess'])<timedelta(hours=24)
