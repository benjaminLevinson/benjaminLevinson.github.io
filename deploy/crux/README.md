# Crux Central hybrid feed — prepared, not enabled

The collector uses normal headed Chrome under Xvfb. It observes only page-initiated public calendar responses; it never reads/reuses API keys, cookies, or browser storage, never solves a challenge, and never uses FlareSolverr, stealth, or proxies. Chrome's sandbox stays enabled. Unknown schema, CAPTCHA, failed HTTP requests, incomplete pagination, unexpectedly empty results, and large unexplained removals preserve the previous ICS and update freshness status.

## Source contract

Central location 2, America/Chicago; category IDs 1, 2, 4, 5, 8, 9, 10, 11, 16. The bounded window is the source UI's rolling month, including its selected final day. Pagination must contain every page with stable pageCount/rowCount and unique booking IDs. Actual booking instances become VEVENTs; there are no guessed RRULEs. Non-booking calendar records or all-day records currently stop collection for schema review, never disappear silently.

Host-browser verification observed 164 bookings across four pages on 2026-10-12. Two successive host refreshes retained identical IDs and sequences. After the user approved the namespace profile and an additional collector-only `chroot` syscall allowance, the rebuilt container completed a fresh full collection: 163 source bookings across all four pages at 2026-10-12T16:29:22Z. The generated ICS retained 164 unique events; one earlier booking no longer returned by the source was retained without guessing cancellation. Central location, all nine selected categories and America/Chicago were verified. An independent ICS parser accepted the calendar.

The verified container retained nonroot UID 1000, all capabilities dropped, no-new-privileges, read-only root, private IPC and Chrome's sandbox. It had only a temporary public-data mount, an isolated outbound bridge and no credentials or inbound ports. The health check passed without network. An intentional missing-browser failure on a separate state copy retained exact calendar/state and lastSuccess while updating failed status. Temporary containers and the test network were removed; production remains unchanged. This is a verified run, not an uptime guarantee. Cancellation, moved-event and sold-out behavior is covered by fixtures; no real bookings were modified. A standard GitHub-hosted headed Chrome run separately encountered explicit AWS WAF CAPTCHA.

## Public files and state

The data branch `crux-data` contains only a validated `bundle.json` (public occurrence fields, update state, status, and ICS). Hugo's full-site build stages `/crux/calendar.ics`, `/crux/state.json`, `/crux/status.json`, `/crux/bundle.json`, and `/crux/index.html`. The landing page computes staleness from lastSuccess, so a stopped collector or publisher cannot leave a permanent “fresh” label.

Booking IDs form stable UIDs. Event changes increment SEQUENCE. Source cancellation is retained explicitly; disappearance requires two complete overlapping snapshots at least 30 minutes apart. Large removals stop for review. Missing entries outside coverage are not cancelled. Past active entries age out after 30 days; cancellation tombstones after 90 days past the event. Capacity/sold-out values never imply cancellation.

## Approved collector sandbox profile

The default Docker policy denied Chrome's sandbox namespace creation. The original `seccomp.proposed.json` is Microsoft's Playwright v1.58.2 `utils/docker/seccomp_profile.json`, with its Apache license in `seccomp.LICENSE`. It retains a deny-by-default syscall policy and allows `clone`, `setns`, and `unshare`. Source: https://github.com/microsoft/playwright/blob/v1.58.2/utils/docker/seccomp_profile.json . Its approved test reached Chrome's `chroot` step, which was still denied because that profile gates it on CAP_SYS_CHROOT and all container capabilities are dropped.

The user then explicitly approved the collector-only additional `chroot` allowance in `seccomp-chroot.proposed.json`. It differs semantically from the original profile by exactly one unconditional `chroot` allow rule and adds no container capabilities. Its historical “PROPOSED ONLY” comment is retained so the reviewed and tested file has identical bytes. Sandboxed Chrome launch and full collection now pass. Use this tested profile for the collector only; the publisher keeps Docker's default seccomp policy. Kernel capability checks still apply.

Keep nonroot UID 1000, all capabilities dropped, no-new-privileges, read-only root, private IPC, no exposed ports, and no collector credential mount. Do not use privileged, SYS_ADMIN, seccomp=unconfined, host networking/IPC, or disable Chrome sandbox. Any further security exception needs separate approval. No further exception was required by the successful test.

## Publication permission gate

The user approved a fine-grained GitHub token selecting only `benjaminLevinson/benjaminLevinson.github.io`, with Contents read/write, automatic Metadata read, and a 90-day expiration. No Actions, Workflows, administration, or other-repository permission. GitHub does not restrict this token to a branch or filename: compromise can modify repository contents beyond the intended data file. Consider a separately reviewed GitHub App if shorter-lived tokens are desired.

The user must perform creation, entry and storage through a private terminal handoff. The assistant must never read, paste, log, transmit or store the token. `enter-publisher-token.py` is a user-run helper: it requires a TTY, disables echo, refuses a preexisting destination, creates a private 0700 directory and an exclusive 0600 file, and prints no credential. It does not validate remote scopes or make network requests. Do not invoke this helper through assistant tools.

User handoff: open GitHub Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate new token. Use name `Crux calendar publisher`, resource owner `benjaminLevinson`, 90 days, **Only select repositories**, and only `benjaminLevinson.github.io`. Grant Contents read/write and automatic Metadata read; leave all other permissions unset. The user generates the token and runs this helper in their own private interactive SSH terminal, passing the private destination file as its only argument. Paste only at the hidden prompt, never into chat, a command line, or an assistant terminal. The helper does not start publication. Official setup reference: https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens .

Keep the token in a private mode-0600 file mounted read-only only into the publisher. The collector container must never receive it. No token values go into git, environment logs, scripts, image layers, wiki, or chat. Do not extract/copy an existing broader credential. The publisher uses a fixed repository, branch and file; it validates the bundle, rejects state regression, and supplies the current blob SHA for conflict protection. It cannot create branches and assumes the initial data branch/file has been deliberately seeded.

## Activation sequence after approval

1. The approved `seccomp-chroot.proposed.json` passed isolated container verification. Set CRUX_SECCOMP_FILE to its installed private host path, verify the hash below, and retain every tested protection. Do not apply any further security exception without approval.
2. Build reviewed images pinned by digest/content hash. Integrate `compose.proposed.yml` into the existing authoritative stack, with private local paths. No ports, proxy routes, host networking, Docker socket, home-directory mount, or public inbound access are needed.
3. Seed the persistent bundle from a fresh verified collection. Preserve that state across updates to retain sequence/cancellation history. Start only the target services. Backup setup is intentionally skipped; existing backups remain untouched.
4. With existing user-authorized GitHub access, deliberately initialize the `crux-data` branch and its public bundle. Supply the separately approved token privately to the publisher, then verify its bounded update and failure behavior.
5. Replace the main full-site workflow with the reviewed `hugo-workflow.proposed.yml` and remove the landing page's `draft: true`. The candidate adds hourly `17 * * * *`, stages the validated bundle before Hugo, and guards Buttondown to main pushes only. Do not deploy a feed-only Pages artifact.
6. Confirm the production run finishes, existing pages remain, exact ICS bytes match, status is fresh, HTTPS works, and the source links/timezone/DST sample matches. No calendar-account write is necessary.

## Failure and rollback

Collector failure updates only status; ICS and lastSuccess remain unchanged. Publisher failure keeps the last public data commit. Site staging falls back to the last published validated bundle; if neither source is valid, it stops before deployment. GitHub schedule delivery is not guaranteed and public-repository schedules may disable after 60 days of inactivity. No artificial keepalive commits are added.

Stop only these services to pause collection/publication. Retain private state. Revert the workflow and page activation change if needed, preserving the last published feed while subscribers transition. Do not delete the data branch or state as a routine rollback. No existing homelab service or FlareSolverr configuration needs modification.

## Validation commands

```sh
PYTHONPATH=scripts/crux python3 -m unittest discover -s tests/crux -v
node --test tests/crux/test_collector.cjs
python3 scripts/crux/stage.py --local-bundle /path/to/verified/bundle.json --output static/crux
hugo --buildDrafts
```

32 local tests pass (26 Python and 6 Node), including independent ICS parsing, stable updates, removal guards, incomplete source rejection, publication fallback, and bounded publisher requests. Tests require `icalendar==6.3.2` as an independent parser. Production Python code uses the standard library. Playwright is locked to 1.58.2; Chrome's tested installed release is 154.0.8037.97. No source data or credential is packaged in the images.

Original profile SHA-256: `cc3e61cabda6bbc1e53e54d27ba4d55a9d3be829b6dd1a596f4a7b31b1cc7849` (namespace-only test failed at chroot).

Approved and successfully tested profile SHA-256: `0d5adedfcce51f0a6ddaf0f27ed9084f606efcd7e5bd459554ed6c1d6d69ba0f` (`seccomp-chroot.proposed.json`). Current collector image built from application code at `5f0bc4d`: `sha256:46854e33e6ef415c869aa410a0ee6acbc9ac0683e35eec5972803d58f6f425ef`. Production activation and user token handoff remain incomplete.
