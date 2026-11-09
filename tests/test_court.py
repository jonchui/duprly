"""Court rosters API for the pckl.bot app: people, DUPR link, votes, court-only DUPR login."""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from web.db import init_db, session_scope
from web.main import app
from web.models import DuprCachedPlayer
from web.services import dupr_live

V = "courtreserve:13679"
ME, YOU = "jon@example.com", "pat@example.com"


@pytest.fixture(scope="module")
def client() -> TestClient:
    init_db()
    with session_scope() as s:
        if s.get(DuprCachedPlayer, "999") is None:
            s.add(DuprCachedPlayer(dupr_id="999", full_name="Cindy Sample", doubles=3.81, image_url="https://img/c.png"))
    return TestClient(app)


def people(client, names, voter=ME):
    r = client.post("/api/court/people", json={"venue": V, "names": names, "voter": voter})
    assert r.status_code == 200, r.text
    return {p["name"]: p for p in r.json()}


def test_unknown_names_come_back_empty(client):
    p = people(client, ["Zed Q.", "  Zed   Q. "])
    assert list(p) == ["Zed Q."]
    assert p["Zed Q."] == {"name": "Zed Q.", "dupr": None, "fupr": {"count": 0, "median": None}, "mine": None}


def test_link_shows_dupr_and_photo(client):
    r = client.post("/api/court/link", json={"venue": V, "name": "Cindy S.", "dupr_id": "999", "voter": ME})
    assert r.status_code == 200, r.text
    d = people(client, ["Cindy S."])["Cindy S."]["dupr"]
    assert d == {"dupr_id": "999", "full_name": "Cindy Sample", "doubles": 3.81, "image_url": "https://img/c.png"}


def test_link_rejects_unsearched_id(client):
    r = client.post("/api/court/link", json={"venue": V, "name": "Fred S.", "dupr_id": "nope", "voter": ME})
    assert r.status_code == 400


def test_votes_fupr_is_shared_play_again_is_mine(client):
    for voter, skill, again in [(ME, 3.5, 1), (YOU, 4.0, -1)]:
        r = client.post("/api/court/votes", json={"venue": V, "class_id": "cr_X1", "voter": voter,
                                                  "votes": [{"name": "Fred S.", "skill": skill, "again": again}]})
        assert r.status_code == 200 and r.json() == {"saved": 1}, r.text
    mine = people(client, ["Fred S."])["Fred S."]
    assert mine["fupr"] == {"count": 2, "median": 3.75}
    assert mine["mine"] == {"skill": 3.5, "again": 1}
    assert people(client, ["Fred S."], voter=YOU)["Fred S."]["mine"] == {"skill": 4.0, "again": -1}


def test_revote_same_class_replaces(client):
    body = {"venue": V, "class_id": "cr_X2", "voter": ME, "votes": [{"name": "Jen K.", "skill": 3.0, "again": 1}]}
    client.post("/api/court/votes", json=body)
    body["votes"][0].update(skill=3.25, again=None)
    client.post("/api/court/votes", json=body)
    p = people(client, ["Jen K."])["Jen K."]
    assert p["fupr"]["count"] == 1 and p["mine"] == {"skill": 3.25, "again": None}


@pytest.mark.parametrize("bad", [{"skill": 9}, {"again": 2}])
def test_bad_votes(client, bad):
    r = client.post("/api/court/votes", json={"venue": V, "class_id": "cr_X3", "voter": ME, "votes": [{"name": "A B.", **bad}]})
    assert r.status_code == 400


def test_voter_must_be_email(client):
    r = client.post("/api/court/people", json={"venue": V, "names": ["A B."], "voter": "nobody"})
    assert r.status_code == 400


def test_court_account_never_uses_lucas(monkeypatch):
    monkeypatch.setenv("COURT_DUPR_USERNAME", "Lucas@JonChui.com")
    monkeypatch.setenv("COURT_DUPR_PASSWORD", "x")
    monkeypatch.setenv("DUPR_USERNAME", "lucas@jonchui.com")
    monkeypatch.setenv("DUPR_PASSWORD", "x")
    assert not dupr_live._has_live_credentials("court")
    with pytest.raises(RuntimeError):
        dupr_live._get_live_client("court")
    monkeypatch.setenv("COURT_DUPR_USERNAME", "court@example.com")
    assert dupr_live._has_live_credentials("court")
