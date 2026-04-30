"""
Tests for the process-wide DUPR rate limiter.

These cover the three failure modes that caused the 2026-04-30
runaway-loop incident on pickleme.cloud:

1. Concurrent callers must serialize through the limiter at
   <= 1 req / second (no more "18 player IDs in one second" log spam).
2. A 429 response must trigger a real backoff, not an immediate retry.
3. Two consecutive login failures must lock the client out, so a
   flagged DUPR account can't keep getting hammered.

We do not actually wait real wall-clock seconds — `_now` and `_sleep`
on the limiter are injected with a fake clock so the tests run in <100ms.
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from dupr_rate_limit import (
    DuprAccountLockedOut,
    DuprRateLimiter,
    DuprRateLimitWaitTooLong,
    get_limiter,
    set_limiter,
)


class FakeClock:
    """Monotonic clock + sleep that advance virtual time deterministically."""

    def __init__(self, start: float = 1000.0):
        self._t = start
        self._lock = threading.Lock()

    def now(self) -> float:
        with self._lock:
            return self._t

    def sleep(self, dt: float) -> None:
        with self._lock:
            self._t += max(0.0, dt)


@pytest.fixture
def limiter():
    """Fresh limiter with a fake clock and tight defaults for tests."""
    fake = FakeClock()
    lim = DuprRateLimiter(
        min_interval_s=1.0,
        backoff_on_429_s=10.0,
        login_failure_lockout_s=60.0,
        max_wait_s=5.0,
    )
    lim._now = fake.now
    lim._sleep = fake.sleep
    lim._fake = fake  # convenience handle for tests
    return lim


# ---- single-call behavior -------------------------------------------------


def test_first_call_does_not_wait(limiter):
    t0 = limiter._fake.now()
    limiter.acquire()
    assert limiter._fake.now() == t0  # no sleep on the first call


def test_second_call_waits_min_interval(limiter):
    limiter.acquire()
    t0 = limiter._fake.now()
    limiter.acquire()
    assert limiter._fake.now() == t0 + 1.0  # exactly min_interval_s later


def test_repeated_calls_are_paced(limiter):
    starts = []
    for _ in range(5):
        starts.append(limiter._fake.now())
        limiter.acquire()
    elapsed_between = [
        starts[i + 1] - starts[i] for i in range(len(starts) - 1)
    ]
    # First gap is 0 (first call), the rest >=1s under the fake clock.
    assert elapsed_between[0] == 0.0
    assert all(g >= 1.0 for g in elapsed_between[1:])


# ---- concurrency ---------------------------------------------------------


def test_concurrent_acquire_serializes_at_one_per_second(limiter):
    """The pickleme.cloud incident: 18 concurrent callers had ZERO pacing."""
    n_calls = 6
    barrier = threading.Barrier(n_calls)
    finish_times = []
    finish_lock = threading.Lock()

    def worker():
        barrier.wait()  # release everyone simultaneously
        limiter.acquire()
        with finish_lock:
            finish_times.append(limiter._fake.now())

    with ThreadPoolExecutor(max_workers=n_calls) as ex:
        futures = [ex.submit(worker) for _ in range(n_calls)]
        for f in futures:
            f.result(timeout=5)

    finish_times.sort()
    # First call goes through immediately, then 1s pacing for the rest.
    # Total elapsed virtual time should be ≥ (n_calls - 1) * 1s.
    span = finish_times[-1] - finish_times[0]
    assert span >= (n_calls - 1) * 1.0


# ---- 429 backoff ---------------------------------------------------------


def _patient_limiter():
    """A limiter willing to wait long enough to actually observe a backoff."""
    fake = FakeClock()
    lim = DuprRateLimiter(
        min_interval_s=1.0,
        backoff_on_429_s=10.0,
        login_failure_lockout_s=60.0,
        max_wait_s=120.0,  # bigger than any single backoff under test
    )
    lim._now = fake.now
    lim._sleep = fake.sleep
    lim._fake = fake
    return lim


def test_429_extends_next_wait_to_backoff_seconds():
    lim = _patient_limiter()
    lim.acquire()
    lim.release_after_response(429, is_login=False)
    t0 = lim._fake.now()
    lim.acquire()
    # Should have slept at least backoff_on_429_s (=10) before the next call.
    assert lim._fake.now() - t0 >= 10.0


def test_429_with_retry_after_header_honors_header():
    lim = _patient_limiter()
    lim.acquire()
    lim.release_after_response(
        429, is_login=False, response_headers={"Retry-After": "45"},
    )
    # 45s > backoff_on_429_s (10), so the bigger value wins.
    snap = lim.snapshot()
    assert snap["next_call_in_s"] >= 45.0


def test_three_consecutive_429s_trigger_lockout():
    lim = _patient_limiter()
    for _ in range(3):
        lim.acquire()
        lim.release_after_response(429, is_login=False)
    # Lockout is 60s — acquire raises the lockout flavor.
    with pytest.raises(DuprAccountLockedOut):
        lim.acquire()


def test_successful_response_resets_429_counter():
    lim = _patient_limiter()
    lim.acquire(); lim.release_after_response(429, is_login=False)
    lim.acquire(); lim.release_after_response(429, is_login=False)
    lim.acquire(); lim.release_after_response(200, is_login=False)
    snap = lim.snapshot()
    assert snap["consecutive_429s"] == 0


# ---- login lockout -------------------------------------------------------


def test_two_consecutive_login_failures_lock_out_client():
    lim = _patient_limiter()
    lim.acquire(is_login=True); lim.release_after_response(400, is_login=True)
    lim.acquire(is_login=True); lim.release_after_response(400, is_login=True)
    # 2nd failure → lockout. Next acquire (login or not) raises.
    with pytest.raises(DuprAccountLockedOut):
        lim.acquire(is_login=True)


def test_successful_login_clears_failure_counter():
    lim = _patient_limiter()
    lim.acquire(is_login=True); lim.release_after_response(400, is_login=True)
    lim.acquire(is_login=True); lim.release_after_response(200, is_login=True)
    snap = lim.snapshot()
    assert snap["consecutive_login_failures"] == 0
    # And another single failure must NOT lock us out (we'd reset to 0
    # and only have one fresh failure).
    lim.acquire(is_login=True); lim.release_after_response(400, is_login=True)
    snap = lim.snapshot()
    assert snap["locked_out_for_s"] == 0.0


# ---- max_wait guardrail --------------------------------------------------


def test_acquire_refuses_when_wait_exceeds_max_wait_s(limiter):
    # Single 429 → backoff = 10s. limiter.max_wait_s = 5s → next acquire
    # should refuse rather than block for 10s.
    limiter.acquire()
    limiter.release_after_response(429, is_login=False)
    with pytest.raises(DuprRateLimitWaitTooLong):
        limiter.acquire()


# ---- gate context manager ------------------------------------------------


def test_gate_context_manager_releases_on_success(limiter):
    class FakeResp:
        status_code = 200
        headers = {}

    with limiter.gate() as gate:
        gate.response = FakeResp()
    snap = limiter.snapshot()
    assert snap["consecutive_429s"] == 0


def test_gate_context_manager_releases_on_429(limiter):
    class FakeResp:
        status_code = 429
        headers = {}

    with limiter.gate() as gate:
        gate.response = FakeResp()
    snap = limiter.snapshot()
    assert snap["consecutive_429s"] == 1


# ---- singleton -----------------------------------------------------------


def test_get_limiter_returns_singleton():
    a = get_limiter()
    b = get_limiter()
    assert a is b
    # Cleanup so we don't pollute other tests' singleton.
    set_limiter(DuprRateLimiter())
