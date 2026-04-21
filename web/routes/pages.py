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

# Hardcoded "current user" until we wire up a real login. When /forecast is
# opened with no path ids, we pre-seed slot 1 with this DUPR id so Jon's first
# click is picking an opponent instead of himself.
# NOTE: picked the rated "Jonadan Chui" profile (8106287732) rather than the
# NR "Ka Long Jonathan Chui" one (7411251891) so the default page renders a
# usable forecast — the NR one has doubles=None and would leave the
# score-preview card stuck waiting for a manual rating entry.
# Override with env var to point the default user at someone else (useful when
# demoing to another pickleballer).
DEFAULT_USER_DUPR_ID = os.environ.get("DUPRLY_DEFAULT_USER_DUPR_ID", "8106287732")


def _slot_prefill(session: Session, dupr_id: str) -> Optional[dict]:
    """
    Build the prefill dict `player_slot.html` expects from a cached DUPR row.

    Returns None when the id isn't in our cache — caller decides whether to
    leave the slot empty, show just the id, or 404 the whole page.

    Fields (all optional keys the template knows how to consume):
        duprid, name, rating, rel, age, gender, loc, img
    """
    hit = dupr_live.get_by_id(session, dupr_id)
    if hit is None:
        return None
    return {
        "duprid": hit.dupr_id,
        "name": hit.full_name,
        "rating": hit.doubles,
        "rel": hit.doubles_reliability,
        "age": hit.age,
        "gender": hit.gender,
        "loc": hit.short_address,
        "img": hit.image_url,
    }


def _parse_initial_score(g1_raw: Optional[str], g2_raw: Optional[str]) -> dict:
    """Clamp ?g1/?g2 query params into the 0..30 range the form expects."""
    def _coerce(v: Optional[str]) -> Optional[int]:
        if v is None or v == "":
            return None
        try:
            n = int(v)
        except ValueError:
            return None
        return max(0, min(30, n))
    return {"g1": _coerce(g1_raw), "g2": _coerce(g2_raw)}


@router.get("/forecast", response_class=HTMLResponse)
def forecast_page(
    request: Request,
    session: Session = Depends(get_session),
    g1: Optional[str] = Query(default=None),
    g2: Optional[str] = Query(default=None),
):
    """
    Forecast landing page.

    When there are no path ids we seed slot 1 with `DEFAULT_USER_DUPR_ID`
    (Jon by default) so the first interaction is picking opponents, not
    finding yourself. Slots 2–4 stay empty — we deliberately don't try to
    auto-pick recent opponents yet because that requires a live DUPR history
    call and on Vercel without DUPR secrets that call would 0-fill anyway.
    Picking the last opponents is a separate feature ("saved forecasts").
    """
    prefills: dict[int, dict] = {}
    seed = _slot_prefill(session, DEFAULT_USER_DUPR_ID)
    if seed is not None:
        prefills[1] = seed
    return _tr(
        request,
        "forecast.html",
        {
            "rows": None,
            "inputs": None,
            "prefills": prefills,
            "initial_score": _parse_initial_score(g1, g2),
        },
    )


@router.get("/forecast/{id1}/{id2}/{id3}/{id4}", response_class=HTMLResponse)
def forecast_page_with_ids(
    id1: str, id2: str, id3: str, id4: str,
    request: Request,
    session: Session = Depends(get_session),
    g1: Optional[str] = Query(default=None),
    g2: Optional[str] = Query(default=None),
):
    """
    Forecast page with all 4 DUPR ids baked into the URL.

    This is the canonical "shareable forecast" URL — copy/paste it and
    anyone lands on exactly the same pre-filled matchup.

    We render each slot even when the cache doesn't know the id (soft
    fallback): the duprid hidden input still gets populated, and the
    score-preview card will show the "waiting on DUPR" guidance card
    because rating/rel/name are missing. Users can then either refresh via
    the DUPR search or run the live refresh from the profile page.
    """
    path_ids = (id1, id2, id3, id4)
    prefills: dict[int, dict] = {}
    for slot_num, did in enumerate(path_ids, start=1):
        pf = _slot_prefill(session, did)
        if pf is None:
            # Soft fallback — keep the id in the slot so fillSlot-equivalent
            # state exists, but leave name/rating blank so the user sees a
            # clearly unresolved slot instead of a silent "player #" label.
            prefills[slot_num] = {"duprid": did}
        else:
            prefills[slot_num] = pf

    return _tr(
        request,
        "forecast.html",
        {
            "rows": None,
            "inputs": None,
            "prefills": prefills,
            "initial_score": _parse_initial_score(g1, g2),
        },
    )


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
    # target is the winner's *minimum match total*, not a single-game score.
    # 22 == "best-of-3 to 11" (winner wins 2 games to 11 each → totals ≥ 22).
    # The old value 11 was a leftover from when we had a Match Format dropdown
    # and caused forecast_matrix to emit single-game rows the fitted predictor
    # was never trained on. See _generate_candidate_scores().
    target: int = Form(default=22),
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
        return _tr(
            request,
            "partials/forecast_table.html",
            {"rows": rows, "inputs": inputs, "matrix_source": "local margin-aware"},
        )
    return _tr(request, "forecast.html", {"rows": rows, "inputs": inputs})


def _build_official_matrix_row(
    r1: float, r2: float, r3: float, r4: float,
    games1: int, games2: int,
    team_delta: float, expected_team1: float,
):
    """
    Promote one DUPR `rating_impacts[loser_score]` delta into a
    forecast_table-compatible `ForecastRow` for the chosen (games1, games2).

    Small shim so the HTMX matrix partial can render DUPR-backed numbers
    without branching on source — same row shape as the local predictor.
    """
    from web.services.forecast import ForecastRow, PlayerImpact

    winner = 1 if games1 > games2 else 2
    if winner == 1:
        d1 = d2 = team_delta
        d3 = d4 = -team_delta
    else:
        d1 = d2 = -team_delta
        d3 = d4 = team_delta
    impacts = [
        PlayerImpact(1, r1, d1, r1 + d1),
        PlayerImpact(2, r2, d2, r2 + d2),
        PlayerImpact(3, r3, d3, r3 + d3),
        PlayerImpact(4, r4, d4, r4 + d4),
    ]
    return ForecastRow(
        games1=games1, games2=games2, winner=winner,
        expected_games_team1=expected_team1, impacts=impacts,
        d1=d1, d2=d2, d3=d3, d4=d4,
    )


@router.post("/forecast/matrix/official", response_class=HTMLResponse)
def forecast_matrix_official(
    request: Request,
    r1: float = Form(...),
    r2: float = Form(...),
    r3: float = Form(...),
    r4: float = Form(...),
    rel1: Optional[float] = Form(default=None),
    rel2: Optional[float] = Form(default=None),
    rel3: Optional[float] = Form(default=None),
    rel4: Optional[float] = Form(default=None),
    duprid_1: str = Form(...),
    duprid_2: str = Form(...),
    duprid_3: str = Form(...),
    duprid_4: str = Form(...),
):
    """
    Full-score matrix rendered from DUPR's official forecaster.

    DUPR's `/forecast` endpoint returns a `rating_impacts[loser_score]`
    array per team per call — so a single round-trip for
    `winning_score=11` already covers every plausible 11-{0..10} and
    {0..10}-11 final. We call twice (to-11 and to-15) to cover both
    game formats, which is all the UI exposes.

    Happy path is ~2 DUPR API calls → up to ~52 rows, comfortably under
    a user's patience budget.
    """
    from web.services import dupr_forecast
    from web.services.forecast import get_predictor

    try:
        p1, p2, p3, p4 = (int(d) for d in (duprid_1, duprid_2, duprid_3, duprid_4))
    except (TypeError, ValueError):
        return HTMLResponse(
            '<div class="rounded-2xl bg-rose-500/10 ring-1 ring-rose-500/30 p-4 text-sm text-rose-300">'
            "DUPR matrix needs 4 numeric DUPR ids (short ids like "
            '<span class="mono">L2PLVZ</span> don\'t work). Pick all 4 players '
            "from the DUPR search so each slot carries a real id, then try again."
            "</div>"
        )

    expected = get_predictor().expected_games(r1, r2, r3, r4)
    rows = []
    errors: list[str] = []
    for winning_score in (11, 15):
        try:
            mf = dupr_forecast.forecast(
                teams=[(p1, p2), (p3, p4)],
                winning_score=winning_score,
                game_count=1,
            )
        except Exception as exc:  # noqa: BLE001
            errors.append(f"to-{winning_score}: {type(exc).__name__}: {exc}")
            continue
        for loser_score, delta in enumerate(mf.team_a.rating_impacts):
            rows.append(_build_official_matrix_row(
                r1, r2, r3, r4,
                games1=winning_score, games2=int(loser_score),
                team_delta=float(delta), expected_team1=expected,
            ))
        for loser_score, delta in enumerate(mf.team_b.rating_impacts):
            rows.append(_build_official_matrix_row(
                r1, r2, r3, r4,
                games1=int(loser_score), games2=winning_score,
                team_delta=float(delta), expected_team1=expected,
            ))

    if not rows:
        msg = " · ".join(errors) or "DUPR returned no forecast data for this matchup."
        return HTMLResponse(
            '<div class="rounded-2xl bg-rose-500/10 ring-1 ring-rose-500/30 p-4 text-sm text-rose-300">'
            f"DUPR forecast failed: {msg}"
            "</div>"
        )

    # Same sort as the local matrix so the two tables feel comparable:
    # blowouts first, then closer scores.
    rows.sort(key=lambda r: (-r.games1 + r.games2, -r.games1))
    inputs = {
        "r1": r1, "r2": r2, "r3": r3, "r4": r4,
        "rel1": rel1, "rel2": rel2, "rel3": rel3, "rel4": rel4,
    }
    return _tr(
        request,
        "partials/forecast_table.html",
        {"rows": rows, "inputs": inputs, "matrix_source": "DUPR official"},
    )


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
    duprid_1: Optional[str] = Query(default=None, alias="duprid1"),
    duprid_2: Optional[str] = Query(default=None, alias="duprid2"),
    duprid_3: Optional[str] = Query(default=None, alias="duprid3"),
    duprid_4: Optional[str] = Query(default=None, alias="duprid4"),
    games_played: int = Query(default=2, ge=1, le=3),
    event_label: Optional[str] = Query(default=None),
    venue_label: Optional[str] = Query(default=None),
    prefer: Optional[str] = Query(
        default=None,
        description=(
            "Delta source: 'official' (try DUPR, fall back to local on failure), "
            "'official_only' (DUPR only — render a guidance card instead of "
            "falling back), or 'local' (force the local model)."
        ),
    ),
    demo: int = Query(default=0, description="If 1, wrap the card in a standalone HTML+Tailwind shell for screenshots"),
):
    """
    Render a single DUPR-style match card for one concrete score.

    Used by the `/forecast` score picker — the user sets Team 1 vs Team 2
    game points (e.g. 11-7) and we rerender the card with live per-player
    deltas (pre / Δ / post), styled to match DUPR's native match UI.

    `prefer='official_only'` is what the forecast page ships in its default
    "DUPR only" mode. Instead of silently falling back to our fitted local
    predictor when DUPR is unavailable (missing creds, non-numeric ids,
    score like 12-10 that isn't first-to-N, API error), we return a small
    guidance card so the user knows exactly why no deltas are rendering.
    The local fallback path still exists behind the /settings "Show local
    model forecast" dev toggle.

    Scores are interpreted as single-game scores (to 11 or to 15) and
    scaled to match-totals before feeding the local predictor when used.
    Pass games_played=3 for a 2-1 split instead of a sweep.

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

    dupr_ids = (duprid_1, duprid_2, duprid_3, duprid_4)
    all_ids_present = all(d and str(d).isdigit() for d in dupr_ids)
    prefer_norm = (prefer or "").lower()
    official_only = prefer_norm == "official_only"

    row = None
    delta_source = None
    official_error: Optional[str] = None
    match_forecast = None  # MatchForecast when official path succeeds

    if prefer_norm != "local":
        if all_ids_present:
            try:
                row, match_forecast = _forecast_one_official_with_meta(
                    r1, r2, r3, r4, games1, games2,
                    dupr_ids=tuple(str(d) for d in dupr_ids),  # type: ignore[arg-type]
                )
                delta_source = "DUPR official"
            except Exception as exc:  # noqa: BLE001 — fall back or surface below
                official_error = f"{type(exc).__name__}: {exc}"
        elif official_only:
            official_error = (
                "Pick all 4 players from the DUPR search — DUPR's forecaster "
                "needs numeric DUPR ids (short ids like L2PLVZ don't work)."
            )

    # DUPR-only mode: if we couldn't build a row from the official API, render
    # a guidance card and bail. The user's /settings toggle asked us to *not*
    # silently fall back to the local model.
    if official_only and row is None:
        msg = official_error or "Pick all 4 players from the DUPR search to see the official forecast."
        return HTMLResponse(
            '<div class="rounded-3xl bg-slate-900 ring-1 ring-sky-700/40 p-6 text-sm">'
            '<div class="flex items-center gap-2 mb-2 flex-wrap">'
            '<span class="text-xs font-semibold text-sky-300 bg-sky-500/10 ring-1 ring-sky-500/30 px-3 py-1 rounded-full">Waiting on DUPR</span>'
            '<span class="text-slate-400">DUPR official forecast is the active mode</span>'
            "</div>"
            f'<p class="text-slate-300">{msg}</p>'
            '<p class="text-slate-500 text-xs mt-3">'
            'Switch to the local model in '
            '<a class="underline hover:text-slate-300" href="/settings">Settings → Dev</a> '
            'to iterate on ratings without a DUPR account.'
            "</p>"
            "</div>"
        )

    if row is None:
        g1_total, g2_total = _scale_to_match_total(games1, games2, games_played)
        row = forecast_svc.forecast_one(
            r1, r2, r3, r4, g1_total, g2_total,
            rel1=rel1, rel2=rel2, rel3=rel3, rel4=rel4,
        )
        row.games1 = games1
        row.games2 = games2
        if delta_source is None:
            delta_source = "local margin-aware"

    players = [
        {"name": name1, "age": age1, "gender": gender1, "short_address": loc1, "image_url": img1, "dupr_id": duprid_1},
        {"name": name2, "age": age2, "gender": gender2, "short_address": loc2, "image_url": img2, "dupr_id": duprid_2},
        {"name": name3, "age": age3, "gender": gender3, "short_address": loc3, "image_url": img3, "dupr_id": duprid_3},
        {"name": name4, "age": age4, "gender": gender4, "short_address": loc4, "image_url": img4, "dupr_id": duprid_4},
    ]
    if delta_source == "DUPR official":
        split_note = "DUPR per-game"
    else:
        split_note = "2-0 sweep" if games_played <= 2 else "2-1 split"

    # Pass DUPR's own per-team win% / predicted score through to the card so
    # we can render them next to the rating deltas (matches DUPR's in-app
    # "Forecaster" view).
    team1_meta = None
    team2_meta = None
    if match_forecast is not None:
        team1_meta = {
            "win_probability_pct": match_forecast.team_a.win_probability_pct,
            "predicted_score": match_forecast.team_a.predicted_losing_score,
        }
        team2_meta = {
            "win_probability_pct": match_forecast.team_b.win_probability_pct,
            "predicted_score": match_forecast.team_b.predicted_losing_score,
        }

    template = "partials/dupr_match_card_demo.html" if demo else "partials/dupr_match_card.html"
    return _tr(
        request,
        template,
        {
            "row": row,
            "players": players,
            "is_preview": True,
            "event_label": event_label or "DUPRLY forecast",
            "venue_label": venue_label or f"Score preview · {games1}-{games2} · {split_note}",
            "delta_source": delta_source,
            "official_error": official_error,
            "games1": games1,
            "games2": games2,
            "games_played": games_played,
            "team1_meta": team1_meta,
            "team2_meta": team2_meta,
        },
    )


def _forecast_one_official_with_meta(
    r1: float, r2: float, r3: float, r4: float,
    games1: int, games2: int,
    dupr_ids: tuple[str, str, str, str],
):
    """
    Like forecast_svc.forecast_one_official() but also returns the raw
    `MatchForecast` so the template can render DUPR's native per-team
    `winProbabilityPercentage` and predicted score alongside the deltas.

    Kept inline in the pages module because the returned meta shape is
    UI glue — not something other services consume.
    """
    from web.services import dupr_forecast
    from web.services.forecast import ForecastRow, PlayerImpact, _resolve_winning_score, get_predictor

    winning_score = _resolve_winning_score(games1, games2)
    if winning_score is None:
        raise dupr_forecast.DuprForecastUnavailable(
            f"Score {games1}-{games2} isn't first-to-11/15/21 — DUPR won't forecast it"
        )
    try:
        p1, p2, p3, p4 = (int(d) for d in dupr_ids)
    except (TypeError, ValueError) as e:
        raise dupr_forecast.DuprForecastUnavailable(f"Non-numeric DUPR id in {dupr_ids!r}: {e}")

    mf = dupr_forecast.forecast(
        teams=[(p1, p2), (p3, p4)],
        winning_score=winning_score,
        game_count=1,
    )

    winner = 1 if games1 > games2 else 2
    loser_score = games2 if winner == 1 else games1
    winning_team = mf.team_a if winner == 1 else mf.team_b
    if loser_score >= len(winning_team.rating_impacts):
        raise dupr_forecast.DuprForecastUnavailable(
            f"loser score {loser_score} >= impacts length {len(winning_team.rating_impacts)}"
        )
    team_delta = float(winning_team.rating_impacts[loser_score])
    if winner == 1:
        d1 = d2 = team_delta
        d3 = d4 = -team_delta
    else:
        d1 = d2 = -team_delta
        d3 = d4 = team_delta

    impacts = [
        PlayerImpact(1, r1, d1, r1 + d1),
        PlayerImpact(2, r2, d2, r2 + d2),
        PlayerImpact(3, r3, d3, r3 + d3),
        PlayerImpact(4, r4, d4, r4 + d4),
    ]
    expected = get_predictor().expected_games(r1, r2, r3, r4)
    row = ForecastRow(
        games1=games1, games2=games2, winner=winner,
        expected_games_team1=expected, impacts=impacts,
        d1=d1, d2=d2, d3=d3, d4=d4,
    )
    return row, mf


@router.post("/forecast/log", response_class=HTMLResponse)
def forecast_log(
    request: Request,
    session: Session = Depends(get_session),
    duprid_1: str = Form(..., alias="duprid1"),
    duprid_2: str = Form(..., alias="duprid2"),
    duprid_3: str = Form(..., alias="duprid3"),
    duprid_4: str = Form(..., alias="duprid4"),
    name1: str = Form(...),
    name2: str = Form(...),
    name3: str = Form(...),
    name4: str = Form(...),
    r1: float = Form(...),
    r2: float = Form(...),
    r3: float = Form(...),
    r4: float = Form(...),
    rel1: Optional[float] = Form(default=None),
    rel2: Optional[float] = Form(default=None),
    rel3: Optional[float] = Form(default=None),
    rel4: Optional[float] = Form(default=None),
    games1: int = Form(..., ge=0, le=30),
    games2: int = Form(..., ge=0, le=30),
    notes: Optional[str] = Form(default=None),
):
    """
    Log the current forecast-card score as a real JUPR match.

    The button on the DUPR-style match card POSTs this endpoint via HTMX.
    We upsert a JuprPlayer per DUPR id (seeded from the current rating +
    reliability the user has in the form) and append a JuprGame to the
    ledger. Returns a small HTML fragment that swaps in place of the card
    to confirm success + link to /jupr.

    This endpoint is intentionally ungated (no JUPR_WRITE_API_KEY check)
    because it's first-party UI glue — same-origin form submission from
    our own page. Tighten with a session token / CSRF if you expose the
    UI on a shared host.
    """
    dupr_ids = [duprid_1, duprid_2, duprid_3, duprid_4]
    names = [name1, name2, name3, name4]
    ratings = [r1, r2, r3, r4]
    reliabilities = [rel1, rel2, rel3, rel4]

    try:
        if games1 == games2:
            raise ValueError("Ties aren't rated — pick a different score.")
        players = []
        for did, nm, rt, rel in zip(dupr_ids, names, ratings, reliabilities):
            if not did or not nm:
                raise ValueError("All 4 slots need a DUPR-picked player (id + name).")
            players.append(
                jupr_svc.find_or_create_by_dupr_id(
                    session,
                    dupr_id=did,
                    full_name=nm,
                    seed_rating=rt,
                    seed_reliability=rel if rel is not None else 50.0,
                )
            )
        if len({p.id for p in players}) != 4:
            raise ValueError("All 4 players must be distinct.")
        game = jupr_svc.record_game(
            session,
            team1=[players[0].id, players[1].id],
            team2=[players[2].id, players[3].id],
            games1=games1, games2=games2,
            notes=notes,
        )
    except ValueError as e:
        return HTMLResponse(
            f'<div class="p-4 rounded-xl bg-rose-500/10 ring-1 ring-rose-500/30 text-rose-200 text-sm">'
            f'<strong>Could not log match:</strong> {e}'
            f'</div>',
            status_code=400,
        )

    return _tr(
        request,
        "partials/log_to_jupr_success.html",
        {
            "game": game,
            "players": players,
            "winner": game.winner,
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


# ---- Settings ---------------------------------------------------------------

@router.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request):
    """
    User-visible settings page.

    Every toggle here is client-side, backed by `localStorage` — these
    preferences change only what the browser renders / posts, never server
    state. We keep settings in localStorage (not cookies) because they're
    pure dev-experience flags; they don't need to survive device switches
    or be sent on every request.
    """
    return _tr(request, "settings.html", {})


# ---- Players search (standalone tab) ---------------------------------------

@router.get("/players", response_class=HTMLResponse)
def players_page(
    request: Request,
    q: Optional[str] = Query(default=None),
    session: Session = Depends(get_session),
):
    """
    DUPR-style "Players" tab: type a name / id / dashboard URL and jump
    straight to `/dupr/player/<id>`.

    The query lives in the URL (?q=chui) so every keystroke is shareable —
    paste the URL, land on the same results. We reuse the existing
    `/dupr/search` HTMX endpoint for live autocomplete; the initial server
    render pre-populates results when ?q is already set (first paint of a
    pasted URL has real content, not a blank page).
    """
    query = (q or "").strip()
    hits: list = []
    if len(query) >= 2:
        hits = list(dupr_live.search(session, query=query, limit=20))
    return _tr(
        request,
        "players.html",
        {
            "q": query,
            "hits": hits,
            "live_available": dupr_live._has_live_credentials(),
        },
    )


# ---- DUPR player profile (mirrors DUPR's /dashboard/player/<id>) -----------

_DUPR_LIVE_TIMEOUT_S = 6.0


def _run_with_timeout(fn, timeout_s: float, *args, **kwargs):
    """
    Run `fn(*args, **kwargs)` with a hard wall-clock timeout.

    Returns (result, error). On timeout or exception `result` is None and
    `error` is a short human-readable string.

    Used to guard live DUPR calls from the page handler — the current
    `dupr_client` implementation retries aggressively on 400-class responses
    (e.g. when an id isn't a real DUPR member), which can wedge the request
    thread for long enough that uvicorn workers pile up. A 6-second budget
    lets healthy calls succeed while keeping the page snappy for bad ids.
    The underlying client call keeps running in the background thread until
    it returns on its own; that's acceptable because
    `_get_live_client()` is a singleton and subsequent requests reuse it.
    """
    import concurrent.futures

    # We deliberately don't cancel the future — Python can't interrupt a
    # blocking socket read. The worker thread will finish when the retry
    # loop does; meanwhile the HTTP request is already free to return.
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(fn, *args, **kwargs)
        try:
            return fut.result(timeout=timeout_s), None
        except concurrent.futures.TimeoutError:
            return None, f"timed out after {timeout_s:.0f}s"
        except Exception as exc:  # noqa: BLE001
            return None, f"{type(exc).__name__}: {exc}"


@router.get("/dupr/player/{dupr_id}", response_class=HTMLResponse)
def dupr_player_page(
    dupr_id: str,
    request: Request,
    session: Session = Depends(get_session),
):
    """
    Render a DUPR-style player profile for a given DUPR id.

    V1 behaviour:
    - Always show whatever we already have cached locally (avatar, name,
      ratings, age/gender/location) so the page is useful even when DUPR
      live creds are absent (e.g. Vercel without the DUPR secrets).
    - When live creds exist, upsert a fresh snapshot AND pull the match
      history via `DuprClient.get_member_match_history_p` so the page
      shows an actual game log like DUPR's app does.
    - Every live call is bounded by `_DUPR_LIVE_TIMEOUT_S` so a bad id or
      slow upstream can't wedge the request thread. Bad ids return a 404
      card just like "no cache" ids.
    - Every failure below the cache is best-effort; we render whatever
      subset of the page we have data for and surface the rest as a note.
    """
    dupr_id = (dupr_id or "").strip()
    cached = dupr_live.get_by_id(session, dupr_id)
    live_error: Optional[str] = None
    match_rows: list = []
    refresh_failed = False

    if dupr_live._has_live_credentials():
        # 1) Refresh the cache entry. If the refresh can't produce a row
        #    (bad id, timeout, 4xx retry storm) we skip the history fetch —
        #    calling /history for a bad id just gets us another retry
        #    storm on the dupr_client side.
        fresh, err = _run_with_timeout(
            dupr_live.refresh, _DUPR_LIVE_TIMEOUT_S, session, dupr_id,
        )
        if err:
            live_error = f"Refresh failed: {err}"
            refresh_failed = True
        elif fresh is not None:
            cached = fresh
        else:
            refresh_failed = True

        # 2) History fetch — only attempt when we got something real from
        #    the cache or the refresh; otherwise the id is almost certainly
        #    invalid and we'd just waste a DUPR round-trip on retries.
        if not refresh_failed or cached is not None:
            def _fetch_history():
                client = dupr_live._get_live_client()
                rc_h, raw = client.get_member_match_history_p(dupr_id)
                return (rc_h, raw)

            result, err = _run_with_timeout(_fetch_history, _DUPR_LIVE_TIMEOUT_S)
            if err:
                msg = f"History fetch failed: {err}"
                live_error = f"{live_error} · {msg}" if live_error else msg
            elif result is not None:
                rc_h, raw = result
                if rc_h == 200 and isinstance(raw, list):
                    match_rows = _summarize_dupr_matches(raw, dupr_id, limit=25)

    if cached is None and not match_rows:
        return HTMLResponse(
            f'<div class="max-w-2xl mx-auto p-8 text-center">'
            f'<h1 class="text-2xl font-bold mb-2">Unknown DUPR player</h1>'
            f'<p class="text-slate-400">We have no cached record for '
            f'<span class="mono">{dupr_id}</span>, and live DUPR lookup '
            f'is unavailable.</p></div>',
            status_code=404,
        )

    return _tr(
        request,
        "dupr_player.html",
        {
            "player": cached,
            "dupr_id": dupr_id,
            "matches": match_rows,
            "live_error": live_error,
            "has_live_creds": dupr_live._has_live_credentials(),
        },
    )


def _summarize_dupr_matches(raw_matches: list, dupr_id: str, limit: int = 25) -> list:
    """
    Normalize DUPR's match-history response into compact dicts for the
    player profile page.

    We intentionally keep this loose (dict-of-strings-and-floats) instead
    of a dataclass so the template can render partial matches — DUPR's
    history payload shape drifts between endpoints and we don't want to
    drop a whole match when one field is missing.
    """
    from datetime import datetime as _dt

    out: list = []
    for m in raw_matches[:limit]:
        if not isinstance(m, dict):
            continue
        teams = m.get("teams") if isinstance(m.get("teams"), list) else []
        team_views = []
        won_by = None
        target_slot = None
        for t_idx, t in enumerate(teams):
            if not isinstance(t, dict):
                continue
            players = t.get("player1"), t.get("player2")
            names = []
            for p_idx, p in enumerate(players):
                if not isinstance(p, dict):
                    continue
                pid = str(p.get("id") or p.get("userId") or "")
                full = (
                    p.get("fullName")
                    or " ".join(x for x in [p.get("firstName"), p.get("lastName")] if x).strip()
                )
                names.append({
                    "dupr_id": pid,
                    "name": full or pid or "—",
                    "image_url": p.get("imageUrl"),
                })
                if pid == str(dupr_id):
                    target_slot = t_idx  # 0 or 1 (team A/B)
            score = t.get("game1") if t.get("game1") is not None else t.get("score")
            team_views.append({
                "players": names,
                "score": score,
                "winner": bool(t.get("winner")),
            })
            if t.get("winner"):
                won_by = t_idx
        event_date = m.get("eventDate") or m.get("matchDate") or m.get("date")
        try:
            ev_iso = _dt.fromisoformat(str(event_date).replace("Z", "+00:00")).date().isoformat() if event_date else None
        except Exception:  # noqa: BLE001
            ev_iso = str(event_date) if event_date else None
        out.append({
            "match_id": str(m.get("matchId") or m.get("id") or ""),
            "event_date": ev_iso,
            "venue": m.get("venue") or m.get("clubName") or m.get("eventName"),
            "teams": team_views,
            "won_by_team_index": won_by,
            "target_team_index": target_slot,
            "is_win": target_slot is not None and target_slot == won_by,
        })
    return out


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

    if len(q) < 2:
        if wants_json:
            return JSONResponse([])
        return HTMLResponse("")

    hits = dupr_live.search(session, query=q, limit=10)

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
