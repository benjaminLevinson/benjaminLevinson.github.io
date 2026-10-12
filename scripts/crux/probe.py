"""Manual, nondeploying public schedule probe using normal headed Chrome.

No spoofing, stealth, challenge handling, account sign-in, request replay, or
credential capture. The page makes its own requests. Only public calendar fields
are retained; request headers, cookies, storage and API keys are never read.
"""
import asyncio
import json
import os
import re
import shutil
import subprocess
import sys
import traceback
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from playwright.async_api import async_playwright

URL = 'https://www.cruxclimbingcenter.com/central-austin/calendar/'
OUT = Path('probe-output')
SELECTED = {1: 'Yoga Classes', 2: 'Fitness Classes', 4: 'Events',
            5: 'All Climbing Lessons', 8: 'Top Rope Lesson',
            9: 'Rock Climbing Basics', 10: 'Lead Climbing Lesson',
            11: 'Bouldering Basics', 16: 'Intro to Kilter Board'}
report = {'url': URL, 'result': 'not_started', 'requests': [], 'snapshots': [],
          'cal_pages': [], 'categories': [], 'locations': [],
          'selected_categories': SELECTED, 'completeness': 'unverified'}
pending = set()
raw_pages = []
failures = []


def location(x):
    return {k: x[k] for k in ('id', 'name', 'timeZone') if k in x}


def booking(x):
    keys = ('id', 'eventId', 'locationId', 'name', 'status', 'startDT', 'endDT',
            'timeZone', 'isCancelled', 'isCanceled', 'isActive', 'isPublic',
            'isSoldOut', 'soldOut', 'capacity', 'remaining', 'available')
    b = {k: x[k] for k in keys if k in x and isinstance(x[k], (str, int, float, bool, type(None)))}
    b['event'] = {k: x.get('event', {})[k] for k in
                  ('id', 'name', 'timeZone', 'locationId', 'isPublic', 'status')
                  if k in x.get('event', {})}
    b['location'] = location(x.get('location', {}))
    return b


async def observe(r):
    u = urlsplit(r.url)
    kind = r.request.resource_type
    if u.hostname == 'crux.portal.approach.app' and kind in {'document', 'script'}:
        report['requests'].append({'path': u.path, 'kind': kind, 'status': r.status})
        if kind == 'script' and r.status >= 400:
            failures.append('script_http_error')
    if u.hostname != 'widgets.api.prod.tilefive.com' or u.path not in {
        '/cal', '/categories', '/locations', '/locations/2'}:
        return
    if r.status != 200 or 'json' not in r.headers.get('content-type', ''):
        failures.append('calendar_api_http_or_type_error')
        return
    try:
        data = await r.json()
        if u.path in {'/locations', '/locations/2'}:
            for x in data if isinstance(data, list) else [data]:
                if x['id'] == 2:
                    report['locations'].append(location(x))
        elif u.path == '/categories':
            report['categories'] = [location(x) for x in data['data']]
            report['category_pagination'] = data.get('pagination')
        else:
            query = {k: v for k, v in parse_qs(u.query).items()
                     if k in {'startDT', 'endDT', 'locationId', 'categoryId', 'page', 'pageSize'}}
            # Store the ordinary response's pagination object: no headers or keys.
            entry = {'query': query, 'pagination': data.get('pagination'),
                     'cal_event_count': len(data['calEvents']),
                     'booking_count': len(data['bookings']),
                     'booking_field_names': sorted(data['bookings'][0]) if data['bookings'] else [],
                     'bookings': [booking(x) for x in data['bookings']]}
            report['cal_pages'].append(entry)
            raw_pages.append(entry)
    except Exception:
        failures.append('public_response_schema_error')


def observe_task(r):
    t = asyncio.create_task(observe(r))
    pending.add(t)
    t.add_done_callback(pending.discard)


async def settle(page):
    await page.wait_for_timeout(1500)
    if pending:
        await asyncio.gather(*list(pending), return_exceptions=True)


async def snapshot(frame, label):
    text = await frame.locator('body').inner_text(timeout=10000)
    report['snapshots'].append({'label': label, 'public_text': text[:35000],
                              'row_count': await frame.get_by_role('row').count(),
                              'buttons': (await frame.get_by_role('button').all_text_contents())[:80]})
    if re.search(r'verify you are human|access denied|just a moment|complete the captcha', text, re.I):
        raise RuntimeError('interactive_access_challenge')


def matching_pages():
    expected = set(SELECTED)
    matches = []
    for p in raw_pages:
        cats = {int(n) for value in p['query'].get('categoryId', []) for n in value.split(',') if n.isdigit()}
        if cats == expected and p['query'].get('locationId') == ['2']:
            matches.append(p)
    return matches


def complete(pages):
    if not pages:
        return False
    # Evidence is retained even if upstream uses a different terminal schema.
    latest = {int(p['query'].get('page', ['0'])[0]): p for p in pages}
    if sorted(latest) != list(range(1, max(latest)+1)):
        return False
    last = latest[max(latest)]
    pg = last['pagination'] or {}
    terminal = (pg.get('hasNextPage') is False or pg.get('hasMore') is False
                or pg.get('isLast') is True
                or isinstance(pg.get('totalPages'), int) and max(latest) >= pg['totalPages'])
    # Do not equate DOM stalling or a short page with proven completeness.
    if not terminal:
        return False
    ids = [b['id'] for p in latest.values() for b in p['bookings']]
    if len(ids) != len(set(ids)):
        raise RuntimeError('duplicate_occurrence_pages')
    return True


async def run():
    chrome = shutil.which('google-chrome') or shutil.which('google-chrome-stable')
    if not chrome:
        raise RuntimeError('installed_chrome_missing')
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False, executable_path=chrome)
        report['browser_version'] = browser.version
        report['browser_mode'] = 'headed_xvfb_fresh_context'
        context = await browser.new_context()
        page = await context.new_page()
        page.set_default_timeout(20000)
        page.on('response', observe_task)
        try:
            r = await page.goto(URL, wait_until='domcontentloaded', timeout=45000)
            report['parent_document_status'] = r.status
            await page.locator('iframe[src*="crux.portal.approach.app"]').wait_for()
            iframe = page.frame_locator('iframe[src*="crux.portal.approach.app"]')
            frame = next((f for f in page.frames() if 'crux.portal.approach.app' in f.url), None)
            if frame is None:
                raise RuntimeError('schedule_frame_missing')
            await settle(page)
            chooser = iframe.get_by_role('button', name=re.compile(r'^Crux Climbing Center - Central'))
            await chooser.wait_for(timeout=45000)
            await chooser.click()
            await iframe.get_by_role('button', name='Save', exact=True).click()
            try:
                await iframe.get_by_role('button', name='Events', exact=True).wait_for(timeout=60000)
            except Exception:
                await snapshot(frame, 'schedule_not_ready')
                raise
            await settle(page)
            await snapshot(frame, 'events_loaded')
            await iframe.get_by_role('button', name='Events', exact=True).click()
            await snapshot(frame, 'category_menu')
            await iframe.get_by_role('button', name='Clear', exact=True).click()
            for name in SELECTED.values():
                await iframe.get_by_role('menuitem', name=re.compile('^'+re.escape(name)+r'\s*$')).click()
            await iframe.get_by_role('button', name='Save', exact=True).click()
            await settle(page)
            await snapshot(frame, 'selected_categories')
            report['selected_frame_url'] = frame.url
            if failures:
                raise RuntimeError('source_response_failure')
            for index in range(80):
                if complete(matching_pages()):
                    break
                rows = frame.get_by_role('row')
                if await rows.count():
                    await rows.last.scroll_into_view_if_needed()
                await frame.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                # Parent page can own the scroll for an auto-sized embedded app.
                await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                await settle(page)
                if failures:
                    raise RuntimeError('source_response_failure')
                if index >= 4 and len(matching_pages()) == 1:
                    break
            await snapshot(frame, 'after_pagination')
            pages = matching_pages()
            report['completeness'] = 'verified' if complete(pages) else 'unverified'
            report['selected_page_count'] = len(pages)
            report['source_timezone_verified'] = any(x.get('timeZone') == 'America/Chicago' for x in report['locations'])
            report['result'] = 'complete_public_snapshot' if report['completeness'] == 'verified' else 'public_schedule_rendered_completion_unverified'
        finally:
            for f in page.frames():
                if 'crux.portal.approach.app' in f.url:
                    try:
                        await snapshot(f, 'final_state')
                    except Exception:
                        pass
            await settle(page)
            report['failures'] = failures
            await browser.close()


async def main():
    OUT.mkdir(exist_ok=True)
    try:
        await run()
    except Exception as e:
        report['result'] = 'probe_error'
        report['error_type'] = type(e).__name__
        report['error_locations'] = [{'file': Path(f.filename).name, 'line': f.lineno, 'function': f.name} for f in traceback.extract_tb(e.__traceback__)]
        # Include only our own fixed identifiers, never arbitrary browser errors.
        if type(e) is RuntimeError and re.fullmatch('[a-z_]+', str(e)):
            report['error_code'] = str(e)
    (OUT/'public-report.json').write_text(json.dumps(report, indent=2)+'\n')
    summary = (f"## Crux corrected public-source probe\n\nResult: **{report['result']}**\n\n"
               f"Browser: {report.get('browser_version')} (headed, fresh context)\n\n"
               f"Calendar responses: {len(report['cal_pages'])}; completeness: {report['completeness']}\n\n"
               "No booking, account sign-in, deployment, API-key capture or request replay.\n")
    print(summary)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as f:
            f.write(summary)
    return 0 if report['result'] == 'complete_public_snapshot' else 2


if __name__ == '__main__':
    if not os.environ.get('DISPLAY'):
        if not shutil.which('xvfb-run'):
            raise SystemExit('Xvfb is required; no headless fallback.')
        raise SystemExit(subprocess.call(['xvfb-run', '-a', sys.executable, __file__]))
    raise SystemExit(asyncio.run(main()))
