# AFS Member Mondays

Subscription: https://blev.dev/afs/calendar.ics. Landing page: https://blev.dev/afs/.

Debian collects official public AFS HTML every six hours and a separate publisher updates the existing website repository's `afs-data` branch. The existing hourly full-site Hugo build stages this feed alongside Crux. No inbound ports, reverse-proxy changes, calendar-account permissions, or new paid service are required.

## Source and selection

The collector reads https://www.austinfilm.org/robots.txt and https://www.austinfilm.org/calendar/, then every future film linked by the calendar. It also rechecks known future films removed from that index. It honors the site's ten-second crawl delay (or a longer advertised delay). A typical 64-page refresh takes about eleven minutes. The source calendar determines the available horizon; no monthly recurrence or unpublished dates are invented. The old `/series/free-member-mondays/` page is not used because it only exposes old films.

A film qualifies only when its main description explicitly says “Member Monday” and names the applicable date. Dates come from that notice; the year and start time come from the corresponding showtime group. Each event uses AFS's Salesforce ticket-instance ID for its persistent UID. Generic membership pricing does not qualify, and other dates for the same film are excluded. Sold-out wording does not imply cancellation. Time is converted using America/Chicago, including daylight-saving transitions. An end time is estimated from the published film runtime; the description identifies that estimate. Unknown runtime means no DTEND.

Ordinary curl is used without custom headers, cookies, authentication, redirects, or retry. Python urllib received 403 in source verification; standard curl returned 200. Any future non-200 response, robots restriction, challenge/unrecognized page, ambiguous date, missing designated showtime, duplicate ID, or incomplete scan preserves the last good calendar and reports a failed refresh. There is no access-control workaround. The collector contains no credentials.

## Changes, removals, and persistence

`/docker/appdata/afs-feed/data/bundle.json` is the sole authoritative state, atomically replaced. Keep it across updates. Unchanged events retain byte-identical ICS, UID, sequence, creation and modification dates. Changes increment SEQUENCE. Explicit source cancellations are retained. A future event absent from two complete checks at least six hours apart is retained as CANCELLED, with a description saying it is no longer listed and should be confirmed with AFS. This requires fetching its original film page successfully and the event remaining within the source calendar's coverage. A 403/404 or parse failure never becomes a cancellation. Events and cancellation tombstones remain for 90 days after the event.

Limitations: this is a conservative HTML parser, not an official AFS API. AFS can change markup or move a notice outside the supported content section; the feed then needs maintenance. Film pages are discovered from the official calendar, so listings absent from both it and previously known state cannot be discovered. Ticket IDs that AFS replaces represent new occurrences; the old ID goes through removal handling. An explicit dated cancellation can reuse an already observed ID when AFS removes its ticket link; ambiguous or undated notices require review. Calendar clients control their own refresh delay.

The landing page computes staleness from lastSuccess (14 hours), so stopped collection, publication or site builds cannot leave a permanent fresh label. The build falls back to the last published validated bundle if the data branch cannot be read; it fails before deployment if neither is valid. Empty calendars are allowed after a complete successful scan, which is normal between announcements.

## Deployment

The authoritative stack is `/docker/docker-compose.yml` (project `docker`). Persistent state is `/docker/appdata/afs-feed/data`, UID/GID 1000, private directory. Build context is `/docker/build/afs-feed`. Integrate `compose.yml`, replacing local tags with the resulting immutable image IDs. `pull_policy: never` prevents blanket image updates from trying to pull local builds.

Both containers run nonroot with a read-only root filesystem, all capabilities dropped, no-new-privileges, default Docker seccomp, bounded logs and a dedicated outbound bridge. Only the publisher mounts the existing website-restricted GitHub token, read-only at `/run/secrets/afs_github_token`. Its existing host path remains `/docker/appdata/crux-feed/secrets/github-token`; no token is copied, printed or embedded. The publisher can only update `bundle.json` on `afs-data` and refuses timestamp/event regression. The token's existing repository-level rights and expiration remain unchanged; renewal is still a user-owned private handoff. There is no Chrome dependency or custom security profile.

1. Run tests and build both images from the pinned Python base digest.
2. Complete one normal collection with `worker.py --once --bootstrap` in an isolated container. Verify output independently and preserve the state.
3. Seed `afs-data/bundle.json` using authorized Git access. Never run code from this branch.
4. Back up the Compose file; validate the candidate and compare expanded existing service definitions without printing credentials. Add only the two AFS services and their bridge.
5. Start only `afs-collector` and `afs-publisher`. Verify a genuine subsequent collection/publisher update.
6. Publish the AFS page and the one added staging step in the existing full-site workflow. Confirm both AFS and Crux and the rest of the site.

Commands from the repository:

```sh
PYTHONPATH=scripts/afs python3 -m unittest discover -s tests/afs -v
# Test-only dependency: icalendar==6.3.2; production Python uses the standard library.
docker build -f deploy/afs/collector.Dockerfile -t local/afs-collector:2026-11-05 .
docker build -f deploy/afs/publisher.Dockerfile -t local/afs-publisher:2026-11-05 .
python3 scripts/afs/stage.py --local-bundle /path/to/bundle.json --output static/afs
hugo
```

For updates, retain state, build reviewed images, update only these image references and run `docker compose up -d --no-deps afs-collector afs-publisher` from `/docker`. To stop: `docker compose stop afs-collector afs-publisher`. To roll back, restore these images and compatible state. Preserve the last public feed and subscriber UIDs; do not delete the data branch as routine rollback. Existing Crux services need no restart or configuration change.

## Backup integration

The existing daily 03:00 America/Chicago backup covers `/docker` and `/home/server`; the collector carries `homelab.backup.pause=true`. The 2026-11-05 backup completed with archive/exit code 0 before this deployment. The new state will be covered by the next run; a separate initial recovery copy is retained with deployment evidence. Publisher access is read-only and does not need pausing. No backup policy is changed.

## Verification and deployment (2026-11-05)

A complete live public scan checked 64 film pages without parsing errors. It found:

- WHITE NIGHTS: November 16, 2026, 7:00 p.m. America/Chicago; ticket `a3CUQ00000ZjWvd2AF`; runtime 101 minutes.
- JIMMY: December 7, 2026, 7:00 p.m. America/Chicago; ticket `a3CUQ00000ZhGRy2AN`; runtime 61 minutes.

The 36 AFS tests and all 32 existing Crux tests pass. An independent icalendar parser accepts the feed. The entire 33-page site builds using production Hugo 0.154.2; both subscription pages and both ICS files are present. The Mac's newer system Hugo 0.161.1 hits a pre-existing RSS template incompatibility, so verification used the exact production binary, with its upstream checksum verified.

The reviewed Compose candidate leaves all 56 existing service definitions unchanged. Private recovery files are at `/docker/backups/afs-feed-20261105T232325Z/`, with a checksummed off-host copy in the task workspace. The approved candidate is installed in the main Compose file; only the two AFS services were started.

The isolated Debian container completed a fresh 64-page scan at **2026-11-05T23:36:00Z**, with two events and no errors. Its ICS bytes and event records matched the first complete scan exactly (stable IDs, SEQUENCE 0, original creation/modification timestamps). The independent parser accepted both events, and the offline container health check passed. ICS SHA-256: `19e5790e24772423fe221ad79e665fb989f0eef77465946623bdc9809f1aa493`.

The temporary test container exited successfully and its network was removed. After explicit user approval, both AFS services were enabled in the main stack. The collector is healthy and the publisher successfully authenticated through its existing read-only secret mount and committed the verified scan to `afs-data`. No credential value was read or copied by the assistant. Every pre-existing running container retained its ID. The verified state is also saved at `/docker/backups/afs-feed-20261105T232325Z/bundle.verified.json` and in the off-host task evidence. Reviewed images: collector `sha256:2518fa8031147e4b2cf0e571f95097688987ce57bb5df03c7a3bc680d97a88af`; publisher `sha256:05a185378ed3ad8c0eb2084328ea902b49fb19ba53a8f90586b8a596117bff50`.

Collection runs every six hours, publication checks every five minutes, and the existing full-site workflow builds hourly (and on main pushes). GitHub scheduling and calendar clients can add delay. The existing website token expiration remains unchanged. The last tested source collection and health check establish successful deployment, not an uptime guarantee.
