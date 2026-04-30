"""
Thin wrapper around DUPR's official match forecaster.

Endpoints:
- POST `/match/v1.0/expected-score` → predicted *game scores* only.
- POST `/match/v1.0/forecast`       → game scores + `winProbabilityPercentage`
  + `winningRatingImpacts` arrays (one delta per possible losing-side game
  count, so length == winningScore).

Why a wrapper and not a thin proxy?

1. Credentials: live calls need `DUPR_USERNAME` / `DUPR_PASSWORD` in env.
   When those are missing we fall back to the canonical Proxyman captures
   in `tests/fixtures/dupr_api/` so the route still renders something
   useful — and tests don't need live auth.
2. Normalization: DUPR returns integer-valued floats (e.g. `11.0`) and
   nulls inconsistently; we normalize to a flat dataclass that the
   forecast / goal / MCP layers can all consume.
3. Identity: we preserve both `player1Id` / `player2Id` so the UI can
   label deltas per-player (DUPR only reports per-team impacts —
   individual player deltas are *inferred* from team impact + the
   player's reliability, which is a separate follow-up).

Fixture fallback is keyed on `winningScore` because the captured
fixtures use the same 4-player id set. Callers wanting realistic
output should set `DUPRLY_USE_FIXTURES=1` or pass `use_fixtures=True`.

See `tests/fixtures/dupr_api/README.md` for the request/response contract.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_LOG = logging.getLogger("duprly.dupr_forecast")

_FIXTURE_DIR = Path(__file__).resolve().parent.parent.parent / "tests" / "fixtures" / "dupr_api"

_CLIENT_LOCK = threading.Lock()
_CLIENT_SINGLETON: Any | None = None


class DuprForecastUnavailable(RuntimeError):
    """Raised when we can neither call DUPR live nor load a matching fixture."""


@dataclass
class TeamForecast:
    player1_id: int
    player2_id: Optional[int]
    predicted_losing_score: Optional[float]
    win_probability_pct: Optional[float]
    rating_impacts: List[float] = field(default_factory=list)

    @property
    def impact_if_blowout_win(self) -> Optional[float]:
        """Rating delta if this team wins AND loser scored 0. impacts[0]."""
        return self.rating_impacts[0] if self.rating_impacts else None

    @property
    def impact_if_tight_win(self) -> Optional[float]:
        """Rating delta if this team wins AND loser scored winningScore-1."""
        return self.rating_impacts[-1] if self.rating_impacts else None


@dataclass
class MatchForecast:
    winning_score: int
    event_format: str
    match_source: str
    match_type: str
    game_count: int
    team_a: TeamForecast
    team_b: TeamForecast
    source: str  # "live" | "fixture"
    raw: Dict[str, Any] = field(default_factory=dict)


# ---- env / creds -----------------------------------------------------------

def _has_live_credentials() -> bool:
    return bool(os.environ.get("DUPR_USERNAME") and os.environ.get("DUPR_PASSWORD"))


def _fixtures_forced() -> bool:
    return os.environ.get("DUPRLY_USE_FIXTURES", "").strip() in {"1", "true", "yes", "on"}


def _get_live_client():
    global _CLIENT_SINGLETON
    if not _has_live_credentials():
        raise DuprForecastUnavailable(
            "DUPR live forecast needs DUPR_USERNAME + DUPR_PASSWORD env vars"
        )
    with _CLIENT_LOCK:
        if _CLIENT_SINGLETON is None:
            from dupr_client import DuprClient  # lazy import
            c = DuprClient()
            rc = c.auth_user(os.environ["DUPR_USERNAME"], os.environ["DUPR_PASSWORD"])
            if rc not in (0, 200):
                raise DuprForecastUnavailable(f"DUPR auth failed rc={rc}")
            _CLIENT_SINGLETON = c
    return _CLIENT_SINGLETON


# ---- fixtures --------------------------------------------------------------

def _fixture_path(endpoint: str, winning_score: int) -> Optional[Path]:
    # Map (endpoint, winning_score) → concrete file. Small enough to spell out.
    table = {
        ("expected-score", 11): "06-expected-score-to-11.response.json",
        ("forecast",        11): "07-forecast-to-11.response.json",
        ("expected-score", 15): "17-expected-score-to-15.response.json",
        ("forecast",        15): "18-forecast-to-15.response.json",
    }
    name = table.get((endpoint, winning_score))
    if not name:
        return None
    p = _FIXTURE_DIR / name
    return p if p.exists() else None


def _load_fixture(endpoint: str, winning_score: int) -> Optional[Dict[str, Any]]:
    p = _fixture_path(endpoint, winning_score)
    if p is None:
        return None
    with p.open() as f:
        data = json.load(f)
    # Strip the _meta block so the shape matches a real DUPR response.
    data = {k: v for k, v in data.items() if k != "_meta"}
    return data


# ---- core ------------------------------------------------------------------

def _parse_team(t: Dict[str, Any]) -> TeamForecast:
    impacts_raw = t.get("winningRatingImpacts") or []
    return TeamForecast(
        player1_id=int(t["player1Id"]),
        player2_id=int(t["player2Id"]) if t.get("player2Id") is not None else None,
        predicted_losing_score=_as_float(t.get("score")),
        win_probability_pct=_as_float(t.get("winProbabilityPercentage")),
        rating_impacts=[float(x) for x in impacts_raw if x is not None],
    )


def _as_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _build_request(
    teams: List[Tuple[int, Optional[int]]],
    *,
    event_format: str,
    match_source: str,
    match_type: str,
    game_count: int,
    winning_score: int,
) -> Dict[str, Any]:
    return {
        "eventFormat": event_format,
        "gameCount": game_count,
        "matchSource": match_source,
        "matchType": match_type,
        "teams": [
            {"player1Id": p1, "player2Id": p2} if p2 is not None else {"player1Id": p1}
            for (p1, p2) in teams
        ],
        "winningScore": winning_score,
    }


def _to_match_forecast(raw: Dict[str, Any], req: Dict[str, Any], source: str) -> MatchForecast:
    teams_raw = raw.get("teams") or []
    if len(teams_raw) != 2:
        raise DuprForecastUnavailable(
            f"DUPR response missing 2-team shape: {json.dumps(raw)[:200]}"
        )
    return MatchForecast(
        winning_score=int(req["winningScore"]),
        event_format=req["eventFormat"],
        match_source=req["matchSource"],
        match_type=req["matchType"],
        game_count=int(req["gameCount"]),
        team_a=_parse_team(teams_raw[0]),
        team_b=_parse_team(teams_raw[1]),
        source=source,
        raw=raw,
    )


def expected_score(
    teams: List[Tuple[int, Optional[int]]],
    *,
    winning_score: int = 11,
    event_format: str = "DOUBLES",
    match_source: str = "CLUB",
    match_type: str = "SIDE_ONLY",
    game_count: int = 1,
    use_fixtures: bool = False,
) -> MatchForecast:
    """
    Call DUPR `/match/v1.0/expected-score`.

    Response has `score` per team but `winProbabilityPercentage` and
    `winningRatingImpacts` are always null — see
    `tests/fixtures/dupr_api/06-*.response.json`.
    """
    req = _build_request(
        teams,
        event_format=event_format,
        match_source=match_source,
        match_type=match_type,
        game_count=game_count,
        winning_score=winning_score,
    )
    return _dispatch("expected-score", req, use_fixtures=use_fixtures)


def forecast(
    teams: List[Tuple[int, Optional[int]]],
    *,
    winning_score: int = 11,
    event_format: str = "DOUBLES",
    match_source: str = "CLUB",
    match_type: str = "SIDE_ONLY",
    game_count: int = 1,
    use_fixtures: bool = False,
) -> MatchForecast:
    """
    Call DUPR `/match/v1.0/forecast` — the richer endpoint that powers the
    "DUPR Forecaster" view in the app. Returns per-team rating deltas for
    every possible losing-side game count (length == winning_score).

    See `tests/fixtures/dupr_api/07-*.response.json` for sample output.
    """
    req = _build_request(
        teams,
        event_format=event_format,
        match_source=match_source,
        match_type=match_type,
        game_count=game_count,
        winning_score=winning_score,
    )
    return _dispatch("forecast", req, use_fixtures=use_fixtures)


def _dispatch(endpoint: str, req: Dict[str, Any], *, use_fixtures: bool) -> MatchForecast:
    want_fixtures = use_fixtures or _fixtures_forced() or not _has_live_credentials()

    if want_fixtures:
        raw = _load_fixture(endpoint, int(req["winningScore"]))
        if raw is None:
            raise DuprForecastUnavailable(
                f"No DUPR fixture for endpoint={endpoint} winningScore={req['winningScore']} "
                f"and live creds are missing or disabled. Provide DUPR_USERNAME/PASSWORD or "
                f"pass a supported winning_score (11 or 15)."
            )
        _LOG.info("dupr %s via fixture winningScore=%s", endpoint, req["winningScore"])
        return _to_match_forecast(raw, req, source="fixture")

    # Live path.
    client = _get_live_client()
    method = "get_forecast" if endpoint == "forecast" else "get_expected_score"
    fn = getattr(client, method)
    try:
        rc, resp = fn(
            teams=req["teams"],
            event_format=req["eventFormat"],
            match_source=req["matchSource"],
            match_type=req["matchType"],
            game_count=req["gameCount"],
            winning_score=req["winningScore"],
        )
    except Exception as e:  # noqa: BLE001 — surface SSL / socket errors as 503
        _LOG.warning("dupr %s live call raised %r", endpoint, e)
        raise DuprForecastUnavailable(
            f"DUPR {endpoint} live call failed: {type(e).__name__}: {e}. "
            f"Set use_fixtures=true or DUPRLY_USE_FIXTURES=1 to use the Proxyman "
            f"sample response instead."
        ) from e
    if rc != 200 or not isinstance(resp, dict):
        raise DuprForecastUnavailable(f"DUPR {endpoint} failed rc={rc}")
    _LOG.info("dupr %s live winningScore=%s", endpoint, req["winningScore"])
    return _to_match_forecast(resp, req, source="live")
