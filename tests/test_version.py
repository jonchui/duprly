import re

from fastapi.testclient import TestClient

from web.main import app
from web import version


def test_changelog_newest_first_and_semver():
    entries = version.changelog()
    vs = [tuple(map(int, e["version"].split("."))) for e in entries]
    assert vs == sorted(vs, reverse=True)
    assert all(e["changes"] for e in entries)


def test_api_version_and_footer():
    c = TestClient(app)
    v = c.get("/api/version").json()
    assert v["version"] == version.changelog()[0]["version"] and v["commit"]
    page = c.get("/changelog").text
    assert re.search(rf"v{re.escape(v['version'])} · {v['commit']}", page)
