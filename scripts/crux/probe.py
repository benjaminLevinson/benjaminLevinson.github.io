"""One-shot public source feasibility probe. No accounts, bookings or deployment.

Uses stock Playwright Chromium: no cookies, stealth, browser spoofing, proxies,
challenge solving, guessed API requests, or response replay. Captures only normal
page-initiated public responses and redacts response values by allowlist.
"""
import asyncio
import json
import os
import re
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

from playwright.async_api import async_playwright

URL = 'https://crux.portal.approach.app/schedule/embed?categoryIds=4&locationIds=2'
OUT = Path('probe-output')
SAFE_VALUES = {
    'id', 'eventId', 'bookingId', 'locationId', 'categoryId', 'categoryIds',
    'event_id', 'booking_id', 'location_id', 'category_id', 'name', 'title',
    'start', 'end', 'startDate', 'endDate', 'startTime', 'endTime',
    'start_date', 'end_date', 'startsAt', 'endsAt', 'date', 'duration',
    'timezone', 'timeZone', 'time_zone', 'utcOffset', 'offset',
    'total', 'totalCount', 'count', 'page', 'pageSize', 'limit', 'skip',
    'hasMore', 'hasNextPage', 'isLast', 'isCancelled', 'isCanceled', 'status',
}
SENSITIVE = re.compile(r'token|secret|password|cookie|authorization|session|cart|customer|attendee|email|phone|payment|user', re.I)
RELEVANT = re.compile(r'schedule|booking|event|location|categor', re.I)
report = {'url': URL, 'result': 'not_started', 'requests': [], 'public_json': [],
          'snapshots': [], 'denials': [], 'completeness': 'unverified'}
pending = set()


def public_url(url):
    """Drop query values (which may be opaque) and fragment from diagnostics."""
    p = urlsplit(url)
    return {'url': f'{p.scheme}://{p.netloc}{p.path}',
            'query_keys': sorted({k for k, _ in parse_qsl(p.query) if not SENSITIVE.search(k)})}


def sanitize(value, key='', depth=0):
    if depth > 12 or SENSITIVE.search(key):
        return None
    if isinstance(value, dict):
        result = {}
        for k, v in value.items():
            if SENSITIVE.search(k):
                continue
            cleaned = sanitize(v, k, depth + 1)
            if cleaned is not None:
                result[k] = cleaned
        return result or None
    if isinstance(value, list):
        # Prevent oversized artifacts. Array lengths separately disclose truncation.
        return {'array_length': len(value), 'sample': [x for v in value[:100]
                if (x := sanitize(v, key, depth + 1)) is not None]}
    if key not in SAFE_VALUES:
        return None
    if isinstance(value, str):
        if key.endswith('Id') or key in {'id', 'event_id', 'booking_id', 'location_id', 'category_id'}:
            return value if re.fullmatch(r'[0-9-]{1,36}', value) else '[non-numeric id omitted]'
        return value[:250]
    return value if isinstance(value, (int, float, bool)) else None


async def observe(response):
    p = urlsplit(response.url)
    if not (p.hostname or '').endswith('.approach.app'):
        return
    kind = response.request.resource_type
    entry = {**public_url(response.url), 'status': response.status, 'kind': kind}
    if len(report['requests']) < 150:
        report['requests'].append(entry)
    if response.status in (401, 403) and kind in {'document', 'script', 'xhr', 'fetch'}:
        report['denials'].append(entry)
        return
    if not RELEVANT.search(p.path) or SENSITIVE.search(p.path):
        return
    if 'json' not in response.headers.get('content-type', ''):
        return
    try:
        data = await response.json()
        report['public_json'].append({**entry,
            'top_level_keys': list(data)[:80] if isinstance(data, dict) else ['array'],
            'data': sanitize(data)})
    except Exception:
        report['public_json'].append({**entry, 'parse': 'failed'})


def observe_task(response):
    task = asyncio.create_task(observe(response))
    pending.add(task)
    task.add_done_callback(pending.discard)


async def checkpoint(page, label):
    await page.wait_for_timeout(1000)
    if pending:
        await asyncio.gather(*list(pending), return_exceptions=True)
    text = await page.locator('body').inner_text()
    challenged = bool(re.search(r'verify you are human|access denied|just a moment|checking your browser|complete the captcha', text, re.I))
    report['snapshots'].append({'label': label, **public_url(page.url),
        'title': await page.title(), 'public_text': text[:35000],
        'text_truncated': len(text) > 35000,
        'row_count': await page.get_by_role('row').count(),
        'buttons': (await page.get_by_role('button').all_text_contents())[:100]})
    if report['denials'] or challenged:
        report['result'] = 'access_denied_or_challenged'
        return False
    return True


async def run():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        context = await browser.new_context()
        page = await context.new_page()
        page.set_default_timeout(15000)
        page.on('response', observe_task)
        response = await page.goto(URL, wait_until='domcontentloaded', timeout=45000)
        report['document_status'] = response.status if response else None
        if not await checkpoint(page, 'initial'):
            await browser.close()
            return

        # Location selection is a public view preference, not a booking.
        chooser = page.get_by_role('button', name=re.compile(r'^Crux Climbing Center - Central 6015'))
        if await chooser.count():
            await chooser.click()
            await page.get_by_role('button', name='SAVE', exact=True).click()
        try:
            await page.get_by_role('button', name='Events', exact=True).wait_for(timeout=20000)
        except Exception:
            await checkpoint(page, 'schedule_not_ready')
            report['result'] = report['result'] if report['denials'] else 'schedule_not_ready'
            await browser.close()
            return
        if not await checkpoint(page, 'events_loaded'):
            await browser.close()
            return

        await page.get_by_role('button', name='Events', exact=True).click()
        report['category_menu'] = await page.get_by_role('menu').inner_text()
        await page.get_by_role('button', name='Clear', exact=True).click()
        # Adult/public scope; all category identities remain subject to inspection.
        names = ['Yoga Classes', 'Fitness Classes', 'Events', 'All Climbing Lessons',
                 'Bouldering Basics', 'Intro to Kilter Board']
        report['selected_categories'] = []
        for name in names:
            item = page.get_by_role('menuitem', name=name, exact=True)
            if await item.count():
                await item.click()
                report['selected_categories'].append(name)
        await page.get_by_role('button', name='Save', exact=True).click()
        if not await checkpoint(page, 'adult_public_scope'):
            await browser.close()
            return

        # Normal scrolling can reveal pagination requests; stalling alone does not
        # establish completeness. Preserve that distinction in the report.
        seen = set()
        stable = 0
        for round_number in range(20):
            rows = await page.get_by_role('row').all_text_contents()
            old_count = len(seen)
            seen.update(rows)
            stable = stable + 1 if len(seen) == old_count else 0
            report['scroll_rounds'] = round_number + 1
            report['unique_rendered_rows'] = len(seen)
            if stable >= 3 or report['denials']:
                break
            await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            await page.wait_for_timeout(1200)
        report['rendered_rows'] = sorted(seen)[:1000]
        report['scroll_stalled'] = stable >= 3
        if not await checkpoint(page, 'after_scroll'):
            await browser.close()
            return
        # Read-only More Info gives an actual booking URL and any timezone label.
        info = page.get_by_role('button', name='More Info', exact=True)
        if await info.count():
            await info.first.click()
            await checkpoint(page, 'sample_occurrence')
            p = urlsplit(page.url)
            if re.fullmatch(r'/event/\d+/booking/\d+(?:/embed)?', p.path):
                report['sample_booking_url'] = f'https://{p.netloc}{p.path}'
        report['result'] = 'public_schedule_rendered' if not report['denials'] else 'access_denied_or_challenged'
        await browser.close()


async def main():
    OUT.mkdir(exist_ok=True)
    try:
        await run()
    except Exception as error:
        # Do not leak arbitrary request URLs, response payloads or tokens in errors.
        report['result'] = 'probe_error'
        report['error_type'] = type(error).__name__
    finally:
        output = json.dumps(report, indent=2, ensure_ascii=False)
        (OUT / 'public-report.json').write_text(output + '\n')
        summary = ('## Crux public source probe\n\n'
                   f"Result: **{report['result']}**\n\n"
                   f"Document HTTP status: {report.get('document_status')}\n\n"
                   f"Public JSON responses observed: {len(report['public_json'])}\n\n"
                   f"Unique rendered rows: {report.get('unique_rendered_rows', 0)}\n\n"
                   'Complete extraction and source timezone require inspection of the report. '
                   'No booking, sign-in, feed publication, Pages deployment, or newsletter action.\n')
        print(summary)
        if os.environ.get('GITHUB_STEP_SUMMARY'):
            with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as handle:
                handle.write(summary)
        print('PUBLIC_REPORT_BEGIN')
        print(output)
        print('PUBLIC_REPORT_END')


if __name__ == '__main__':
    asyncio.run(main())
