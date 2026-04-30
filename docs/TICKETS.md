# duprly Tickets — known gaps & hypotheses

Short, referenceable tickets for known issues that we consciously chose NOT
to fix in the current PR. New tickets go at the top.

---

## T-002 · Hypothesis: DUPR `/search` never returns the **calling** user's own profile

- Reported: 2026-04-21 (Jon Chui)
- Status: `hypothesis-only` — needs confirmation with a second account
- Code entry point: `web/services/dupr_live.py::search` + `dupr_client.search_players`

### Observed behavior

Authenticated as user `4405492894` ("Jon chui", duprId `0YVNWN`,
Louisville CO, doubles 3.858, `shortAddress = "Louisville, CO, USA"`,
`enablePrivacy = false`):

| request | result |
|---|---|
| `GET /player/v1.0/4405492894` | 200, full profile, ratings returned |
| `POST /player/v1.0/search { query: "Jon chui" }` | 200, total=2, **4405492894 missing** |
| `POST /player/v1.0/search { query: "Jonathan Chui" }` | 200, total=1, missing |
| `POST /player/v1.0/search { query: "0YVNWN" }` (short id) | 200, total=0 |

Previously I hypothesized that DUPR drops profiles with `shortAddress=null`.
After seeing Jon's DUPR app profile screenshot (location set to
"Louisville, CO, USA", nothing hidden in Privacy), that explanation
is almost certainly wrong for this case.

### New working hypothesis

**DUPR's `/search` endpoint excludes the caller's own `id` from the
result set** (probably via `"excludeUserIds": [$jti]` or similar on the
server, consistent with the app UX of "find other players to book
with"). That would explain why a fully populated, public profile is
invisible to the account that owns it but visible via
`/player/v1.0/{id}`.

### How to confirm

1. Auth as a **different** DUPR account (or an unauthenticated one if
   the API allows).
2. `POST /player/v1.0/search { query: "Jon Chui" }`.
3. If `4405492894` appears in the hits list, this hypothesis is
   confirmed — and the bug is "search is fine, it's just ego-filtered".
4. If it still doesn't appear, fall back to the previous hypothesis
   (server-side indexing lag, shortAddress edge case, etc.).

### Why we're not fixing right now

Our hybrid search already handles this correctly: the `URL paste` / 
`numeric-id paste` / `cached-name match` paths all recover Jon's
profile without depending on `/search`. See commit `1f0c787`.

### Follow-up

- Add an ego-test probe to `scripts/lookup_dupr.py` that flags when
  `/search` silently drops the caller's id.
- If confirmed, document it as a known DUPR quirk in the UI empty-state
  partial.

---

## T-001 · Predictor sign regresses on lopsided losses

- Code entry point: `dupr_predictor.predict_impacts`
- Status: `partial-workaround` — surfaces in `/goal`; `/forecast` uses a
  margin-aware wrapper that papers over the worst behavior.

See [`docs/PREDICTOR_CONFIDENCE_JON_74.md`](./PREDICTOR_CONFIDENCE_JON_74.md)
for the analysis. The fitted model's `predict_impacts()` drives off
`(games1 - expected_g1)` — i.e. the *winner's* total only. That means
22-0, 22-7, 22-14, 22-18 all produce identical deltas because `games1`
is 22 in every case. It also explains the T-001 symptom of losing teams
occasionally getting positive deltas on lopsided scores.

### Workaround shipped for `/forecast/card` (2026-04-21)

`web/services/forecast._margin_aware_impacts()` rewrites the delta to
use `actual_margin - expected_margin` instead. Enabled by default via
`forecast_one(margin_aware=True)` — that's what the new DUPR-style score
picker calls. Legacy code paths can opt out with `margin_aware=False`.

### Full fix

Refit the model against DUPR's live `/match/forecast` endpoint (see
`docs/DUPR_FORECAST_API.md` and `tests/fixtures/dupr_api/`), which is
now plumbed through. Once the fitted predictor learns the losing-team
term natively, the margin-aware wrapper becomes redundant and can be
deleted.
