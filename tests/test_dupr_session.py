import base64, json

from dupr_client import DuprClient
from web.services import dupr_live


def _jwt(claims):
    enc = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")
    return f"{enc({'alg': 'RS512'})}.{enc(claims)}.sig"


def test_cookie_session_token_sent_as_cookie():
    c = DuprClient.__new__(DuprClient)
    c.auth_mode = "bearer"
    c.access_token = _jwt({"sid": "s1", "token_type": "ACCESS"})
    assert c.headers() == {"Cookie": f"__Host-dupr_at={c.access_token}"}


def test_legacy_token_sent_as_bearer():
    c = DuprClient.__new__(DuprClient)
    c.auth_mode = "bearer"
    c.access_token = _jwt({"token_type": "ACCESS"})
    assert c.headers() == {"Authorization": f"Bearer {c.access_token}"}


def test_verify_code_reads_session_cookie(monkeypatch):
    class R:
        status_code = 200
        headers = {}
        cookies = {"__Host-dupr_at": "AT", "__Host-dupr_rt": "RT"}
        def json(self):
            return {"result": {"user": {"id": 1}}}
    monkeypatch.setattr(DuprClient, "_rl_request", lambda self, *a, **k: R())
    assert dupr_live.verify_code("chal", "123456") == {"token": "AT", "refresh_token": "RT"}


def test_session_token_alone_enables_live(monkeypatch):
    monkeypatch.delenv("DUPR_USERNAME", raising=False)
    monkeypatch.delenv("DUPR_PASSWORD", raising=False)
    monkeypatch.setenv("DUPR_SESSION_TOKEN", "tok")
    assert dupr_live._has_live_credentials()
    assert not dupr_live._has_live_credentials("court")
