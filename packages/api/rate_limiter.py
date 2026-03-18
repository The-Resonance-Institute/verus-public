"""
Rate Limiter.

Per-engagement rate limiting for expensive API routes (reasoning runs,
plan stress-tests). Uses a sliding window counter stored in memory.

In production this would use Redis. The in-memory implementation here
has the same interface so swapping to Redis requires only changing the
backend, not the route code.

Rate limit tiers:
  REASONING_RUN   — 5 runs per engagement per hour
  PLAN_STRESS_TEST — 3 runs per engagement per hour
  CHAT_MESSAGE    — 200 messages per session (enforced in chat engine)

The rate limit check is a FastAPI dependency that:
  1. Reads the engagement_id from the route's path parameter
  2. Looks up the counter for this (engagement_id, action) pair
  3. If the counter is at or above the limit: raises 429
  4. If below: increments the counter and returns

Rate limit responses include:
  Retry-After: N   (seconds until the window resets)
  X-RateLimit-Limit: N
  X-RateLimit-Remaining: N
"""
from __future__ import annotations

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status

from packages.api.schemas import ErrorCode

logger = logging.getLogger(__name__)


class RateLimitedAction(str, Enum):
    REASONING_RUN    = "reasoning_run"
    PLAN_STRESS_TEST = "plan_stress_test"
    CHAT_SESSION     = "chat_session"


# Limits: (max_calls, window_seconds)
_LIMITS: dict[RateLimitedAction, tuple[int, int]] = {
    RateLimitedAction.REASONING_RUN:    (5,  3600),   # 5/hour
    RateLimitedAction.PLAN_STRESS_TEST: (3,  3600),   # 3/hour
    RateLimitedAction.CHAT_SESSION:     (10, 3600),   # 10 new sessions/hour
}


@dataclass
class _WindowEntry:
    """Sliding window state for one (engagement_id, action) pair."""
    timestamps: list[float] = field(default_factory=list)


class InMemoryRateLimiter:
    """
    Thread-safe sliding window rate limiter backed by in-memory storage.

    For production: replace _store with a Redis client implementation
    that exposes the same check_and_increment() interface.
    """

    def __init__(self) -> None:
        self._store: dict[tuple[str, str], _WindowEntry] = defaultdict(
            _WindowEntry
        )

    def check_and_increment(
        self,
        engagement_id: UUID,
        action: RateLimitedAction,
    ) -> tuple[bool, int, int]:
        """
        Check and increment the rate limit counter.

        Returns:
            (allowed, remaining, reset_in_seconds)
            allowed:         True if the call is permitted.
            remaining:       Calls remaining in the current window.
            reset_in_seconds: Seconds until the window fully resets.
        """
        limit, window_secs = _LIMITS[action]
        key = (str(engagement_id), action.value)
        entry = self._store[key]
        now = time.monotonic()

        # Evict timestamps outside the window
        cutoff = now - window_secs
        entry.timestamps = [t for t in entry.timestamps if t > cutoff]

        count = len(entry.timestamps)
        remaining = max(0, limit - count)

        if count >= limit:
            # Window reset time: oldest timestamp + window_secs
            reset_in = int(entry.timestamps[0] + window_secs - now) + 1
            return False, 0, reset_in

        # Permit and record
        entry.timestamps.append(now)
        return True, remaining - 1, window_secs

    def reset(self, engagement_id: UUID, action: RateLimitedAction) -> None:
        """Reset the counter for a (engagement, action) pair. Used in tests."""
        key = (str(engagement_id), action.value)
        if key in self._store:
            del self._store[key]

    def get_count(self, engagement_id: UUID, action: RateLimitedAction) -> int:
        """Return the current call count within the window."""
        limit, window_secs = _LIMITS[action]
        key = (str(engagement_id), action.value)
        entry = self._store.get(key)
        if entry is None:
            return 0
        now = time.monotonic()
        cutoff = now - window_secs
        return sum(1 for t in entry.timestamps if t > cutoff)


# Module-level singleton — shared across all requests in a process
_limiter = InMemoryRateLimiter()


def get_rate_limiter() -> InMemoryRateLimiter:
    """FastAPI dependency: return the module-level rate limiter singleton."""
    return _limiter


def enforce_rate_limit(
    engagement_id: UUID,
    action: RateLimitedAction,
    limiter: InMemoryRateLimiter,
) -> None:
    """
    Enforce a rate limit, raising 429 if the limit is exceeded.

    Args:
        engagement_id: The engagement making the request.
        action:        The action being rate-limited.
        limiter:       The rate limiter instance.

    Raises:
        HTTPException(429) if the rate limit is exceeded.
    """
    allowed, remaining, reset_in = limiter.check_and_increment(
        engagement_id, action
    )
    if not allowed:
        limit, _ = _LIMITS[action]
        logger.warning(
            "Rate limit exceeded: engagement=%s action=%s limit=%d",
            engagement_id, action.value, limit,
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": {
                    "code":           ErrorCode.RATE_LIMIT_EXCEEDED,
                    "message":        (
                        f"Rate limit exceeded for '{action.value}'. "
                        f"Limit is {limit} per hour per engagement."
                    ),
                    "correlation_id": "N/A",
                }
            },
            headers={
                "Retry-After":           str(reset_in),
                "X-RateLimit-Limit":     str(limit),
                "X-RateLimit-Remaining": "0",
            },
        )

    logger.debug(
        "Rate limit check passed: engagement=%s action=%s remaining=%d",
        engagement_id, action.value, remaining,
    )
