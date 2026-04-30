# DUPR API fixtures

Real request/response pairs captured via Proxyman from the DUPR iOS app
(build 1486) on 2026-04-09. These are the ground truth for the
`/match/v1.0/expected-score` and `/match/v1.0/forecast` endpoints that
DUPR uses to produce the "DUPR Forecaster" rating-change projections.

- **Host**: `api.dupr.gg`
- **Auth**: `Authorization: Bearer <JWT>` — bearer tokens have been
  stripped. When running scripts that talk to live DUPR, provide an
  email/password via `DUPR_USERNAME`/`DUPR_PASSWORD` and let
  `dupr_client.DuprClient.auth_user` mint its own token.
- **Caller context**: player id `4405492894` (Jon chui, duprId `0YVNWN`,
  Louisville CO, doubles 3.858) — the caller's own profile.

## Files

| file | endpoint | winningScore | purpose |
|---|---|---|---|
| `06-expected-score-to-11.request.json`  | `/expected-score` | 11 | best-of-3 to 11 predicted game score |
| `06-expected-score-to-11.response.json` | `/expected-score` | 11 | expected ≈ 3.5 for underdog, 11 for favorite |
| `07-forecast-to-11.request.json`  | `/forecast` | 11 | full rating-impact curves (11 slots, losing team scored 0..10) |
| `07-forecast-to-11.response.json` | `/forecast` | 11 | `winProbabilityPercentage` + `winningRatingImpacts` arrays |
| `17-expected-score-to-15.request.json`  | `/expected-score` | 15 | best-of-3 to 15 predicted game score |
| `17-expected-score-to-15.response.json` | `/expected-score` | 15 | expected ≈ 4.5 for underdog, 15 for favorite |
| `18-forecast-to-15.request.json`  | `/forecast` | 15 | 15-slot impact curves (losing team scored 0..14) |
| `18-forecast-to-15.response.json` | `/forecast` | 15 | idem |

## Schema (both endpoints, same request body)

```jsonc
{
  "eventFormat": "DOUBLES" | "SINGLES",
  "gameCount": 1,
  "matchSource": "CLUB" | "TOURNAMENT" | ...,
  "matchType":   "SIDE_ONLY" | "SIDE_AND_SERVE" | ...,
  "teams": [
    { "player1Id": <long>, "player2Id": <long> },
    { "player1Id": <long>, "player2Id": <long> }
  ],
  "winningScore": 11 | 15 | 21
}
```

## `/expected-score` response

```jsonc
{
  "teams": [
    {
      "player1Id": <long>,
      "player2Id": <long>,
      "score": <float>,                     // predicted games-won IF this team is the loser
      "winProbabilityPercentage": null,     // always null on this endpoint
      "winningRatingImpacts":    null       // always null on this endpoint
    },
    /* opponent team; its score is the winningScore integer (e.g. 11) */
  ]
}
```

## `/forecast` response

Same shape, but **both** teams get full rating-impact data:

```jsonc
{
  "teams": [
    {
      "player1Id": <long>, "player2Id": <long>,
      "score": <float>,                     // predicted losing-side game count
      "winProbabilityPercentage": <int>,    // e.g. 10 / 90
      "winningRatingImpacts": [<float>, ...]// length == winningScore
                                            // index N = delta IF this team wins AND losing team scored N games
    },
    /* other team, symmetric */
  ]
}
```

## Invariants we rely on in tests

1. `winningRatingImpacts.length == winningScore` for both teams on
   `/forecast`.
2. `winProbabilityPercentage` sums to ~100 across both teams on
   `/forecast`; always null on `/expected-score`.
3. For the under-dog team, `winningRatingImpacts[-1]` (tightest win,
   loser scored winningScore-1) is the *smallest* positive delta —
   because close wins mean less rating movement.
4. For the favorite team, `winningRatingImpacts[0]` (blowout win,
   loser scored 0) is the *most negative* value — they "lose" the most
   potential rating if they squeak by or underperform.

## Use in code

- `web/services/dupr_forecast.py` → calls DUPR live; falls back to the
  matching fixture when `DUPRLY_USE_FIXTURES=1` so the API and tests
  don't depend on live creds.
- `tests/test_dupr_forecast_fixtures.py` → parses all 8 files, checks
  the invariants above.
