"""
Write-auth for public JUPR/FUPR endpoints.

Reads expect no auth. Writes require a shared bearer token via
`Authorization: Bearer <JUPR_WRITE_API_KEY>` OR `X-Api-Key: <key>`.

If `JUPR_WRITE_API_KEY` is unset in the environment, writes are treated
as *open* — intentional for local dev. In production set it on Vercel.
"""

from __future__ import annotations

import hmac
import os
from typing import Optional

from fastapi import Header, HTTPException, Request, status


def _configured_key() -> Optional[str]:
    v = os.environ.get("JUPR_WRITE_API_KEY", "").strip()
    return v or None


def require_write_key(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    x_api_key: Optional[str] = Header(default=None, alias="X-Api-Key"),
) -> None:
    """FastAPI dependency that gates a POST/PUT/DELETE endpoint."""
    expected = _configured_key()
    if expected is None:
        return  # local dev / unconfigured — allow all

    provided: Optional[str] = None
    if authorization and authorization.lower().startswith("bearer "):
        provided = authorization.split(" ", 1)[1].strip()
    elif x_api_key:
        provided = x_api_key.strip()

    if not provided or not hmac.compare_digest(provided, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or missing API key — use 'Authorization: Bearer <key>' or 'X-Api-Key: <key>'",
            headers={"WWW-Authenticate": 'Bearer realm="duprly"'},
        )
