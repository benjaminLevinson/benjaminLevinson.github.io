"""AFS's public HTML, fetched with ordinary curl and robots.txt pacing."""
from __future__ import annotations
import re
import subprocess
import time
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser
from zoneinfo import ZoneInfo

ORIGIN = 'https://www.austinfilm.org'
CALENDAR = ORIGIN + '/calendar/'
TZ = ZoneInfo('America/Chicago')
UTC = timezone.utc
MONTHS = {m.lower(): n for n, m in enumerate(
    ['', 'January', 'February', 'March', 'April', 'May', 'June', 'July',
     'August', 'September', 'October', 'November', 'December']) if m}
MONTHS.update({m[:3]: n for m, n in list(MONTHS.items())})
MONTH_RE = '|'.join(sorted(MONTHS, key=len, reverse=True))
DATE_RE = re.compile(r'\b(' + MONTH_RE + r')\.?\s+(\d{1,2})(?:st|nd|rd|th)?(?:,?\s+(20\d{2}))?\b', re.I)
MEMBER_RE = re.compile(r'\bmember\s+mondays?\b', re.I)
TIME_RE = re.compile(r'\b(\d{1,2}):(\d{2})\s*([AP]M)\b', re.I)
VOID = {'area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'}

class SourceError(ValueError):
    pass

class Node:
    def __init__(self, tag='', attrs=()):
        self.tag, self.attrs, self.children = tag, dict(attrs), []
    def text(self):
        if self.tag in {'script','style'}: return ''
        return ' '.join(c.text() if isinstance(c, Node) else c for c in self.children)
    def has(self, cls):
        return cls in self.attrs.get('class','').split()
    def all(self, tag=None, cls=None):
        result = []
        for child in self.children:
            if isinstance(child, Node):
                if (tag is None or child.tag == tag) and (cls is None or child.has(cls)):
                    result.append(child)
                result.extend(child.all(tag, cls))
        return result

class Document(HTMLParser):
    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.root=Node(); self.stack=[self.root]; self.feed(html)
    def handle_starttag(self, tag, attrs):
        n=Node(tag,attrs); self.stack[-1].children.append(n)
        if tag not in VOID: self.stack.append(n)
    def handle_startendtag(self,tag,attrs):
        self.handle_starttag(tag,attrs)
        if tag not in VOID: self.handle_endtag(tag)
    def handle_endtag(self,tag):
        for i in range(len(self.stack)-1,0,-1):
            if self.stack[i].tag==tag:
                del self.stack[i:]; break
    def handle_data(self,data): self.stack[-1].children.append(data)

def clean(s): return ' '.join(s.split())
def iso(d): return d.astimezone(UTC).isoformat(timespec='seconds').replace('+00:00','Z')
def source_url(url):
    return bool(re.fullmatch(r'https://www\.austinfilm\.org/screening/[a-z0-9-]+/',url))

def inventory(html, today):
    root=Document(html).root
    days=root.all('td', 'c-calendar__day')
    if not days: raise SourceError('calendar_schema')
    dates=[]; urls=set()
    for day in days:
        try: date=datetime.strptime(day.attrs['id'],'%Y%m%d').date()
        except (KeyError, ValueError): raise SourceError('calendar_date')
        dates.append(date)
        if date < today: continue
        for a in day.all('a','afs_screening_link'):
            url=a.attrs.get('href','')
            if not source_url(url): raise SourceError('screening_url')
            urls.add(url)
    if not min(dates)<=today<=max(dates) or not urls or len(urls)>250:
        raise SourceError('calendar_incomplete')
    return sorted(urls), min(dates).isoformat(), max(dates).isoformat()

def parse_film(html, url, known=(), today=None):
    today=today or datetime.now(TZ).date()
    if not source_url(url): raise SourceError('screening_url')
    root=Document(html).root
    contents=root.all(cls='c-screening-content')
    if len(contents)!=1 or not root.all('h1') or not root.all(cls='c-screening-data'):
        raise SourceError('film_schema')
    title=clean(root.all('h1')[0].text())
    paragraphs=contents[0].all('p')
    notices=[clean(p.text()) for p in paragraphs if MEMBER_RE.search(clean(p.text()))]
    if not notices:
        if MEMBER_RE.search(clean(contents[0].text())): raise SourceError('designation_schema')
        return []
    # A designation must name a date. Generic pricing and series labels cannot qualify.
    references=[]
    for notice in notices:
        matches=list(DATE_RE.finditer(notice))
        if not matches: raise SourceError('designation_without_date')
        for m in matches:
            references.append((MONTHS[m[1].lower()],int(m[2]),int(m[3]) if m[3] else None,notice))
    venue=root.all(cls='c-screening__venue-label')
    if len(venue)!=1 or clean(venue[0].text())!='AFS Cinema': raise SourceError('venue_changed')
    # Venue address is published immediately after the venue label.
    meta=root.all(cls='c-screening-meta-wrap')
    address=[clean(p.text()) for p in meta[0].all('p') if re.search(r'Austin,\s*TX',clean(p.text()))]
    if len(address)!=1: raise SourceError('venue_address')
    runtime=clean(root.all(cls='c-screening-data')[0].text())
    duration=re.search(r'(?:(\d+)\s*h\s*)?(\d+)\s*min\b',runtime,re.I)
    minutes=(int(duration[1] or 0)*60+int(duration[2])) if duration else None
    if minutes is not None and not 1<=minutes<=600: raise SourceError('runtime')
    events=[]
    groups=root.all(cls='c-showtime-display')
    matching_dates=set()
    for group in groups:
        try: date=datetime.strptime(group.attrs['id'],'showtime-%Y%m%d').date()
        except (ValueError,KeyError): raise SourceError('showtime_date')
        relevant=[ref for ref in references if ref[:2]==(date.month,date.day) and ref[2] in (None,date.year)]
        if not relevant: continue
        matching_dates.add(date)
        # Avoid attributing an explicitly timed benefit to another showing that day.
        times={m.group(0).replace(' ','').upper() for ref in relevant for m in TIME_RE.finditer(ref[3])}
        links=group.all('a')
        for a in links:
            match=TIME_RE.search(clean(a.text()))
            if not match: continue
            if times and match.group(0).replace(' ','').upper() not in times: continue
            ticket=a.attrs.get('href','')
            idmatch=re.fullmatch(r'https://austinfilmsociety\.(?:my\.salesforce-sites\.com|my\.site\.com)/ticket/#/instances/([a-zA-Z0-9]{15,18})',ticket)
            if not idmatch: raise SourceError('ticket_id')
            hour=int(match[1]); minute=int(match[2])
            if not 1<=hour<=12 or minute>59: raise SourceError('showtime_time')
            hour=hour%12+(12 if match[3].upper()=='PM' else 0)
            start=datetime(date.year,date.month,date.day,hour,minute,tzinfo=TZ)
            cancelled=bool(re.search(r'\bcancel(?:led|ed|lation)\b',clean(group.text()),re.I) or
                           any(re.search(r'\bcancel(?:led|ed|lation)\b',ref[3],re.I) for ref in relevant))
            events.append({'id':idmatch[1], 'title':title, 'start':iso(start),
                           'end':iso(start+timedelta(minutes=minutes)) if minutes else None,
                           'source':url, 'ticket':ticket,
                           'location':'AFS Cinema, '+address[0],
                           'status':'cancelled' if cancelled else 'active'})
    # An explicit dated cancellation can retain a previously observed ticket ID
    # even if AFS has removed that ticket link. Never invent an ID from a date.
    for old in known:
        date=datetime.fromisoformat(old['start'].replace('Z','+00:00')).astimezone(TZ).date()
        if old['id'] in {e['id'] for e in events}: continue
        if any(ref[:2]==(date.month,date.day) and ref[2] in (None,date.year) and
               re.search(r'\bcancel(?:led|ed|lation)\b',ref[3],re.I) for ref in references):
            events.append({**old,'status':'cancelled'})
    # A still-published past notice need not have an upcoming showtime anymore.
    if not events and any((r[2] or today.year,r[0],r[1]) >=
                         (today.year,today.month,today.day) for r in references):
        raise SourceError('designated_showtime_missing')
    if len({e['id'] for e in events})!=len(events): raise SourceError('duplicate_ticket_id')
    return events

class Fetcher:
    def __init__(self): self.last=0; self.delay=10; self.robots=None
    def get(self,url):
        if url!=ORIGIN+'/robots.txt' and url!=CALENDAR and not source_url(url):
            raise SourceError('fetch_url')
        if self.robots is not None and not self.robots.can_fetch('*',url):
            raise SourceError('robots_denied')
        time.sleep(max(0,self.last+self.delay-time.monotonic()))
        self.last=time.monotonic()
        # No forged headers, cookies, authentication, redirects, retry, or challenge bypass.
        r=subprocess.run(['curl','--silent','--show-error','--fail','--max-time','45',
                          '--max-filesize','3000000','--proto','=https','--write-out','\n%{http_code}',url],
                         capture_output=True,timeout=50)
        if r.returncode: raise SourceError('source_http')
        body,code=r.stdout.rsplit(b'\n',1)
        if code!=b'200' or len(body)>3_000_000: raise SourceError('source_http')
        return body.decode('utf-8')
    def start(self):
        text=self.get(ORIGIN+'/robots.txt')
        self.robots=RobotFileParser(); self.robots.parse(text.splitlines())
        self.delay=max(10,self.robots.crawl_delay('*') or 0)
        if self.delay>60: raise SourceError('robots_delay_changed')

def collect(previous=None, fetcher=None, now=None):
    now=now or datetime.now(UTC); today=now.astimezone(TZ).date()
    f=fetcher or Fetcher(); f.start()
    urls,start,end=inventory(f.get(CALENDAR),today)
    # Continue checking known future films even when removed from the calendar.
    if previous:
        urls=sorted(set(urls)|{r['event']['source'] for r in previous['state']['events'].values()
                             if datetime.fromisoformat(r['event']['start'].replace('Z','+00:00'))>=now})
    events=[]
    for url in urls:
        known=[r['event'] for r in previous['state']['events'].values() if r['event']['source']==url] if previous else []
        events.extend(e for e in parse_film(f.get(url),url,known,today)
                      if datetime.fromisoformat(e['start'].replace('Z','+00:00')) >= now-timedelta(days=1))
    if len({e['id'] for e in events})!=len(events): raise SourceError('duplicate_id')
    return {'events':events,'pages':urls,'coverageStart':start,'coverageEnd':end,'collectedAt':iso(datetime.now(UTC))}
