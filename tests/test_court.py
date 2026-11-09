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


# ---- player's own DUPR login (app keeps creds in the Keychain, sends the token) ----

class FakeResp:
    def __init__(self, status, body):
        self.status_code, self._body, self.headers = status, body, {}

    def json(self):
        return self._body


class FakeDupr:
    """Stands in for dupr_client.DuprClient: no network, no token file.
    me@example.com/right logs straight in; code@example.com/right gets an emailed code (123456)."""
    tokens_seen: list = []
    posts: list = []

    def __init__(self, *a, **k):
        self.access_token = "SHARED-FILE-TOKEN"  # what a real client would load from ~/.duprly_config
        self.saved = False

    def save_token(self):
        self.saved = True

    def u(self, path):
        return path

    def _rl_request(self, method, url, is_login=False, json=None, **kw):
        FakeDupr.posts.append((url, sorted(json)))
        if url == "/auth/v1.0/login/":
            if json == {"email": "me@example.com", "password": "right"}:
                return FakeResp(200, {"status": "SUCCESS", "result": {"accessToken": "tok-me"}})
            if json == {"email": "code@example.com", "password": "right"}:
                return FakeResp(200, {"status": "SUCCESS", "result": {"twoFactorRequired": True, "challengeToken": "chal-123",
                                                                     "methods": [{"type": "urn:dupr:second-factor:email"}]}})
            return FakeResp(401, {"status": "FAILURE", "message": "bad"})
        if url == "/auth/v1.0/2fa/verify":
            if json == {"challengeToken": "chal-123", "code": "123456"}:
                return FakeResp(200, {"status": "SUCCESS", "result": {"accessToken": "tok-me", "refreshToken": "r"}})
            return FakeResp(400, {"status": "FAILURE", "message": "Verification code expired. Please request a new code."})
        if url == "/auth/v1.0/2fa/resend":
            return FakeResp(200 if json == {"challengeToken": "chal-123"} else 400, {})
        return FakeResp(404, {})

    def search_players(self, q, limit=25):
        FakeDupr.tokens_seen.append(self.access_token)
        if self.access_token != "tok-me":
            return 401, {}
        return 200, {"hits": [{"id": 4242, "fullName": "Cindy Sample", "ratings": {"doubles": "3.9"}}]}

    def get_player(self, q):
        return 404, None


@pytest.fixture
def fake_dupr(monkeypatch):
    import dupr_client
    monkeypatch.setattr(dupr_client, "DuprClient", FakeDupr)
    monkeypatch.delenv("COURT_DUPR_USERNAME", raising=False)
    monkeypatch.delenv("COURT_DUPR_PASSWORD", raising=False)
    FakeDupr.tokens_seen, FakeDupr.posts = [], []
    return FakeDupr


def test_dupr_login_returns_token_only_for_good_creds(client, fake_dupr):
    ok = client.post("/api/court/dupr-login", json={"username": "me@example.com", "password": "right"})
    assert ok.status_code == 200 and ok.json() == {"ok": True, "token": "tok-me"}
    bad = client.post("/api/court/dupr-login", json={"username": "me@example.com", "password": "wrong"})
    assert bad.status_code == 401


def test_search_needs_a_login(client, fake_dupr):
    r = client.get("/api/court/dupr-search", params={"q": "cindy s"})
    assert r.status_code == 401 and r.json()["detail"] == "dupr_login_required"


def test_search_uses_my_token_never_the_shared_file(client, fake_dupr):
    r = client.get("/api/court/dupr-search", params={"q": "cindy sam"}, headers={"X-Dupr-Token": "tok-me"})
    assert r.status_code == 200, r.text
    assert "SHARED-FILE-TOKEN" not in fake_dupr.tokens_seen and "tok-me" in fake_dupr.tokens_seen
    expired = client.get("/api/court/dupr-search", params={"q": "zzz qqq"}, headers={"X-Dupr-Token": "old"})
    assert expired.status_code == 401


def test_isolated_client_does_not_load_or_save_shared_token(fake_dupr):
    c = dupr_live.isolated_client()
    assert c.access_token is None
    c.access_token = "x"
    c.save_token()
    assert not getattr(c, "saved", False)


def test_dupr_login_with_emailed_code(client, fake_dupr):
    r = client.post("/api/court/dupr-login", json={"username": "code@example.com", "password": "right"})
    assert r.status_code == 200, r.text
    assert r.json() == {"ok": False, "needs_code": True, "challenge": "chal-123", "methods": ["urn:dupr:second-factor:email"]}
    bad = client.post("/api/court/dupr-code", json={"challenge": "chal-123", "code": "000000"})
    assert bad.status_code == 401 and bad.json()["detail"] == "Verification code expired. Please request a new code."
    ok = client.post("/api/court/dupr-code", json={"challenge": "chal-123", "code": " 123456 "})
    assert ok.status_code == 200 and ok.json() == {"ok": True, "token": "tok-me"}
    assert client.post("/api/court/dupr-resend", json={"challenge": "chal-123"}).json() == {"ok": True}
    # the password only ever goes to DUPR's login call
    assert [u for u, keys in fake_dupr.posts if "password" in keys] == ["/auth/v1.0/login/"] * 1


def test_login_user_handles_challenge_without_crashing(monkeypatch):
    import dupr_client
    c = dupr_client.DuprClient()
    c.save_token = lambda: None
    monkeypatch.setattr(c, "_rl_request", lambda *a, **k: FakeResp(200, {"result": {"twoFactorRequired": True, "challengeToken": "x"}}))
    assert c.login_user("a@b.c", "p") == 428 and not c.access_token


def test_failed_or_code_login_pauses_retries(monkeypatch):
    """A login that needs an emailed code must not be retried on every request (each try emails a code)."""
    calls = []

    class CodeOnly:
        access_token = None
        def save_token(self): pass
        def auth_user(self, u, p):
            calls.append(u)
            return 428

    monkeypatch.setattr(dupr_live, "isolated_client", lambda token=None: CodeOnly())
    monkeypatch.setenv("COURT_DUPR_USERNAME", "court@example.com")
    monkeypatch.setenv("COURT_DUPR_PASSWORD", "x")
    dupr_live._CLIENTS.pop("court", None)
    dupr_live._LOGIN_PAUSED_UNTIL.pop("court", None)
    for _ in range(3):
        with pytest.raises(RuntimeError):
            dupr_live._get_live_client("court")
    assert calls == ["court@example.com"]  # one login, then paused
    dupr_live._LOGIN_PAUSED_UNTIL.pop("court", None)
