"""
FastAPI application entry.

Exposes:
- GET  /                    — home
- GET  /forecast            — forecast page
- POST /forecast            — form submit (returns HTML; HTMX-aware)
- GET  /jupr                — JUPR leaderboard & game entry UI
- GET  /p/{player_id}       — player profile (DUPR seed · JUPR current · FUPR crowd)
- GET  /api/health          — liveness
- POST /api/forecast        — JSON forecast
- /api/jupr/*               — players, games, leaderboard
- /api/fupr/*               — votes, aggregate
- GET  /api/docs            — OpenAPI UI
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware

# Load .env BEFORE any modules that read env vars (DUPR creds, JUPR_WRITE_API_KEY).
#
# We resolve the project-root .env explicitly from this file's location rather
# than relying on CWD. Otherwise `uvicorn web.main:app` launched from anywhere
# but the repo root silently starts with no DUPR credentials and the UI shows
# "Local cache only" even though .env is sitting right there.
#
# Vercel ignores this because it injects env vars at runtime — load_dotenv()
# is a no-op when the target file doesn't exist.
try:
    from dotenv import load_dotenv

    _DOTENV_PATH = Path(__file__).resolve().parent.parent / ".env"
    load_dotenv(dotenv_path=_DOTENV_PATH, override=False)
except ImportError:
    pass

from web.db import init_db
from web.routes.api import router as api_router
from web.routes.pages import router as pages_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="duprly",
        description=(
            "Open pickleball rating sandbox. Forecast DUPR rating impact for "
            "every score, run your own JUPR (mirror DUPR with the same "
            "reverse-engineered algorithm), and crowd-rate players via FUPR."
        ),
        version="0.1.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )

    # Open CORS — public API is explicit goal.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # DB tables (no-op if already present).
    init_db()

    # Static files
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    if os.path.isdir(static_dir):
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

    # Routes
    app.include_router(api_router)
    app.include_router(pages_router)

    return app


app = create_app()
