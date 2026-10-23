"""Tournament-level DUPR forecast helpers.

This module powers the /forecast "Tournament planner" tab. It intentionally
keeps the model self-contained because the existing forecast service models
best-of-3 match totals, while this feature forecasts single games to 11.
"""

from __future__ import annotations

import html
import json
import math
import re
import uuid
from dataclasses import asdict
from dataclasses import dataclass
from itertools import product
from typing import Iterable, Optional
from urllib.parse import urlparse

import requests
from sqlalchemy.orm import Session

from web.services import dupr_live

K_BASE = 0.0816
WINNING_SCORE = 11
DEFAULT_TARGET_RATING = 4.0

_RATING_RE = re.compile(r"^(?:[1-8](?:\.\d+)?|--|NR)$", re.IGNORECASE)
_AGE_RE = re.compile(r"^(?:\d{1,3}|--)$")
_GENDER_RE = re.compile(r"^(?:M|F|MALE|FEMALE|--)$", re.IGNORECASE)
_STATE_RE = re.compile(r"\b[A-Z]{2}\b")

_SKIP_LINES = {
    "teams",
    "team",
    "skill",
    "age",
    "gender",
    "city/state",
    "teams skill age gender city/state",
    "all",
    "registered",
    "waitlist",
    "event details",
}

_FIRST_NAME_ALIASES = {
    "jonathan": ["Jon"],
    "jake": ["Jacob"],
    "jacob": ["Jake"],
    "matthew": ["Matt"],
    "matt": ["Matthew"],
    "herb": ["Herbert"],
    "jeff": ["Jeffrey"],
}


@dataclass
class TournamentPlayer:
    name: str
    pasted_rating: Optional[float] = None
    age: Optional[str] = None
    gender: Optional[str] = None
    location: Optional[str] = None
    dupr_id: Optional[str] = None
    dupr_name: Optional[str] = None
    doubles: Optional[float] = None
    reliability: Optional[float] = None
    source: str = "paste"
    note: Optional[str] = None

    @property
    def rating(self) -> Optional[float]:
        return self.doubles if self.doubles is not None else self.pasted_rating

    @property
    def display_name(self) -> str:
        return self.dupr_name or self.name


@dataclass
class TournamentTeam:
    label: str
    players: tuple[TournamentPlayer, TournamentPlayer]

    @property
    def avg_rating(self) -> Optional[float]:
        ratings = [p.rating for p in self.players]
        if any(r is None for r in ratings):
            return None
        return float(sum(ratings) / 2)


@dataclass
class MatchForecast:
    opponent_label: str
    opponent_avg: float
    avg_diff: float
    win_probability: float
    win_11_0: float
    win_11_3: float
    win_11_5: float
    win_11_7: float
    win_11_9: float
    win_11_10: float


@dataclass
class TargetPath:
    title: str
    scores: str
    projected_rating: float
    delta: float
    note: str
    hits_target: bool


@dataclass
class TournamentAnalysis:
    players: list[TournamentPlayer]
    teams: list[TournamentTeam]
    target_player: TournamentPlayer
    target_team: TournamentTeam
    target_rating: float
    current_rating: float
    target_gap: float
    forecasts: list[MatchForecast]
    same_score_sweeps: list[TargetPath]
    target_paths: list[TargetPath]
    warnings: list[str]
    source_text: str


def _clean_lines(raw_text: str) -> list[str]:
    return [line.strip() for line in (raw_text or "").splitlines() if line.strip()]


def _is_rating_line(line: str) -> bool:
    return bool(_RATING_RE.match(line.strip()))


def _is_age_line(line: str) -> bool:
    return bool(_AGE_RE.match(line.strip()))


def _is_gender_line(line: str) -> bool:
    return bool(_GENDER_RE.match(line.strip()))


def _rating_value(line: Optional[str]) -> Optional[float]:
    if not line:
        return None
    s = line.strip()
    if s in {"--", ""} or s.upper() == "NR":
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _looks_like_name(line: str) -> bool:
    s = line.strip()
    if not s or s == "--":
        return False
    lowered = s.lower()
    if lowered in _SKIP_LINES or "skill age gender" in lowered:
        return False
    if _is_rating_line(s) or _is_age_line(s) or _is_gender_line(s):
        return False
    if _looks_like_location(s):
        return False
    # Names from PickleballBrackets are usually two tokens, but allow "Brady S".
    return bool(re.search(r"[A-Za-z]", s)) and len(s.split()) >= 2


def _looks_like_location(line: str) -> bool:
    s = line.strip()
    if not s or s == "--":
        return False
    tokens = s.split()
    if not tokens:
        return False
    if tokens[-1].upper() in {"CO", "CA", "TX", "AZ", "UT", "NY", "FL", "WA", "OR"}:
        # Avoid classifying "Giuliano H" or "Brady S" as locations. A
        # location ending in a state code usually has a city token before it.
        return len(tokens) >= 2 and not _is_rating_line(tokens[0])
    return False


def parse_roster_text(raw_text: str) -> list[TournamentPlayer]:
    """Parse copied PickleballBrackets-style roster text into players.

    Expected shape is repeated blocks of:
      name, skill/rating, age, gender, location
    But we tolerate missing trailing fields and skip blank lines.
    """
    lines = _clean_lines(raw_text)
    players: list[TournamentPlayer] = []
    i = 0
    while i < len(lines):
        name = lines[i]
        # The copied PB table is regular enough that a real player row starts
        # with name, then immediate skill/rating. If the next line is another
        # name or a city/state, this line is a header/location and must be
        # skipped. This is what prevents "Boulder CO" from becoming a player.
        if not _looks_like_name(name) or i + 1 >= len(lines) or not _is_rating_line(lines[i + 1]):
            i += 1
            continue
        i += 1

        rating = _rating_value(lines[i])
        i += 1
        age = None
        gender = None
        location = None

        if i < len(lines) and _is_age_line(lines[i]):
            age = None if lines[i] == "--" else lines[i]
            i += 1
        if i < len(lines) and _is_gender_line(lines[i]):
            gender = None if lines[i] == "--" else lines[i][:1].upper()
            i += 1
        if i < len(lines):
            maybe_location = lines[i]
            if maybe_location == "--" or _looks_like_location(maybe_location):
                location = None if maybe_location == "--" else maybe_location
                i += 1

        players.append(
            TournamentPlayer(
                name=" ".join(name.split()),
                pasted_rating=rating,
                age=age,
                gender=gender,
                location=location,
            )
        )
    return players


def analysis_to_payload(analysis: TournamentAnalysis) -> dict:
    """Serialize an analysis into a JSON-safe cache/share payload."""
    payload = asdict(analysis)
    for player in payload["players"]:
        player["rating"] = player["doubles"] if player["doubles"] is not None else player["pasted_rating"]
        player["display_name"] = player["dupr_name"] or player["name"]
    for team in payload["teams"]:
        ratings = [
            p["doubles"] if p["doubles"] is not None else p["pasted_rating"]
            for p in team["players"]
        ]
        team["avg_rating"] = None if any(r is None for r in ratings) else sum(ratings) / 2
    target_player = payload["target_player"]
    target_player["rating"] = (
        target_player["doubles"]
        if target_player["doubles"] is not None
        else target_player["pasted_rating"]
    )
    target_player["display_name"] = target_player["dupr_name"] or target_player["name"]
    ratings = [
        p["doubles"] if p["doubles"] is not None else p["pasted_rating"]
        for p in payload["target_team"]["players"]
    ]
    payload["target_team"]["avg_rating"] = None if any(r is None for r in ratings) else sum(ratings) / 2
    return payload


def create_share_id() -> str:
    return uuid.uuid4().hex[:12]


def payload_to_json(payload: dict) -> str:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True)


def payload_from_json(raw: str) -> dict:
    return json.loads(raw)


def fetch_public_bracket_text(url: str, timeout_s: float = 8.0) -> str:
    """Best-effort public page fetch for bracket URLs.

    Protected PickleballBrackets pages generally render through authenticated
    browser state, so this works only when the URL exposes enough static HTML.
    """
    parsed = urlparse((url or "").strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Enter a full http(s) PickleballBrackets URL.")
    if "pickleball" not in parsed.netloc.lower():
        raise ValueError("For now URL import only accepts PickleballBrackets-style URLs.")

    resp = requests.get(
        parsed.geturl(),
        timeout=timeout_s,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
            )
        },
    )
    if resp.status_code in {401, 403}:
        raise ValueError("That bracket appears to require login. Paste the roster text instead.")
    resp.raise_for_status()
    text = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", " ", resp.text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", "\n", text)
    text = html.unescape(text)
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())


def _resolve_players(
    session: Session,
    players: list[TournamentPlayer],
    *,
    live_lookup: bool,
) -> list[str]:
    warnings: list[str] = []
    for p in players:
        if not live_lookup:
            continue
        hits = []
        try:
            seen: set[str] = set()
            for query in _lookup_queries(p.name):
                for h in dupr_live.search(session, query, limit=8, live_fallback=True):
                    if h.dupr_id in seen:
                        continue
                    seen.add(h.dupr_id)
                    hits.append(h)
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"DUPR lookup failed for {p.name}: {exc}")
            continue
        hit = _best_hit_for_player(p, hits)
        if hit is None:
            p.note = "No DUPR match; using pasted skill"
            continue
        p.dupr_id = hit.dupr_id
        p.dupr_name = hit.full_name
        p.doubles = hit.doubles
        p.reliability = hit.doubles_reliability
        p.source = hit.source
        if hit.full_name.lower() != p.name.lower():
            p.note = f"Matched to {hit.full_name}"
        if p.doubles is None and p.pasted_rating is not None:
            p.note = (p.note + "; " if p.note else "") + "DUPR is NR; using pasted skill"
    return warnings


def _lookup_queries(name: str) -> list[str]:
    parts = [p for p in re.split(r"\s+", name.strip()) if p]
    queries = [name.strip()]
    if len(parts) >= 2:
        first = parts[0].lower()
        last = parts[-1]
        for alias in _FIRST_NAME_ALIASES.get(first, []):
            queries.append(f"{alias} {last}")
        queries.append(last)
    out: list[str] = []
    seen: set[str] = set()
    for q in queries:
        if q and q.lower() not in seen:
            seen.add(q.lower())
            out.append(q)
    return out


def _state_hint(location: Optional[str]) -> Optional[str]:
    if not location:
        return None
    tokens = [t.strip(",").upper() for t in location.split() if t.strip(",")]
    for token in reversed(tokens):
        if len(token) == 2 and token.isalpha():
            return token
    return None


def _best_hit_for_player(player: TournamentPlayer, hits):
    if not hits:
        return None
    parts = [p for p in re.split(r"\s+", player.name.strip().lower()) if p]
    first = parts[0] if parts else ""
    last = parts[-1] if len(parts) >= 2 else ""
    aliases = {first, *[a.lower() for a in _FIRST_NAME_ALIASES.get(first, [])]}
    state = _state_hint(player.location)

    def score(hit) -> tuple[int, float]:
        full = (hit.full_name or "").strip().lower()
        full_parts = [p for p in full.split() if p]
        h_first = full_parts[0] if full_parts else ""
        h_last = full_parts[-1] if len(full_parts) >= 2 else ""
        s = 0
        if full == player.name.strip().lower():
            s += 120
        if last and h_last == last:
            s += 70
        if h_first in aliases:
            s += 45
        elif first and h_first.startswith(first[:3]):
            s += 25
        elif first and h_first[:1] == first[:1] and last and h_last == last:
            s += 20
        if hit.doubles is not None:
            s += 15
        hit_loc_tokens = hit.short_address.upper().replace(",", " ").split() if hit.short_address else []
        if state and state in hit_loc_tokens:
            s += 12
        # Prefer names that are not NR when scores tie; no need for extra
        # precision beyond that.
        rating = float(hit.doubles or 0.0)
        return (s, rating)

    best = max(hits, key=score)
    # Avoid wild last-name-only false positives unless the match has at least
    # a weak name signal. If there is no score, use pasted skill instead.
    if score(best)[0] < 60 and best.doubles is None:
        return None
    return best


def pair_teams(players: list[TournamentPlayer]) -> list[TournamentTeam]:
    teams: list[TournamentTeam] = []
    for idx in range(0, len(players) - 1, 2):
        p1, p2 = players[idx], players[idx + 1]
        teams.append(TournamentTeam(label=f"{p1.name} / {p2.name}", players=(p1, p2)))
    return teams


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def _mov(loser_score: int) -> float:
    loser_score = max(0, min(WINNING_SCORE - 1, int(loser_score)))
    return ((WINNING_SCORE - loser_score) / WINNING_SCORE) ** 1.8


def _win_probability(my_avg: float, opp_avg: float) -> float:
    return _sigmoid(3.0 * (my_avg - opp_avg))


def _target_delta(
    target_rating_now: float,
    partner_rating: float,
    opponent_avg: float,
    *,
    won: bool,
    loser_score: int,
) -> float:
    my_avg = (target_rating_now + partner_rating) / 2.0
    p_win = _win_probability(my_avg, opponent_avg)
    return K_BASE * _mov(loser_score) * ((1.0 - p_win) if won else -p_win)


def _forecast_matches(
    target_team: TournamentTeam,
    opponent_teams: Iterable[TournamentTeam],
) -> list[MatchForecast]:
    my_avg = target_team.avg_rating
    if my_avg is None:
        return []
    out: list[MatchForecast] = []
    for opp in opponent_teams:
        opp_avg = opp.avg_rating
        if opp_avg is None:
            continue
        p_win = _win_probability(my_avg, opp_avg)
        deltas = {
            l: K_BASE * _mov(l) * (1.0 - p_win)
            for l in (0, 3, 5, 7, 9, 10)
        }
        out.append(
            MatchForecast(
                opponent_label=opp.label,
                opponent_avg=opp_avg,
                avg_diff=my_avg - opp_avg,
                win_probability=p_win,
                win_11_0=deltas[0],
                win_11_3=deltas[3],
                win_11_5=deltas[5],
                win_11_7=deltas[7],
                win_11_9=deltas[9],
                win_11_10=deltas[10],
            )
        )
    return out


def _format_scores(path: list[tuple[str, str]]) -> str:
    return "; ".join(f"{label}: {score}" for label, score in path)


def _path_delta(
    target_start: float,
    partner_rating: float,
    opponents: list[TournamentTeam],
    choices: list[tuple[bool, int]],
) -> tuple[float, list[tuple[str, str]]]:
    rating = target_start
    details: list[tuple[str, str]] = []
    for opp, (won, loser_score) in zip(opponents, choices):
        opp_avg = opp.avg_rating
        if opp_avg is None:
            continue
        d = _target_delta(rating, partner_rating, opp_avg, won=won, loser_score=loser_score)
        rating += d
        score = f"11-{loser_score}" if won else f"{loser_score}-11"
        details.append((opp.label, score))
    return rating - target_start, details


def _same_score_sweeps(
    target_start: float,
    partner_rating: float,
    opponents: list[TournamentTeam],
    target_rating: float,
) -> list[TargetPath]:
    rows: list[TargetPath] = []
    for loser_score in (0, 1, 2, 3, 5):
        choices = [(True, loser_score)] * len(opponents)
        delta, _ = _path_delta(target_start, partner_rating, opponents, choices)
        projected = target_start + delta
        rows.append(
            TargetPath(
                title=f"All 11-{loser_score}",
                scores=f"Every game 11-{loser_score}",
                projected_rating=projected,
                delta=delta,
                note="Same margin against every opponent.",
                hits_target=projected >= target_rating,
            )
        )
    return rows


def _best_path_by_wins(
    target_start: float,
    partner_rating: float,
    opponents: list[TournamentTeam],
    wins: int,
) -> TargetPath:
    states: dict[int, tuple[float, list[tuple[str, str]]]] = {0: (target_start, [])}
    for opp in opponents:
        next_states: dict[int, tuple[float, list[tuple[str, str]]]] = {}
        for win_count, (rating, path) in states.items():
            opp_avg = opp.avg_rating
            if opp_avg is None:
                continue
            for won in (True, False):
                for loser_score in range(0, WINNING_SCORE):
                    nwins = win_count + (1 if won else 0)
                    if nwins > wins:
                        continue
                    d = _target_delta(rating, partner_rating, opp_avg, won=won, loser_score=loser_score)
                    new_rating = rating + d
                    score = f"11-{loser_score}" if won else f"{loser_score}-11"
                    current = next_states.get(nwins)
                    if current is None or new_rating > current[0]:
                        next_states[nwins] = (new_rating, path + [(opp.label, score)])
        states = next_states
    rating, path = states.get(wins, (target_start, []))
    return TargetPath(
        title=f"Best possible {wins}-{len(opponents) - wins}",
        scores=_format_scores(path),
        projected_rating=rating,
        delta=rating - target_start,
        note="Optimistic upper bound for that win count.",
        hits_target=False,
    )


def _barely_enough_all_wins(
    target_start: float,
    partner_rating: float,
    opponents: list[TournamentTeam],
    target_rating: float,
) -> Optional[TargetPath]:
    if not opponents or len(opponents) > 7:
        return None
    best: Optional[tuple[int, float, list[tuple[str, str]]]] = None
    for loser_scores in product(range(WINNING_SCORE), repeat=len(opponents)):
        choices = [(True, l) for l in loser_scores]
        delta, path = _path_delta(target_start, partner_rating, opponents, choices)
        projected = target_start + delta
        if projected < target_rating:
            continue
        points_against = sum(loser_scores)
        if best is None or points_against > best[0] or (
            points_against == best[0] and projected < best[1]
        ):
            best = (points_against, projected, path)
    if best is None:
        return None
    points_against, projected, path = best
    return TargetPath(
        title="Barely enough undefeated path",
        scores=_format_scores(path),
        projected_rating=projected,
        delta=projected - target_start,
        note=f"Maximum points allowed across wins while still clearing target: {points_against}.",
        hits_target=True,
    )


def _target_paths(
    target_start: float,
    partner_rating: float,
    opponents: list[TournamentTeam],
    target_rating: float,
) -> list[TargetPath]:
    paths = _same_score_sweeps(target_start, partner_rating, opponents, target_rating)
    barely = _barely_enough_all_wins(target_start, partner_rating, opponents, target_rating)
    if barely is not None:
        paths.append(barely)
    for wins in range(len(opponents) - 1, max(-1, len(opponents) - 4), -1):
        best = _best_path_by_wins(target_start, partner_rating, opponents, wins)
        best.hits_target = best.projected_rating >= target_rating
        paths.append(best)
    return paths


def analyze(
    session: Session,
    *,
    raw_text: str,
    target_name: Optional[str] = None,
    target_rating: float = DEFAULT_TARGET_RATING,
    live_lookup: bool = True,
) -> TournamentAnalysis:
    players = parse_roster_text(raw_text)
    warnings = _resolve_players(session, players, live_lookup=live_lookup)
    if len(players) < 4:
        raise ValueError("Paste at least 4 players. Teams are paired in pasted order.")
    if len(players) % 2:
        warnings.append(f"Ignoring unpaired last player: {players[-1].name}")
        players = players[:-1]

    teams = pair_teams(players)
    target_lower = (target_name or "").strip().lower()
    target_player = None
    for p in players:
        if target_lower and target_lower in p.name.lower():
            target_player = p
            break
    if target_player is None:
        target_player = next((p for p in players if "jonathan" in p.name.lower() or p.name.lower().startswith("jon ")), None)
    if target_player is None:
        target_player = players[0]
        warnings.append("No target player matched; using the first pasted player.")

    target_team = next(t for t in teams if target_player in t.players)
    target_idx = 0 if target_team.players[0] is target_player else 1
    partner = target_team.players[1 - target_idx]
    if target_player.rating is None:
        raise ValueError(f"{target_player.name} needs a DUPR rating or pasted skill.")
    if partner.rating is None:
        raise ValueError(f"{partner.name} needs a DUPR rating or pasted skill.")

    opponent_teams = [t for t in teams if t is not target_team and t.avg_rating is not None]
    skipped = [t.label for t in teams if t is not target_team and t.avg_rating is None]
    if skipped:
        warnings.append("Skipped teams missing ratings: " + ", ".join(skipped))
    if not opponent_teams:
        raise ValueError("No opponent teams have enough rating data to forecast.")

    current_rating = float(target_player.rating)
    forecasts = _forecast_matches(target_team, opponent_teams)
    target_paths = _target_paths(current_rating, float(partner.rating), opponent_teams, target_rating)
    same_score_sweeps = [p for p in target_paths if p.title.startswith("All ")]

    return TournamentAnalysis(
        players=players,
        teams=teams,
        target_player=target_player,
        target_team=target_team,
        target_rating=target_rating,
        current_rating=current_rating,
        target_gap=target_rating - current_rating,
        forecasts=forecasts,
        same_score_sweeps=same_score_sweeps,
        target_paths=target_paths,
        warnings=warnings,
        source_text=raw_text,
    )
