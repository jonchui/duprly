from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "ok"


class PlayerSummary(BaseModel):
    player_id: str
    display_name: Optional[str] = None
    gender: Optional[str] = None
    age: Optional[int] = None
    location: Optional[str] = None
    doubles_rating: Optional[float] = None
    singles_rating: Optional[float] = None
    reliability: Optional[int] = None
    updated_at: Optional[datetime] = None


class ClubMembership(BaseModel):
    club_id: str
    player_id: str
    role: Literal["admin", "member"]
    status: Literal["active", "inactive"]
    updated_at: Optional[datetime] = None


class MatchParticipant(BaseModel):
    player_id: str
    side: int
    position: Optional[int] = None
    pre_doubles_rating: Optional[float] = None
    pre_reliability: Optional[int] = None
    display_name: Optional[str] = None
    doubles_rating: Optional[float] = None
    reliability: Optional[int] = None


class MatchSummary(BaseModel):
    match_id: str
    played_at: datetime
    match_type: Optional[str] = None
    score_for: Optional[int] = None
    score_against: Optional[int] = None
    winner_side: Optional[int] = None
    participants: List[MatchParticipant] = Field(default_factory=list)


class MatchDetail(MatchSummary):
    metadata: Optional[Dict[str, Any]] = None
    tags: List[str] = Field(default_factory=list)


class SimilarityFactor(BaseModel):
    name: str
    weight: float
    target: Optional[float] = None
    actual: Optional[float] = None
    delta: Optional[float] = None
    explanation: Optional[str] = None


class SimilarMatch(BaseModel):
    match: MatchSummary
    score: float
    distance: Optional[float] = None
    factors: List[SimilarityFactor] = Field(default_factory=list)


class SimilarMatchesResponse(BaseModel):
    match_id: str
    k: int
    scope: Literal["club", "mine", "global"]
    results: List[SimilarMatch] = Field(default_factory=list)


class PlayerMatchesResponse(BaseModel):
    player_id: str
    matches: List[MatchSummary] = Field(default_factory=list)
    next_cursor: Optional[str] = None


class CrawlRunRequest(BaseModel):
    seed: Optional[List[str]] = None
    window_days: Optional[int] = None
    max_depth: Optional[int] = None
    max_new_players: Optional[int] = None
    rate_limit_per_min: Optional[int] = None


class CrawlStatus(BaseModel):
    status: Literal["idle", "running", "error"]
    queued: int = 0
    in_progress: int = 0
    errors: int = 0
    last_run_at: Optional[datetime] = None
