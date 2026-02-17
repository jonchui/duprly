from typing import List, Literal, Optional

from fastapi import FastAPI, HTTPException, Query

from .api_models import (
    CrawlRunRequest,
    CrawlStatus,
    HealthResponse,
    MatchDetail,
    MatchSummary,
    PlayerMatchesResponse,
    PlayerSummary,
    SimilarMatchesResponse,
)

app = FastAPI(title="duprly api", version="0.1.0")


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()


@app.get("/me", response_model=PlayerSummary)
def get_me() -> PlayerSummary:
    raise HTTPException(status_code=501, detail="Not implemented")


@app.get("/players/{player_id}", response_model=PlayerSummary)
def get_player(player_id: str) -> PlayerSummary:
    raise HTTPException(status_code=501, detail="Not implemented")


@app.get("/players/{player_id}/matches", response_model=PlayerMatchesResponse)
def get_player_matches(
    player_id: str,
    limit: int = Query(50, ge=1, le=200),
    cursor: Optional[str] = None,
) -> PlayerMatchesResponse:
    raise HTTPException(status_code=501, detail="Not implemented")


@app.get("/clubs/{club_id}/players", response_model=List[PlayerSummary])
def get_club_players(
    club_id: str,
    query: Optional[str] = Query(None, min_length=1),
) -> List[PlayerSummary]:
    raise HTTPException(status_code=501, detail="Not implemented")


@app.get("/matches/recent", response_model=List[MatchSummary])
def get_recent_matches(
    scope: Literal["me", "club"] = "me",
    limit: int = Query(50, ge=1, le=200),
) -> List[MatchSummary]:
    raise HTTPException(status_code=501, detail="Not implemented")


@app.get("/matches/{match_id}", response_model=MatchDetail)
def get_match(match_id: str) -> MatchDetail:
    raise HTTPException(status_code=501, detail="Not implemented")


@app.get("/matches/{match_id}/similar", response_model=SimilarMatchesResponse)
def get_similar_matches(
    match_id: str,
    k: int = Query(20, ge=1, le=100),
    scope: Literal["club", "mine", "global"] = "club",
    min_rel: Optional[int] = Query(None, ge=0, le=100),
    opponent_rating_min: Optional[float] = None,
    opponent_rating_max: Optional[float] = None,
    match_type: Optional[str] = None,
) -> SimilarMatchesResponse:
    raise HTTPException(status_code=501, detail="Not implemented")


@app.post("/crawl/run", response_model=CrawlStatus)
def run_crawl(request: CrawlRunRequest) -> CrawlStatus:
    raise HTTPException(status_code=501, detail="Not implemented")


@app.get("/crawl/status", response_model=CrawlStatus)
def get_crawl_status() -> CrawlStatus:
    raise HTTPException(status_code=501, detail="Not implemented")


@app.post("/crawl/player/{player_id}/refresh", response_model=CrawlStatus)
def refresh_player(player_id: str) -> CrawlStatus:
    raise HTTPException(status_code=501, detail="Not implemented")
