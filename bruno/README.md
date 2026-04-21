# duprly API collection

Bruno collection for duprly's own REST API **plus** DUPR's upstream API
(api.dupr.gg), so you can isolate whether an issue is in our code or
DUPR's.

## Open in Bruno

1. `brew install bruno` (or download from https://usebruno.com)
2. Open → `bruno/duprly-api/`
3. Switch environment → "local"
4. Fill the secret vars (see below).

## Why Bruno over Postman

- Plain text `.bru` files → diffs cleanly in git
- Secret vars live in `.gitignore`'d files, never in the collection
- CLI support: `bru run` for scripted checks
- No cloud sign-in required

## Secret vars

Bruno stores these outside the repo. In the Bruno UI under Env → Vars → Secrets:

| var | how to get it |
|---|---|
| `dupr_username` | your DUPR account email |
| `dupr_password` | your DUPR account password |
| `dupr_bearer` | `DuprClient.auth_user(...)` or DevTools → Network on dashboard.dupr.com |
| `jupr_write_api_key` | optional; only if you set `JUPR_WRITE_API_KEY` locally |

Or skip Bruno and use the one-shot shell helper (see below).

## Debugging workflow: "is it our API or DUPR's?"

Preferred — the shell script runs both sides with identical query and prints
a verdict:

```bash
./scripts/debug_dupr_search.sh "natalie nguyen"
```

Output tells you exactly one of:

- `→ Likely a typo / unindexed profile.` — DUPR has 0 hits either, try variants.
- `→ BUG: upstream has hits, our API dropped them.` — check `web/services/dupr_live.py`.
- `→ duprly is serving from cache only.` — upstream 0, we have cache hits.
- `→ Both healthy.`

Interactive debugging in Bruno — run these in order:

1. `duprly_local/01_health` → duprly alive?
2. `duprly_local/02_dupr_search_by_name` → our hybrid search
3. `dupr_upstream/01_search_players` → same query against raw DUPR
4. Diff the two responses.

If our API returns fewer hits than DUPR raw:
- check `web/services/dupr_live.py::upsert_cached_player` — we drop rows
  with `_is_bad_name` (undefined undefined, empty, etc.)
- check `web/services/dupr_live.py::search` — `thin_cache` gate
- check cache state: `.venv-web/bin/python -c "from web.db import get_session; ..."`

If DUPR raw also returns 0:
- verify spelling (DUPR does NOT fuzzy-match)
- verify the profile exists via direct id lookup (`dupr_upstream/02_get_player`)
- see `docs/TICKETS.md` T-002 for the caller-self-exclusion quirk

## Known gotchas

1. **DUPR's /search is exact-match, not fuzzy.** "ngyuen" ≠ "nguyen". One
   character off = 0 results.
2. **DUPR hides the caller's own profile from /search.** Use
   `GET /player/v1.0/{your_numeric_id}` or paste your dashboard URL.
3. **Short DUPR ids (`GXWLNV`) don't work in /search or /player/{id}.**
   Our backend converts short ids back to numeric by searching — see
   `dupr_client.DuprClient._is_short_dupr_id`.
4. **DNS flakes on Tailscale.** If you see `NameResolutionError`, check
   `nslookup api.dupr.gg`. A stale uvicorn that was running through a DNS
   blip sometimes doesn't recover — restart it.

## Layout

```
bruno/
├── README.md                      # this file
└── duprly-api/
    ├── bruno.json                 # collection metadata
    ├── environments/local.bru     # base URLs + secret var names
    ├── duprly_local/              # our REST API
    │   ├── 01_health.bru
    │   ├── 02_dupr_search_by_name.bru
    │   ├── 03_dupr_search_by_id.bru
    │   ├── 04_dupr_get_player.bru
    │   ├── 05_dupr_refresh_player.bru
    │   ├── 10_dupr_forecast_fixture.bru
    │   ├── 11_dupr_forecast_live.bru
    │   ├── 12_dupr_expected_score.bru
    │   ├── 20_forecast_local_model.bru
    │   └── 30_reset_shadow.bru
    └── dupr_upstream/             # raw api.dupr.gg
        ├── README.md              # how to grab a bearer token
        ├── 01_search_players.bru
        ├── 02_get_player.bru
        ├── 10_expected_score.bru
        └── 11_forecast.bru
```
