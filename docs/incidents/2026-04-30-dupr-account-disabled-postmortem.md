# Incident: pbislife@jonchui.com DUPR account disabled

**Status:** account disabled by DUPR (~2026-04-22), under support review
**Severity:** S1 (production credential disabled, blocks coach + students)
**Owner:** Jon Chui
**Detected:** 2026-04-30 03:00 UTC (when forecast.picklewith.me stopped responding)
**Resolved (cause):** 2026-04-30 03:35 UTC (DUPR creds removed from VPS, rate
limiter shipped — see commit `69d0af8`)
**Resolved (account):** _pending DUPR support_

---

## Timeline

| When (UTC) | What |
|---|---|
| 2026-02-18 04:13 | VPS bootstrapped. `/root/duprly/.env` created with `pbislife@jonchui.com`. Never touched again. |
| 2026-04-22 11:29 | `forecast.picklewith.me` deployed (commit `869c7d5`). Webapp inherits the Feb-18 .env at startup → makes live DUPR calls when users hit `/dupr/player/<id>`. |
| 2026-04-22 ~19:30 PDT | Account first noticed disabled. Jon emails DUPR support. |
| 2026-04-23 06:02 | duprly-web service start (last restart before incident). |
| 2026-04-26 17:23 PDT | Diana (DUPR support) confirms: "our systems detected the use of automated tools, scripts, or other unauthorized methods to scrape data". |
| 2026-04-29 17:00 → 2026-04-30 02:00 | **Sustained 11.3 DUPR calls/sec for ~10 hours straight.** Caught in journalctl. |
| 2026-04-30 03:00 | Site goes unreachable over HTTPS (load avg 3.5, CPU 58%). |
| 2026-04-30 03:01 | Service force-killed. |
| 2026-04-30 03:35 | DUPR creds disabled on VPS. Saved access token deleted. Rate limiter deployed. |

## Root cause

Three failure modes layered:

1. **No rate limiting in `dupr_client`.** Every `requests.get` / `requests.post`
   hit `api.dupr.gg` immediately, with no token bucket between callers.
2. **Public `/dupr/player/<dupr_id>` endpoint** that triggered a live DUPR call
   on each visit. Search-engine bots discovered this endpoint and crawled it.
3. **Auth-retry loop with no backoff.** When the JWT expired, every concurrent
   FastAPI request handler simultaneously called `_relogin()`, getting 429s,
   then immediately retrying. Once 429s started, the loop would never exit
   because the response never became 200 ("login user: 429" forever).

The trigger was bot crawler `74.7.227.3` walking ~170 player pages
(`/dupr/player/4405492894`, `/dupr/player/5246622881`, …) in quick succession.
With no caching, no rate limit, and no retry backoff, this fanned out into the
infinite login loop.

## Numbers (in journalctl window — Apr 29 + Apr 30 only)

| Metric | Count |
|---|---|
| Total DUPR API calls (POST/GET) | **393,431** |
| Total `/login/` attempts | **786,821** |
| HTTP 429 responses | **358,440** |
| HTTP 400 responses on login (account flagged) | **34,742** |

### Per-hour DUPR calls (all from the journal window)

| Hour (UTC) | Calls | Rate |
|---|---:|---:|
| Apr 29 17:00 | 27,693 | 7.7 / sec |
| Apr 29 18:00 | 40,623 | 11.3 / sec |
| Apr 29 19:00 | 40,563 | 11.3 / sec |
| Apr 29 20:00 | 40,521 | 11.3 / sec |
| Apr 29 21:00 | 40,523 | 11.3 / sec |
| Apr 29 22:00 | 40,547 | 11.3 / sec |
| Apr 29 23:00 | 40,562 | 11.3 / sec |
| Apr 30 00:00 | 40,462 | 11.2 / sec |
| Apr 30 01:00 | 40,568 | 11.3 / sec |
| Apr 30 02:00 | 40,295 | 11.2 / sec |
| Apr 30 03:00 | 1,079 | 0.3 / sec (after kill) |

Service uptime: Apr 23 06:02 → Apr 30 03:01 = **6.87 days**.
Journal only retains the last ~48 hours, so the actual lifetime call count
is likely **~6× higher** (~2.4M DUPR calls total, ~4.8M login attempts).

CPU stat from systemd: 3d 13h 11min CPU time over 6.87 days uptime ≈
**51.7% sustained CPU**, all of it in the retry loop.

## Why pbislife@jonchui.com (and not lucas@jonchui.com)

The local `.env` was updated to `lucas@jonchui.com` at some point. The VPS
`.env` is gitignored (correctly — secrets don't go in git) and was bootstrapped
once on 2026-02-18 with `pbislife@jonchui.com`. The local update never made
it to the VPS. **This is a deploy-process gap.** Fix: add an explicit
`scripts/sync-vps-env.sh` (or rotate to a deploy-secret store like
`pass` / `1password` / sealed secrets).

## Remediation (already shipped)

Commit `69d0af8` on `feat/dupr-search-and-shadow-reset`:

1. New `dupr_rate_limit.DuprRateLimiter` — process-wide token bucket. Every
   outgoing DUPR HTTP call funnels through it. See module docstring for the
   policy and `tests/test_dupr_rate_limit.py` for behavior coverage.
2. `min_interval_s = 1.0` — at most one DUPR call per second per process.
3. `Retry-After` header honored on 429.
4. 3× consecutive 429s → 5-minute lockout (refuse with synthetic 503 instead
   of stomping on a flagged account).
5. 2× consecutive login failures → 5-minute lockout (this is what would have
   prevented this incident if it had been there from day one).
6. `max_wait_s = 60` cap — single requests can't queue indefinitely.
7. `/healthz` exposes the limiter snapshot for ops visibility.
8. `/robots.txt` blocks crawlers from `/dupr/player/` and `/api/`.

Then on 2026-04-30 03:35:
- DUPR creds commented out in `/root/duprly/.env` (backup at `.env.bak.*`).
- `/root/.duprly_config` (cached access token) renamed to `.bak.*`.
- `duprly-web` restarted — runs in pure cache mode, no DUPR calls possible.

## Pending work before re-enabling DUPR creds

- [ ] Wait for DUPR support to restore `pbislife@jonchui.com`.
- [ ] Decide whether to rotate to `lucas@jonchui.com`. Lean: NO, because the
      same crawler will re-trigger the same surface area. Restore pbislife
      first, harden, then revisit.
- [ ] Add request auth on `/dupr/player/*` (require a session cookie or
      a signed query token) so anonymous crawlers can't trigger live
      DUPR calls at all. Caching the response helps secondary load but not
      the first-hit-on-cold-cache problem.
- [ ] Verify the rate limiter actually serializes traffic in production (not
      just unit tests) by running a synthetic burst against the live URL.
- [ ] Add a `scripts/sync-vps-env.sh` so local .env edits actually propagate
      to the VPS through a documented path.

## Lessons

- "I'll add rate limiting later" is never true. Every external API client must
  ship with a rate limiter on day one, period.
- Public endpoints that trigger third-party API calls are crawler honeypots.
  Either gate them behind auth or cache aggressively at the public edge.
- Any retry-on-401 path must back off on the retry response (429 / 400),
  otherwise it converts a recoverable transient failure into a permanent
  outage of your upstream account.
- Local `.env` ≠ deployed `.env`. This needs to be a deploy-script step,
  not "I'll remember to scp it next time".
