# DUPR upstream (api.dupr.gg) — raw calls

These requests hit DUPR's API directly (bypassing duprly). Use them to
isolate "is it our code or DUPR's?" during debugging.

## Auth

DUPR uses a bearer JWT obtained from `POST /auth/v1.0/login`. Two ways to
get it:

1. **Automated**: the Python client (`dupr_client.DuprClient.auth_user`)
   does this for you and stores the token at `~/.duprly_config`:
   ```bash
   .venv-web/bin/python -c "
   from dotenv import load_dotenv; load_dotenv()
   from dupr_client import DuprClient; import os
   c = DuprClient()
   c.auth_user(os.environ['DUPR_USERNAME'], os.environ['DUPR_PASSWORD'])
   print(c.token)"
   ```
2. **Manual**: open DevTools on dashboard.dupr.com → Network tab → copy
   the `authorization` header from any XHR.

Paste the token into the `dupr_bearer` secret var in
`environments/local.bru` (Bruno secret vars are gitignored).

## Why these calls differ from dashboard.dupr.com

DUPR's web dashboard sends extra fields in search requests that our
backend client also sends (see `dupr_client.search_players`):

| field | our client | dashboard.dupr.com |
|---|---|---|
| `query` | ✅ | ✅ |
| `limit`, `offset` | ✅ | ✅ |
| `includeUnclaimedPlayers` | ✅ `true` | ✅ `true` |
| `filter.lat` / `filter.lng` | ✅ Boulder, CO | ✅ (user geolocation) |
| `filter.radiusInMeters` | ✅ `~infinity` | ❌ omitted |
| `filter.rating.{min,max}Rating` | ❌ | ✅ (null null) |
| `filter.locationText` | ❌ | ✅ (usually empty) |
| `address` top-level | ✅ | ❌ |
| `exclude` | ❌ | ✅ `[]` |

So far we haven't seen a case where these differences change the hit set.
If you find one, add a regression fixture in `tests/fixtures/dupr_api/`.
