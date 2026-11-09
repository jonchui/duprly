"""Site version: newest web/changelog.json entry + the deployed git commit."""

from __future__ import annotations

import json
import os
import subprocess
from functools import lru_cache
from pathlib import Path

_CHANGELOG = Path(__file__).with_name("changelog.json")


@lru_cache(maxsize=1)
def changelog() -> list:
    return json.loads(_CHANGELOG.read_text())


@lru_cache(maxsize=1)
def commit() -> str:
    sha = os.environ.get("VERCEL_GIT_COMMIT_SHA", "")  # set by Vercel on every deploy
    if not sha:
        try:
            sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=_CHANGELOG.parent,
                                          stderr=subprocess.DEVNULL, text=True).strip()
        except Exception:
            sha = ""
    return sha[:7] or "local"


def info() -> dict:
    latest = changelog()[0]
    return {"version": latest["version"], "commit": commit(), "date": latest["date"],
            "env": os.environ.get("VERCEL_ENV", "local"), "changes": latest["changes"]}
