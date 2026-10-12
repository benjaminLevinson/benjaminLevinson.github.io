# Crux Central hybrid feed — prepared, not enabled

The collector uses normal headed Chrome under Xvfb. It observes only page-initiated public calendar responses; it never reads/reuses API keys, cookies, or browser storage, never solves a challenge, and never uses FlareSolverr, stealth, or proxies. Chrome's sandbox stays enabled. Unknown schema, CAPTCHA, failed HTTP requests, incomplete pagination, unexpectedly empty results, and large unexplained removals preserve the previous ICS and update freshness status.

## Source contract

Central location 2, America/Chicago; category IDs 1, 2, 4, 5, 8, 9, 10, 11, 16. The bounded window is the source UI's rolling month, including its selected final day. Pagination must contain every page with stable pageCount/rowCount and unique booking IDs. Actual booking instances become VEVENTs; there are no guessed RRULEs. Non-booking calendar records or all-day records currently stop collection for schema review, never disappear silently.

The complete normal-browser diagnostic observed 164 bookings across four pages on 2026-10-12. The observed bookings were active; cancellation, disappearance, moved-event, and sold-out behavior is validated with controlled fixtures, not by modifying real Crux bookings. This is one verified snapshot, not an uptime guarantee. A standard GitHub-hosted headed Chrome run separately encountered explicit AWS WAF CAPTCHA. The production adapter completed two subsequent full refreshes with the same 164 IDs and unchanged sequences; controlled launch failure preserved exact last-good state and ICS. The built container reached Chrome under nonroot, read-only, cap-drop-all, no-new-privileges, no-network validation and failed because Docker denied Chrome sandbox namespace creation. The user subsequently approved testing the namespace profile; the ephemeral no-network test passed namespace creation but failed at Chrome's `sys_chroot("/proc/self/fdinfo/")` check. Production remains unchanged.

## Public files and state

The data branch `crux-data` contains only a validated `bundle.json` (public occurrence fields, update state, status, and ICS). Hugo's full-site build stages `/crux/calendar.ics`, `/crux/state.json`, `/crux/status.json`, `/crux/bundle.json`, and `/crux/index.html`. The landing page computes staleness from lastSuccess, so a stopped collector or publisher cannot leave a permanent “fresh” label.

Booking IDs form stable UIDs. Event changes increment SEQUENCE. Source cancellation is retained explicitly; disappearance requires two complete overlapping snapshots at least 30 minutes apart. Large removals stop for review. Missing entries outside coverage are not cancelled. Past active entries age out after 30 days; cancellation tombstones after 90 days past the event. Capacity/sold-out values never imply cancellation.

## Collector sandbox permission gate

The default-security container test failed with `Failed to move to new namespace ... errno = Operation not permitted`. The prepared `seccomp.proposed.json` is copied from Microsoft's Playwright v1.58.2 `utils/docker/seccomp_profile.json`, with its Apache license in `seccomp.LICENSE`. It retains a deny-by-default syscall policy and permits the namespace syscalls needed by sandboxed Chromium (`clone`, `setns`, `unshare`). Source: https://github.com/microsoft/playwright/blob/v1.58.2/utils/docker/seccomp_profile.json .

The user approved this collector-only namespace profile and it was tested in an ephemeral container. It still failed at Chrome's `chroot` step. The profile permits `chroot` only when CAP_SYS_CHROOT is present; the approved configuration drops all container capabilities. A separate `seccomp-chroot.proposed.json` adds exactly one unconditional syscall allowance, `chroot`, while retaining all other controls. This additional allowance has NOT been tested or applied and requires separate explicit approval. It increases the collector's available syscall surface; kernel capability checks still apply. This is the next narrow candidate, not a proven complete fix. Keep nonroot UID 1000, all capabilities dropped, no-new-privileges, read-only root, private IPC, no exposed ports, and no credential mount. Do not use privileged, SYS_ADMIN, seccomp=unconfined, host networking/IPC, or disable Chrome sandbox. If another exception is required, stop and report it separately. The publisher retains Docker's default seccomp policy.

## Publication permission gate

The user approved a fine-grained GitHub token selecting only `benjaminLevinson/benjaminLevinson.github.io`, with Contents read/write, automatic Metadata read, and a 90-day expiration. No Actions, Workflows, administration, or other-repository permission. GitHub does not restrict this token to a branch or filename: compromise can modify repository contents beyond the intended data file. Consider a separately reviewed GitHub App if shorter-lived tokens are desired.

The user must perform creation, entry and storage through a private terminal handoff. The assistant must never read, paste, log, transmit or store the token. `enter-publisher-token.py` is a user-run helper: it requires a TTY, disables echo, refuses a preexisting destination, creates a private 0700 directory and an exclusive 0600 file, and prints no credential. It does not validate remote scopes or make network requests. Do not invoke this helper through assistant tools.

User handoff: open GitHub Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate new token. Use name `Crux calendar publisher`, resource owner `benjaminLevinson`, 90 days, **Only select repositories**, and only `benjaminLevinson.github.io`. Grant Contents read/write and automatic Metadata read; leave all other permissions unset. The user generates the token and runs this helper in their own private interactive SSH terminal, passing the private destination file as its only argument. Paste only at the hidden prompt, never into chat, a command line, or an assistant terminal. The helper does not start publication. Official setup reference: https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens .

Keep the token in a private mode-0600 file mounted read-only only into the publisher. The collector container must never receive it. No token values go into git, environment logs, scripts, image layers, wiki, or chat. Do not extract/copy an existing broader credential. The publisher uses a fixed repository, branch and file; it validates the bundle, rejects state regression, and supplies the current blob SHA for conflict protection. It cannot create branches and assumes the initial data branch/file has been deliberately seeded.

## Activation sequence after approval

1. Obtain separate approval for the proposed additional `chroot` syscall allowance, then test that profile and complete a nonprivileged container run with Chrome's sandbox enabled. Do not apply any further security exception without approval.
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

Prepared profile SHA-256: `cc3e61cabda6bbc1e53e54d27ba4d55a9d3be829b6dd1a596f4a7b31b1cc7849`. That exact profile was applied only to the approved ephemeral test. The test failed at Chrome chroot and its container was removed. No persistent service configuration changed.
