from datetime import datetime,timedelta,timezone
from feed import load,timestamp
b=load('/data/bundle.json')
assert datetime.now(timezone.utc)-timestamp(b['status']['lastSuccess'])<timedelta(hours=14)
assert b['status']['refreshStatus']=='ok'
