"""
Tests for the "Log to JUPR" button path:

    POST /forecast/log  →  upserts JuprPlayers, records a JuprGame, returns
                            an HTML success fragment.

These cover:
- Find-or-create by dupr_id (idempotent).
- Happy path produces a leaderboard entry in the same test DB.
- Validation surface: duplicate players, ties, missing names.
- UI contract: the card partial renders a "Log to JUPR" button when
  all 4 slots have a dupr_id in the meta.
"""
from __future__ import annotations

import os
import tempfile

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(monkeypatch) -> TestClient:
    """
    Fresh in-memory SQLite per test so the JUPR ledger starts empty.
    We clobber DATABASE_URL before importing the app and reset the
    global engine singleton in web.db so init_db() hits the new URL.
    """
    # Use a temp file (not :memory:) so the same connection string
    # resolves to the same DB across request threads in FastAPI.
    tmpdir = tempfile.mkdtemp(prefix="duprly-test-")
    db_path = os.path.join(tmpdir, "jupr.db")
    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{db_path}")

    import importlib

    import web.db as db_mod
    db_mod._engine = None
    db_mod._SessionLocal = None
    db_mod.DATABASE_URL = db_mod._resolve_database_url()
    db_mod._IS_SQLITE = db_mod.DATABASE_URL.startswith("sqlite")

    import web.main as main_mod
    importlib.reload(main_mod)
    return TestClient(main_mod.app)


class TestForecastLogEndpoint:
    def test_logs_match_and_creates_players(self, client: TestClient):
        r = client.post(
            "/forecast/log",
            data={
                "duprid1": "4405492894", "duprid2": "7511597513",
                "duprid3": "7270240621", "duprid4": "5651921565",
                "name1": "Jon Chui", "name2": "Harrison Webb",
                "name3": "Cody F", "name4": "Erich Wagner",
                "r1": 3.86, "r2": 4.07, "r3": 3.85, "r4": 4.41,
                "rel1": 65, "rel2": 72, "rel3": 70, "rel4": 80,
                "games1": 11, "games2": 7,
            },
        )
        assert r.status_code == 200, r.text
        assert "Logged to JUPR" in r.text
        assert "Jon Chui" in r.text
        # Leaderboard should now include all 4 players.
        board = client.get("/api/jupr/leaderboard").json()
        names = {row["full_name"] for row in board}
        assert {"Jon Chui", "Harrison Webb", "Cody F", "Erich Wagner"} <= names

    def test_logging_same_players_twice_reuses_rows(self, client: TestClient):
        """Second log for the same 4 DUPR ids must NOT create dup JuprPlayer rows."""
        payload = {
            "duprid1": "1111", "duprid2": "2222",
            "duprid3": "3333", "duprid4": "4444",
            "name1": "A", "name2": "B", "name3": "C", "name4": "D",
            "r1": 3.5, "r2": 3.6, "r3": 3.7, "r4": 3.8,
            "games1": 11, "games2": 5,
        }
        assert client.post("/forecast/log", data=payload).status_code == 200
        assert client.post("/forecast/log", data=payload).status_code == 200
        # /api/jupr/leaderboard shows one row per unique player id.
        board = client.get("/api/jupr/leaderboard").json()
        dupr_ids = {row["full_name"] for row in board}
        assert len(dupr_ids) == 4, f"expected 4 unique players, got {board}"

    def test_rejects_tie_scores(self, client: TestClient):
        r = client.post(
            "/forecast/log",
            data={
                "duprid1": "1", "duprid2": "2", "duprid3": "3", "duprid4": "4",
                "name1": "A", "name2": "B", "name3": "C", "name4": "D",
                "r1": 3.5, "r2": 3.5, "r3": 3.5, "r4": 3.5,
                "games1": 11, "games2": 11,
            },
        )
        assert r.status_code == 400
        assert "tie" in r.text.lower() or "aren't rated" in r.text.lower()

    def test_rejects_duplicate_players(self, client: TestClient):
        r = client.post(
            "/forecast/log",
            data={
                "duprid1": "1", "duprid2": "1",  # same id in two slots!
                "duprid3": "3", "duprid4": "4",
                "name1": "A", "name2": "A", "name3": "C", "name4": "D",
                "r1": 3.5, "r2": 3.5, "r3": 3.5, "r4": 3.5,
                "games1": 11, "games2": 7,
            },
        )
        assert r.status_code == 400
        assert "distinct" in r.text.lower()


class TestMatchCardLogButton:
    def test_card_shows_log_button_when_all_duprids_present(self, client: TestClient):
        r = client.get(
            "/forecast/card",
            params={
                "r1": 3.86, "r2": 4.07, "r3": 3.85, "r4": 4.41,
                "games1": 11, "games2": 7,
                "duprid1": "1111", "duprid2": "2222",
                "duprid3": "3333", "duprid4": "4444",
                "name1": "A", "name2": "B", "name3": "C", "name4": "D",
            },
        )
        assert r.status_code == 200
        body = r.text
        assert "Log to JUPR" in body
        assert 'hx-post="/forecast/log"' in body

    def test_card_hides_log_button_when_duprids_missing(self, client: TestClient):
        r = client.get(
            "/forecast/card",
            params={
                "r1": 3.86, "r2": 4.07, "r3": 3.85, "r4": 4.41,
                "games1": 11, "games2": 7,
            },
        )
        assert r.status_code == 200
        body = r.text
        assert 'hx-post="/forecast/log"' not in body
        assert "Pick all 4 players from DUPR search" in body
