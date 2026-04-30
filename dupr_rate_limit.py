"""
Process-wide rate limiter for DUPR API calls.

Why this exists
---------------
DUPR's API has aggressive rate-limiting. On 2026-04-30 our `pickleme.cloud`
deployment was caught in a runaway loop:

  - A bot crawler discovered `/dupr/player/<dupr_id>` URLs and started
    walking 170+ player pages in quick succession.
  - Each page call fanned out one (or more, paginated) DUPR API call.
  - When DUPR returned 429 ("too many requests") on the JWT login path,
    `dupr_client._relogin()` re-fired immediately, racing every other
    request handler that was stuck on the same expired token.
  - The infinite retry storm got our DUPR account flagged, melted the
    VPS (load avg 3.5, CPU 58% sustained) and made the box unreachable
    over HTTPS until uvicorn was killed.

What this module does
---------------------
A single, shared `DuprRateLimiter` instance acts as a token bucket
across all threads in the FastAPI process. Every outgoing call into
`api.dupr.gg` is required to `acquire()` exactly one token before
hitting the network — and `release_after_response()` is called with
the response so we can extend the next-acquire wait when DUPR signals
backoff (429 / 503 / Retry-After).

Default policy
--------------
- `min_interval_s = 1.0` — at most one DUPR HTTP call per second per
  process. (Matches the user-facing safety request: "limit it to only 1
  per second".) This is the hard floor; backoff is added on top.
- `backoff_on_429_s = 30.0` — after a 429, hold the gate for at least
  this long before any new call goes out. If `Retry-After` is in the
  response header we honor that instead.
- `login_failure_lockout_s = 300.0` — when DUPR returns 400 or 429 on
  `/auth/v1.0/login/` we lock the entire client out for 5 minutes.
  400 on login is DUPR's "account flagged" signal and there's nothing
  the caller can do but wait.
- `max_wait_s = 60.0` — bound how long any single `acquire()` will
  block. Past this we raise `DuprRateLimitWaitTooLong` so request
  handlers can return a 503 instead of holding a connection forever.

Tests live in `tests/test_dupr_rate_limit.py`.
"""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from typing import Optional

from loguru import logger


class DuprRateLimitWaitTooLong(RuntimeError):
    """Raised when `acquire()` would have to wait longer than `max_wait_s`."""


class DuprAccountLockedOut(RuntimeError):
    """Raised when the client is in the post-401/post-429 login lockout window."""


@dataclass
class _LimiterState:
    next_call_at: float = 0.0  # epoch seconds; cannot make a new call before this
    locked_out_until: float = 0.0  # epoch seconds; we refuse all calls until this
    consecutive_429s: int = 0
    consecutive_login_failures: int = 0


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


class DuprRateLimiter:
    """Process-wide gate for DUPR HTTP calls.

    Thread-safe. All `requests.*` calls into `api.dupr.gg` should funnel
    through `with limiter.gate(): r = requests.post(...)` (or call
    `acquire()` / `release_after_response(r)` manually).

    The limiter does NOT replace `requests`; it just throttles what goes
    in. Failures (DNS, TLS, connection reset) are not punished — those
    are not DUPR-side rate-limit signals.
    """

    def __init__(
        self,
        *,
        min_interval_s: Optional[float] = None,
        backoff_on_429_s: Optional[float] = None,
        login_failure_lockout_s: Optional[float] = None,
        max_wait_s: Optional[float] = None,
    ):
        # Env overrides give us a way to dial throttling tighter on a hot
        # VPS without needing a code push. Defaults follow the policy in
        # the module docstring.
        self.min_interval_s = (
            min_interval_s
            if min_interval_s is not None
            else _env_float("DUPR_RL_MIN_INTERVAL_S", 1.0)
        )
        self.backoff_on_429_s = (
            backoff_on_429_s
            if backoff_on_429_s is not None
            else _env_float("DUPR_RL_BACKOFF_429_S", 30.0)
        )
        self.login_failure_lockout_s = (
            login_failure_lockout_s
            if login_failure_lockout_s is not None
            else _env_float("DUPR_RL_LOGIN_LOCKOUT_S", 300.0)
        )
        self.max_wait_s = (
            max_wait_s
            if max_wait_s is not None
            else _env_float("DUPR_RL_MAX_WAIT_S", 60.0)
        )
        self._lock = threading.Lock()
        self._state = _LimiterState()
        self._sleep = time.sleep  # injectable for tests
        self._now = time.monotonic  # injectable for tests

    # ---- public API -----------------------------------------------------

    def reset(self) -> None:
        """Reset all timers and counters. Useful for tests."""
        with self._lock:
            self._state = _LimiterState()

    def snapshot(self) -> dict:
        """Return a copy of the limiter state for diagnostics / /healthz."""
        with self._lock:
            now = self._now()
            return {
                "next_call_in_s": max(0.0, self._state.next_call_at - now),
                "locked_out_for_s": max(0.0, self._state.locked_out_until - now),
                "consecutive_429s": self._state.consecutive_429s,
                "consecutive_login_failures": self._state.consecutive_login_failures,
                "min_interval_s": self.min_interval_s,
                "backoff_on_429_s": self.backoff_on_429_s,
                "login_failure_lockout_s": self.login_failure_lockout_s,
                "max_wait_s": self.max_wait_s,
            }

    def acquire(self, *, is_login: bool = False) -> None:
        """Block until the limiter allows the next DUPR call.

        Raises:
            DuprAccountLockedOut: when we're inside the post-failure
                lockout window (typically after a 429 / flagged login).
                Login attempts respect the lockout too — that's the whole
                point — so the only way out is to wait.
            DuprRateLimitWaitTooLong: when the wait would exceed
                `max_wait_s`. The caller should treat this like a 503
                and return early.
        """
        # Compute how long we need to sleep under the lock, then sleep
        # OUTSIDE the lock so concurrent callers can also queue. The lock
        # is just for reading + bumping the next_call_at cursor.
        with self._lock:
            now = self._now()
            if self._state.locked_out_until > now:
                wait = self._state.locked_out_until - now
                # Lockout windows are always "fail fast" for the caller —
                # if we're flagged, we're flagged; pretending to wait
                # 5 minutes inside one HTTP request is worse than 503ing.
                raise DuprAccountLockedOut(
                    f"DUPR client locked out for {wait:.1f}s "
                    f"(consecutive_429s={self._state.consecutive_429s}, "
                    f"consecutive_login_failures={self._state.consecutive_login_failures})"
                )
            wait = max(0.0, self._state.next_call_at - now)
            if wait > self.max_wait_s:
                raise DuprRateLimitWaitTooLong(
                    f"DUPR rate-limit wait would be {wait:.1f}s "
                    f"(max {self.max_wait_s:.1f}s); refuse and 503 upstream"
                )
            # Reserve our slot: bump next_call_at by at least
            # min_interval_s from the LATER of (now+wait, current cursor).
            # This makes concurrent acquires queue cleanly.
            slot_at = max(now + wait, self._state.next_call_at)
            self._state.next_call_at = slot_at + self.min_interval_s
        if wait > 0:
            self._sleep(wait)

    def release_after_response(self, status_code: int, *, is_login: bool, response_headers: Optional[dict] = None) -> None:
        """Update limiter state based on the just-completed call.

        Call this for EVERY response — success or failure — so we keep
        the consecutive-failure counters accurate. Successful calls reset
        the failure counters and clear lockouts.
        """
        with self._lock:
            now = self._now()
            if status_code == 429:
                # DUPR is asking us to back off. Honor Retry-After if
                # present (it's commonly the second-largest contributor
                # to runaway loops — clients ignore it and just retry).
                retry_after = self._parse_retry_after(response_headers)
                wait = max(retry_after if retry_after is not None else 0.0, self.backoff_on_429_s)
                self._state.next_call_at = max(self._state.next_call_at, now + wait)
                self._state.consecutive_429s += 1
                # Three 429s in a row → escalate to a real lockout so we
                # stop stomping on DUPR until a human looks. Without this
                # we'd just back off 30s, retry, 429, back off 30s, …
                if self._state.consecutive_429s >= 3:
                    self._state.locked_out_until = max(
                        self._state.locked_out_until,
                        now + self.login_failure_lockout_s,
                    )
                    logger.warning(
                        f"DUPR rate limiter: hit {self._state.consecutive_429s} "
                        f"consecutive 429s — locking out for "
                        f"{self.login_failure_lockout_s:.0f}s to give the "
                        f"account time to recover"
                    )
                else:
                    logger.warning(
                        f"DUPR rate limiter: 429 received, backing off "
                        f"{wait:.1f}s (consecutive={self._state.consecutive_429s})"
                    )
                return

            if is_login and status_code in (400, 401, 403):
                # 400/401/403 on the login path = bad creds OR account
                # flagged (DUPR returns 400 in the "your account is
                # restricted" case). Either way, hammering re-login is
                # exactly what got us here in the first place.
                self._state.consecutive_login_failures += 1
                if self._state.consecutive_login_failures >= 2:
                    self._state.locked_out_until = max(
                        self._state.locked_out_until,
                        now + self.login_failure_lockout_s,
                    )
                    logger.error(
                        f"DUPR rate limiter: login failed {self._state.consecutive_login_failures} "
                        f"times in a row (last status {status_code}) — "
                        f"locking out for {self.login_failure_lockout_s:.0f}s"
                    )
                return

            if 200 <= status_code < 300:
                # Healthy response — clear failure counters so a single
                # bad minute doesn't permanently lock us out.
                self._state.consecutive_429s = 0
                if is_login:
                    self._state.consecutive_login_failures = 0
                # We don't clear `locked_out_until` here: if we're inside
                # a lockout, `acquire()` won't even let this call out,
                # so reaching this branch means the lockout already
                # expired. Nothing to do.
                return
            # 5xx / network errors fall through with no state change —
            # those aren't DUPR rate-limit signals so we don't punish
            # the limiter for them.

    # ---- context-manager helper ----------------------------------------

    class _Gate:
        def __init__(self, limiter: "DuprRateLimiter", is_login: bool):
            self.limiter = limiter
            self.is_login = is_login
            self.response = None  # caller assigns this for auto-release

        def __enter__(self):
            self.limiter.acquire(is_login=self.is_login)
            return self

        def __exit__(self, exc_type, exc, tb):
            # Caller sets `gate.response = r` before exiting. Without it
            # we have no way to update backoff state — but we still don't
            # want to swallow the exception.
            r = self.response
            if r is not None:
                try:
                    status = int(getattr(r, "status_code", 0) or 0)
                    headers = dict(getattr(r, "headers", {}) or {})
                except Exception:
                    status, headers = 0, None
                self.limiter.release_after_response(
                    status, is_login=self.is_login, response_headers=headers,
                )
            return False  # don't suppress exceptions

    def gate(self, *, is_login: bool = False) -> "_Gate":
        """`with limiter.gate(): r = requests.post(...); gate.response = r` shape."""
        return self._Gate(self, is_login)

    # ---- internals ------------------------------------------------------

    @staticmethod
    def _parse_retry_after(headers: Optional[dict]) -> Optional[float]:
        if not headers:
            return None
        for key in ("Retry-After", "retry-after"):
            v = headers.get(key)
            if v is not None:
                try:
                    return max(0.0, float(v))
                except (TypeError, ValueError):
                    return None
        return None


# Process-wide singleton. `dupr_client` should import THIS instance so all
# DuprClient objects in the same process share one bucket.
_GLOBAL_LIMITER: Optional[DuprRateLimiter] = None


def get_limiter() -> DuprRateLimiter:
    global _GLOBAL_LIMITER
    if _GLOBAL_LIMITER is None:
        _GLOBAL_LIMITER = DuprRateLimiter()
    return _GLOBAL_LIMITER


def set_limiter(limiter: DuprRateLimiter) -> None:
    """Replace the singleton. Tests use this; production should not."""
    global _GLOBAL_LIMITER
    _GLOBAL_LIMITER = limiter
