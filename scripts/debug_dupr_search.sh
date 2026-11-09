#!/usr/bin/env bash
# debug_dupr_search.sh — diff our /api/dupr/search vs DUPR's raw /player/search
#
# When the duprly UI shows "No matches" and you want to know whether:
#   (a) DUPR itself has no hits (likely a typo / non-indexed profile),
#   (b) our cache-first layer dropped them (bug in our side),
#   (c) DUPR is unreachable (DNS / SSL / auth),
# run this script with the query. It calls both endpoints with the same
# query string and prints a compact summary.
#
# Usage:
#   ./scripts/debug_dupr_search.sh "natalie nguyen"
#   DUPRLY_BASE=http://127.0.0.1:8765 ./scripts/debug_dupr_search.sh "Jon Chui"
#
# Requires: .env with DUPR_USERNAME/DUPR_PASSWORD, jq, a running duprly
# server (default http://127.0.0.1:8000).

set -euo pipefail

QUERY="${1:-}"
if [[ -z "$QUERY" ]]; then
  echo "usage: $0 <search query>" >&2
  exit 64
fi

DUPRLY_BASE="${DUPRLY_BASE:-http://127.0.0.1:8000}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if ! command -v jq >/dev/null 2>&1; then
  echo "jq required (brew install jq)" >&2
  exit 69
fi

QUERY_ENC="$(python3 -c "import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1]))" "$QUERY")"

printf '\n\033[1;36m── DUPR upstream  (api.dupr.gg /player/search) ──\033[0m\n'

UPSTREAM_JSON="$(
  .venv-web/bin/python - "$QUERY" <<PY
import json, os, sys
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(dotenv_path=Path("${REPO_ROOT}") / ".env")
from dupr_client import DuprClient

query = sys.argv[1]
c = DuprClient()
rc = c.auth_user(os.environ["DUPR_USERNAME"], os.environ["DUPR_PASSWORD"])
if rc not in (0, 200):
    print(json.dumps({"error": f"auth rc={rc}"}))
    sys.exit(0)
rc, res = c.search_players(query, limit=10)
out = {
    "http_status": rc,
    "total": (res or {}).get("total"),
    "hits": [
        {
            "id": h.get("id"),
            "duprId": h.get("duprId"),
            "fullName": h.get("fullName"),
            "doubles": (h.get("ratings") or {}).get("doubles"),
            "shortAddress": h.get("shortAddress"),
        }
        for h in ((res or {}).get("hits") or [])
    ],
}
print(json.dumps(out, indent=2))
PY
)"
echo "$UPSTREAM_JSON" | jq '{http_status, total, hits: (.hits | length), first_5: (.hits[0:5])}'

printf '\n\033[1;32m── duprly  (%s/api/dupr/search) ──\033[0m\n' "$DUPRLY_BASE"

DUPRLY_RAW="$(curl -s -w '\n---HTTP:%{http_code}---' \
  "${DUPRLY_BASE}/api/dupr/search?q=${QUERY_ENC}&limit=10&live=true")"
DUPRLY_STATUS="$(echo "$DUPRLY_RAW" | awk -F: '/^---HTTP:/{print $2}' | tr -d -)"
DUPRLY_BODY="$(echo "$DUPRLY_RAW" | sed '/^---HTTP:/d')"

echo "$DUPRLY_BODY" | jq --arg status "$DUPRLY_STATUS" '{
  http_status: ($status|tonumber),
  hits: (length),
  first_5: (.[0:5] | map({dupr_id, full_name, doubles, source, stale}))
}'

printf '\n\033[1;33m── verdict ──\033[0m\n'
UPSTREAM_HITS="$(echo "$UPSTREAM_JSON" | jq '.hits | length')"
DUPRLY_HITS="$(echo "$DUPRLY_BODY" | jq 'length')"
printf 'DUPR upstream: %s hits\n' "$UPSTREAM_HITS"
printf 'duprly API:    %s hits\n' "$DUPRLY_HITS"

if [[ "$UPSTREAM_HITS" == "0" && "$DUPRLY_HITS" == "0" ]]; then
  echo '→ Likely a typo / unindexed profile. Try variants.'
elif [[ "$UPSTREAM_HITS" != "0" && "$DUPRLY_HITS" == "0" ]]; then
  echo '→ BUG: upstream has hits, our API dropped them. Check web/services/dupr_live.py.'
elif [[ "$UPSTREAM_HITS" == "0" && "$DUPRLY_HITS" != "0" ]]; then
  echo '→ duprly is serving from cache only. Pass live=true (already on).'
else
  echo '→ Both healthy.'
fi
