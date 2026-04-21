"""HTML page routes (server-rendered with Jinja + HTMX)."""

from __future__ import annotations

import os
from typing import Optional

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from web.db import get_session
from web.services import dupr_live
from web.services import forecast as forecast_svc
from web.services import fupr as fupr_svc
from web.services import goal as goal_svc
from web.services import jupr as jupr_svc
from web.services import shadow as shadow_svc

_TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "..", "templates")
templates = Jinja2Templates(directory=os.path.abspath(_TEMPLATES_DIR))

router = APIRouter()


def _tr(request: Request, name: str, context: dict) -> HTMLResponse:
    """Starlette >=0.38 signature-safe wrapper around TemplateResponse."""
    return templates.TemplateResponse(request, name, context)


@router.get("/", response_class=HTMLResponse)
def home(request: Request, session: Session = Depends(get_session)):
    top = jupr_svc.leaderboard(session, limit=5)
    return _tr(request, "index.html", {"leaderboard": top})


# ---- Forecast ----------------------------------------------------------------

@router.get("/forecast", response_class=HTMLResponse)
def forecast_page(request: Request):
    return _tr(request, "forecast.html", {"rows": None, "inputs": None})


@router.post("/forecast", response_class=HTMLResponse)
def forecast_submit(
    request: Request,
    r1: float = Form(...),
    r2: float = Form(...),
    r3: float = Form(...),
    r4: float = Form(...),
    rel1: Optional[float] = Form(default=None),
    rel2: Optional[float] = Form(default=None),
    rel3: Optional[float] = Form(default=None),
    rel4: Optional[float] = Form(default=None),
    target: int = Form(default=11),
):
    rows = forecast_svc.forecast_matrix(
        r1, r2, r3, r4, target=target,
        rel1=rel1, rel2=rel2, rel3=rel3, rel4=rel4,
    )
    inputs = {
        "r1": r1, "r2": r2, "r3": r3, "r4": r4,
        "rel1": rel1, "rel2": rel2, "rel3": rel3, "rel4": rel4,
        "target": target,
    }
    if request.headers.get("HX-Request"):
        return _tr(request, "partials/forecast_table.html", {"rows": rows, "inputs": inputs})
    return _tr(request, "forecast.html", {"rows": rows, "inputs": inputs})


# ---- JUPR --------------------------------------------------------------------

@router.get("/jupr", response_class=HTMLResponse)
def jupr_page(
    request: Request,
    session: Session = Depends(get_session),
):
    board = jupr_svc.leaderboard(session, limit=50)
    games = jupr_svc.recent_games(session, limit=15)
    return _tr(request, "jupr.html", {"leaderboard": board, "games": games})


@router.get("/p/{player_id}", response_class=HTMLResponse)
def player_page(
    player_id: int,
    request: Request,
    session: Session = Depends(get_session),
):
    rating = jupr_svc.get_rating(session, player_id)
    if rating is None:
        return HTMLResponse("Player not found", status_code=404)
    fupr_agg = fupr_svc.aggregate(session, player_id)
    games = jupr_svc.recent_games(session, player_id=player_id, limit=25)
    return _tr(
        request,
        "player.html",
        {"rating": rating, "fupr": fupr_agg, "games": games},
    )


@router.get("/jupr/search", response_class=HTMLResponse)
def jupr_search(
    request: Request,
    q: str = Query(default=""),
    session: Session = Depends(get_session),
):
    """HTMX endpoint — returns a `<ul>` of matching JUPR players."""
    q = (q or "").strip()
    if not q:
        return HTMLResponse("")
    from sqlalchemy import select as _sel

    from web.models import JuprPlayer
    rows = session.execute(
        _sel(JuprPlayer)
        .where(JuprPlayer.full_name.ilike(f"%{q}%"))
        .order_by(JuprPlayer.full_name)
        .limit(20)
    ).scalars().all()
    return _tr(request, "partials/player_search.html", {"players": rows, "q": q})


# ---- DUPR search (HTMX partial for forecast auto-fill) -----------------------

@router.get("/dupr/search", response_class=HTMLResponse)
def dupr_search_partial(
    request: Request,
    q: str = Query(default=""),
    slot: int = Query(default=1, ge=1, le=4),
    session: Session = Depends(get_session),
):
    q = (q or "").strip()
    if len(q) < 2:
        return HTMLResponse("")
    hits = dupr_live.search(session, query=q, limit=10)
    return _tr(
        request,
        "partials/dupr_search.html",
        {"hits": hits, "slot": slot, "q": q},
    )


# ---- Goal (reverse forecast) -------------------------------------------------

@router.get("/goal", response_class=HTMLResponse)
def goal_page(request: Request):
    return _tr(request, "goal.html", {"forecast": None, "inputs": None})


@router.post("/goal", response_class=HTMLResponse)
def goal_submit(
    request: Request,
    me_slot: int = Form(...),
    r1: float = Form(...),
    r2: float = Form(...),
    r3: float = Form(...),
    r4: float = Form(...),
    target_delta: float = Form(...),
    target: int = Form(default=22),
    rel1: Optional[float] = Form(default=None),
    rel2: Optional[float] = Form(default=None),
    rel3: Optional[float] = Form(default=None),
    rel4: Optional[float] = Form(default=None),
):
    forecast = goal_svc.compute(
        me_slot=me_slot,
        r1=r1, r2=r2, r3=r3, r4=r4,
        target_delta=target_delta,
        target=target,
        rel1=rel1, rel2=rel2, rel3=rel3, rel4=rel4,
    )
    inputs = {
        "me_slot": me_slot,
        "r1": r1, "r2": r2, "r3": r3, "r4": r4,
        "rel1": rel1, "rel2": rel2, "rel3": rel3, "rel4": rel4,
        "target_delta": target_delta, "target": target,
    }
    if request.headers.get("HX-Request"):
        return _tr(request, "partials/goal_table.html", {"forecast": forecast, "inputs": inputs})
    return _tr(request, "goal.html", {"forecast": forecast, "inputs": inputs})


# ---- Shadow Reset Simulator --------------------------------------------------

@router.get("/reset", response_class=HTMLResponse)
def reset_page(request: Request):
    """Shadow-reset simulator form."""
    return _tr(
        request,
        "reset.html",
        {
            "summary": None,
            "inputs": None,
            "error": None,
            "default_cutoff": shadow_svc.DEFAULT_CUTOFF.isoformat(),
        },
    )


@router.post("/reset", response_class=HTMLResponse)
def reset_submit(
    request: Request,
    dupr_id: str = Form(...),
    cutoff_date: Optional[str] = Form(default=None),
    baseline_rating: Optional[float] = Form(default=None),
):
    from datetime import date as _date

    cutoff = None
    error: Optional[str] = None
    summary = None
    if cutoff_date:
        try:
            cutoff = _date.fromisoformat(cutoff_date.strip())
        except ValueError:
            error = f"Invalid cutoff date: {cutoff_date!r} (expected YYYY-MM-DD)"
    if error is None:
        try:
            summary = shadow_svc.simulate(
                dupr_id=dupr_id.strip(),
                baseline_rating=baseline_rating,
                cutoff=cutoff,
            )
        except shadow_svc.ShadowUnavailable as e:
            error = str(e)
        except Exception as e:  # catch-all so the form always renders
            error = f"Simulation failed: {e}"

    inputs = {
        "dupr_id": dupr_id,
        "cutoff_date": cutoff_date or shadow_svc.DEFAULT_CUTOFF.isoformat(),
        "baseline_rating": baseline_rating,
    }
    template = "partials/reset_results.html" if request.headers.get("HX-Request") else "reset.html"
    return _tr(
        request,
        template,
        {
            "summary": summary,
            "inputs": inputs,
            "error": error,
            "default_cutoff": shadow_svc.DEFAULT_CUTOFF.isoformat(),
        },
    )
