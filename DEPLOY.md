# Deploying duprly (MCP + Vercel + gateway-mcp)

## What this repo exposes on Vercel

- `GET /health` — JSON health check
- `GET /sse` — MCP over SSE (same as `duprly_mcp.py --sse`)
- `POST /messages/*` — MCP message endpoint (required by the SSE transport)

The Python runtime loads the top-level **`app.py`** ASGI app (Starlette). Paths are `/health`, `/sse`, and `/messages/*` — no `/api` prefix, so MCP clients and gateway-mcp can use `https://YOUR_PROJECT.vercel.app/sse` directly.

### Limits

Vercel **serverless** functions exit after the configured `maxDuration`. Long-lived MCP SSE sessions may disconnect on Hobby or when idle. If that bites you, run the MCP on a VPS with `uvicorn` or use a platform that supports long streaming requests. Treat successful `/health` + a short MCP session as “working.”

---

## Environment variables (Vercel)

In the Vercel project → Settings → Environment Variables, set (at minimum):

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | **Recommended for production.** Postgres URL (`postgresql+psycopg://...` or `postgres://...` — the app normalizes common forms). Without it, the server uses SQLite under `/tmp` on Vercel (ephemeral; local-cache tools reset on cold starts). |
| `DUPR_USERNAME` / `DUPR_PASSWORD` | DUPR API auth |
| `DUPR_CLUB_ID` | Optional; used by club tools if not passed in the tool call |
| `MCP_API_KEY` | Optional; if set, clients must send `Authorization: Bearer <key>` to `/sse` and `/messages/` |

For **Neon / Supabase**, paste the connection string as `DATABASE_URL`.

---

## CI/CD (GitHub Actions → Vercel)

This repo includes `.github/workflows/deploy-vercel.yml`. It deploys **preview** deployments on pull requests and **production** when `main` is pushed — once you add secrets:

| Secret | Where to get it |
|--------|------------------|
| `VERCEL_TOKEN` | [Vercel account tokens](https://vercel.com/account/tokens) |
| `VERCEL_ORG_ID` | Vercel Team → Settings → General (Team ID) |
| `VERCEL_PROJECT_ID` | Project → Settings → General (Project ID) |

Also connect the GitHub repo to the Vercel project (Vercel dashboard → Project → Git).

---

## Manual deploy (Vercel CLI)

```bash
npm i -g vercel
cd /path/to/duprly
vercel link
vercel env pull .env.local   # optional
vercel deploy --prod
```

Smoke check:

```bash
curl -sS "https://YOUR_PROJECT.vercel.app/health"
```

---

## gateway-mcp

This repository is **not** gateway-mcp. After duprly is live, configure the **gateway** project to register a backend like:

- **Upstream SSE URL:** `https://YOUR-DUPRLY.vercel.app/sse`
- **Auth:** forward `Authorization: Bearer <MCP_API_KEY>` if you set `MCP_API_KEY` on duprly
- **Public route:** whatever your gateway uses, e.g. `https://gateway-mcp.vercel.app/mcps/duprly`

OAuth / basic auth live **in the gateway**, not in duprly; duprly only enforces the Bearer check when `MCP_API_KEY` is set.

---

## Moving the repo under `gateway-mcp` on GitHub

1. Create or transfer the repo to the `gateway-mcp` org (e.g. `gateway-mcp/duprly`).
2. In Vercel, import or reconnect the project to that GitHub repo (same codebase).
3. Re-add GitHub Actions secrets if the repo name/org changed.
