"""Tiny in-memory rate limiters (single process, which this server must be anyway)."""

from __future__ import annotations

import time
from collections import deque


class SlidingWindow:
    """Allow at most `limit` events per `window` seconds per key."""

    def __init__(self, limit: int, window: float, max_keys: int = 50_000) -> None:
        self.limit = limit
        self.window = window
        self.max_keys = max_keys
        self._hits: dict[str, deque[float]] = {}

    def _prune(self, key: str, now: float) -> deque[float]:
        hits = self._hits.get(key)
        if hits is None:
            if len(self._hits) >= self.max_keys:
                self._gc(now)
            hits = self._hits.setdefault(key, deque())
        while hits and now - hits[0] > self.window:
            hits.popleft()
        return hits

    def _gc(self, now: float) -> None:
        for k in [k for k, v in self._hits.items() if not v or now - v[-1] > self.window]:
            del self._hits[k]

    def blocked(self, key: str) -> bool:
        if self.limit <= 0:
            return False
        return len(self._prune(key, time.monotonic())) >= self.limit

    def hit(self, key: str) -> None:
        if self.limit <= 0:
            return
        self._prune(key, time.monotonic()).append(time.monotonic())

    def reset(self, key: str) -> None:
        self._hits.pop(key, None)


class TokenBucket:
    def __init__(self, rate: float, burst: int) -> None:
        self.rate = rate
        self.capacity = burst
        self.tokens = float(burst)
        self.last = time.monotonic()

    def allow(self) -> bool:
        if self.rate <= 0:
            return True
        now = time.monotonic()
        self.tokens = min(self.capacity, self.tokens + (now - self.last) * self.rate)
        self.last = now
        if self.tokens >= 1:
            self.tokens -= 1
            return True
        return False
