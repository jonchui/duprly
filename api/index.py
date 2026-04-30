"""
Vercel Python serverless entrypoint for duprly.com web app.

Vercel imports a module-level `app` from this file. Keep this shim small
and put real logic in web/main.py.
"""

from __future__ import annotations

import os
import sys

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from web.main import app  # noqa: E402,F401
