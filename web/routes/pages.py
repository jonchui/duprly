"""HTML page routes (server-rendered with Jinja + HTMX)."""

from __future__ import annotations

import os
from typing import Optional

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
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


def _scale_to_match_total(games1: int, games2: int, games_played: int) -> tuple[int, int]:
    """
    Convert single-game scores (e.g. 11-7) into the match-total the fitted
    predictor was trained on (sum of game-points across a best-of-3 match).

    See web/services/forecast.py::_generate_candidate_scores: the DuprPredictor
    was fit on games1/games2 totals like 22-13 (2-game sweep), 28-22 (2-1),
    not single-game scores. Feeding it (11, 7) gives a saturated / near-boundary
    delta because that looks like a losing-margin edge case to the model.

    Heuristic:
      - games_played=2 (assume 2-0 sweep) → double both scores.
      - games_played=3 (2-1 split): winner won 2, loser won 1. Approximate
        game totals as (2*winner_pts + loser_pts) and mirror. Close enough
        for single-score UI; for an exact matrix use forecast_matrix().
    """
    if games1 == games2:
        return games1, games2
    if games_played <= 2:
        return games1 * 2, games2 * 2
    # 3-game split: winner took 2 of 3, loser 1 of 3.
    if games1 > games2:
        winner_total = 2 * games1 + games2
        loser_total = 2 * games2 + games1
        return winner_total, loser_total
    else:
        winner_total = 2 * games2 + games1
        loser_total = 2 * games1 + games2
        return loser_total, winner_total


@router.get("/forecast/card", response_class=HTMLResponse)
def forecast_card(
    request: Request,
    r1: float = Query(...),
    r2: float = Query(...),
    r3: float = Query(...),
    r4: float = Query(...),
    games1: int = Query(..., ge=0, le=30),
    games2: int = Query(..., ge=0, le=30),
    rel1: Optional[float] = Query(default=None),
    rel2: Optional[float] = Query(default=None),
    rel3: Optional[float] = Query(default=None),
    rel4: Optional[float] = Query(default=None),
    name1: Optional[str] = Query(default=None),
    name2: Optional[str] = Query(default=None),
    name3: Optional[str] = Query(default=None),
    name4: Optional[str] = Query(default=None),
    age1: Optional[int] = Query(default=None),
    age2: Optional[int] = Query(default=None),
    age3: Optional[int] = Query(default=None),
    age4: Optional[int] = Query(default=None),
    gender1: Optional[str] = Query(default=None),
    gender2: Optional[str] = Query(default=None),
    gender3: Optional[str] = Query(default=None),
    gender4: Optional[str] = Query(default=None),
    loc1: Optional[str] = Query(default=None),
    loc2: Optional[str] = Query(default=None),
    loc3: Optional[str] = Query(default=None),
    loc4: Optional[str] = Query(default=None),
    img1: Optional[str] = Query(default=None),
    img2: Optional[str] = Query(default=None),
    img3: Optional[str] = Query(default=None),
    img4: Optional[str] = Query(default=None),
    games_played: int = Query(default=2, ge=1, le=3),
    event_label: Optional[str] = Query(default=None),
    venue_label: Optional[str] = Query(default=None),
):
    """
    Render a single DUPR-style match card for one concrete score.

    Used by the `/forecast` score picker — the user sets Team 1 vs Team 2
    game points (e.g. 11-7) and we rerender the card with live per-player
    deltas (pre / Δ / post), styled to match DUPR's native match UI.

    Scores are interpreted as single-game scores (to 11 or to 15) and
    scaled to match-totals before feeding the predictor — the fitted model
    was trained on totals, not single-game scores. Pass games_played=3
    for a 2-1 split instead of a sweep.

    The `name{N}`, `age{N}`, `gender{N}`, `loc{N}`, `img{N}` query params
    are optional — the forecast page populates them from the DUPR search
    pick so the card mirrors DUPR's own layout.
    """
    if games1 == games2:
        return HTMLResponse(
            '<div class="text-amber-300 text-sm p-4 rounded-lg bg-amber-500/10 ring-1 ring-amber-500/30">'
            "Ties aren't rated. Pick a different score."
            "</div>"
        )
    g1_total, g2_total = _scale_to_match_total(games1, games2, games_played)
    row = forecast_svc.forecast_one(
        r1, r2, r3, r4, g1_total, g2_total,
        rel1=rel1, rel2=rel2, rel3=rel3, rel4=rel4,
    )
    row.games1 = games1
    row.games2 = games2
    players = [
        {"name": name1, "age": age1, "gender": gender1, "short_address": loc1, "image_url": img1},
        {"name": name2, "age": age2, "gender": gender2, "short_address": loc2, "image_url": img2},
        {"name": name3, "age": age3, "gender": gender3, "short_address": loc3, "image_url": img3},
        {"name": name4, "age": age4, "gender": gender4, "short_address": loc4, "image_url": img4},
    ]
    split_note = "2-0 sweep" if games_played <= 2 else "2-1 split"
    return _tr(
        request,
        "partials/dupr_match_card.html",
        {
            "row": row,
            "players": players,
            "is_preview": True,
            "event_label": event_label or "DUPRLY forecast",
            "venue_label": venue_label or f"Score preview · {games1}-{games2} · {split_note}",
            "delta_source": "local margin-aware model",
        },
    )


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

@router.get("/dupr/search")
def dupr_search_partial(
    request: Request,
    q: str = Query(default=""),
    slot: int = Query(default=1, ge=1, le=4),
    session: Session = Depends(get_session),
):
    """
    Content-negotiated DUPR search.

    - Accept: application/json → returns a JSON array of hits (same shape as
      /api/dupr/search). Use this for scripts, SDKs, or sanity-checking
      the underlying hybrid search.
    - otherwise → returns the HTMX autocomplete HTML partial consumed by
      the forecast/goal/reset player pickers.
    """
    q = (q or "").strip()
    accept = (request.headers.get("accept") or "").lower()
    wants_json = "application/json" in accept and "text/html" not in accept

    # region agent log
    try:
        import json as _json, time as _time
        _payload = {
            "sessionId": "994e0d",
            "runId": "reset-search-debug",
            "hypothesisId": "H1",
            "location": "web/routes/pages.py:dupr_search_partial",
            "message": "incoming /dupr/search request",
            "data": {
                "q_received": q,
                "q_len": len(q),
                "slot": slot,
                "query_string": str(request.url.query),
                "referer": request.headers.get("referer"),
                "hx_request": request.headers.get("hx-request"),
                "hx_target": request.headers.get("hx-target"),
                "hx_trigger": request.headers.get("hx-trigger"),
                "hx_trigger_name": request.headers.get("hx-trigger-name"),
                "short_circuit_empty": len(q) < 2,
                "wants_json": wants_json,
            },
            "timestamp": int(_time.time() * 1000),
        }
        with open("/Users/jonchui/code/duprly/.cursor/debug-994e0d.log", "a") as _lf:
            _lf.write(_json.dumps(_payload) + "\n")
    except Exception:
        pass
    # endregion

    if len(q) < 2:
        if wants_json:
            return JSONResponse([])
        return HTMLResponse("")

    hits = dupr_live.search(session, query=q, limit=10)

    # region agent log
    try:
        import json as _json2, time as _time2
        _payload2 = {
            "sessionId": "994e0d",
            "runId": "reset-search-debug",
            "hypothesisId": "H5",
            "location": "web/routes/pages.py:dupr_search_partial:after_search",
            "message": "dupr_live.search returned",
            "data": {
                "q": q,
                "hit_count": len(hits),
                "first_hit_name": hits[0].full_name if hits else None,
                "referer": request.headers.get("referer"),
            },
            "timestamp": int(_time2.time() * 1000),
        }
        with open("/Users/jonchui/code/duprly/.cursor/debug-994e0d.log", "a") as _lf2:
            _lf2.write(_json2.dumps(_payload2) + "\n")
    except Exception:
        pass
    # endregion

    if wants_json:
        return JSONResponse([
            {
                "dupr_id": h.dupr_id,
                "full_name": h.full_name,
                "doubles": h.doubles,
                "doubles_reliability": h.doubles_reliability,
                "singles": h.singles,
                "image_url": h.image_url,
                "source": h.source,
                "stale": h.stale,
                "age": h.age,
                "gender": h.gender,
                "short_address": h.short_address,
                "short_dupr_id": h.short_dupr_id,
            }
            for h in hits
        ])

    return _tr(
        request,
        "partials/dupr_search.html",
        {
            "hits": hits,
            "slot": slot,
            "q": q,
            "live_available": dupr_live._has_live_credentials(),
        },
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
