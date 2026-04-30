# Deploying the duprly website to Vercel

The public website (forecast · JUPR · FUPR) is a single Python FastAPI app
rendered into Vercel's Python serverless runtime.

## Local dev

```bash
# from repo root
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn web.main:app --reload --port 8000
```

Visit:

- `http://localhost:8000/` — home
- `http://localhost:8000/forecast` — score matrix forecaster
- `http://localhost:8000/jupr` — JUPR leaderboard + add-player
- `http://localhost:8000/api/docs` — public OpenAPI

SQLite file `duprly_web.db` is created in the working directory. Delete it
to start fresh.

## Vercel setup (Git-driven, no manual `--prod`)

Per this repo's Vercel rules, we let Git integration drive deploys:

1. **Link the repo to a Vercel project**
   ```bash
   vercel link          # one-time
   ```
2. **Add the Neon Postgres integration via Marketplace**
   - Vercel dashboard → Storage → Add → Neon
   - Choose the duprly project — Vercel auto-provisions `DATABASE_URL`,
     `POSTGRES_URL`, etc. for Preview and Production.
3. **Set write-auth secret**
   ```bash
   openssl rand -hex 32 | vercel env add JUPR_WRITE_API_KEY production
   # repeat for preview if you want gated writes on preview too
   ```
4. **Push to main** → Vercel auto-deploys from the Git commit.

Verify per the workspace rule:

```bash
vercel inspect <deployment-url>       # confirm live commit SHA
vercel curl <deployment-url>/api/health
```

## Public API shape

Base: `https://<your-deployment>.vercel.app/api`

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET    | `/health` | — | Liveness |
| POST   | `/forecast` | — | Score matrix for 4 ratings |
| GET    | `/jupr/players` | — | List players (`q=` for search) |
| POST   | `/jupr/players` | write-key | Create JUPR player |
| GET    | `/jupr/players/{id}` | — | Current JUPR rating |
| GET    | `/jupr/players/{id}/games` | — | Game history |
| POST   | `/jupr/games` | write-key | Record a game |
| GET    | `/jupr/leaderboard` | — | Top JUPR ratings |
| GET    | `/fupr/{id}` | — | Crowd aggregate |
| POST   | `/fupr/{id}/votes` | — (IP-rate-limited) | Cast vote |

Write-key (when `JUPR_WRITE_API_KEY` is set) goes in either header:

```
Authorization: Bearer <key>
X-Api-Key: <key>
```

## Why a single Python app (and not Next.js)

- Reuses `dupr_predictor.py` + `dupr_model.json` verbatim — no re-derivation.
- FastAPI gives us the public OpenAPI at `/api/docs` for free.
- Jinja + Tailwind CDN + HTMX = a modern UI with zero build step.

If you later want a richer frontend (charts, client routing, shadcn/ui),
the REST API is stable and a Next.js frontend can live alongside the
Python backend without touching it.
