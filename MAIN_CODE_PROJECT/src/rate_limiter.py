"""Configurable rate limiter with token bucket for burst-aware throughput control."""

from __future__ import annotations

from typing import Any, Callable, List, Optional, TypeVar
import threading
import time


T = TypeVar('T')


class TokenBucket:
    """Token bucket rate limiter with configurable rate and burst capacity.

    Tokens refill at *rate* per second. Burst allows up to *capacity*
    tokens to accumulate for short spikes.
    """

    def __init__(self, rate: float, capacity: int) -> None:
        if rate <= 0:
            raise ValueError('rate must be > 0')
        self._rate = rate
        self._capacity = capacity
        self._tokens = float(capacity)
        self._last_refill = time.monotonic()
        self._lock = threading.Lock()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self._capacity, self._tokens + elapsed * self._rate)
        self._last_refill = now

    def try_consume(self, tokens: float = 1.0) -> bool:
        with self._lock:
            self._refill()
            if self._tokens >= tokens:
                self._tokens -= tokens
                return True
            return False

    def consume(self, tokens: float = 1.0) -> None:
        while not self.try_consume(tokens):
            time.sleep(0.001)

    def wait_time(self, tokens: float = 1.0) -> float:
        with self._lock:
            self._refill()
            if self._tokens >= tokens:
                return 0.0
            deficit = tokens - self._tokens
            return deficit / self._rate

    def set_rate(self, rate: float) -> None:
        with self._lock:
            self._rate = rate

    def set_capacity(self, capacity: int) -> None:
        with self._lock:
            self._capacity = capacity
            self._tokens = min(self._tokens, float(capacity))

    @property
    def rate(self) -> float:
        return self._rate

    @property
    def available(self) -> float:
        with self._lock:
            self._refill()
            return self._tokens


class RateLimiter:
    """Multi-key rate limiter backed by token buckets for per-resource throttling."""

    def __init__(self, default_rate: float = 10.0, default_capacity: int = 20) -> None:
        self._default_rate = default_rate
        self._default_capacity = default_capacity
        self._buckets: dict = {}
        self._lock = threading.Lock()

    def _bucket(self, key: str) -> TokenBucket:
        with self._lock:
            if key not in self._buckets:
                self._buckets[key] = TokenBucket(self._default_rate, self._default_capacity)
            return self._buckets[key]

    def try_acquire(self, key: str = 'default', tokens: float = 1.0) -> bool:
        return self._bucket(key).try_consume(tokens)

    def acquire(self, key: str = 'default', tokens: float = 1.0) -> None:
        self._bucket(key).consume(tokens)

    def configure(self, key: str, rate: float, capacity: int) -> None:
        bucket = self._bucket(key)
        bucket.set_rate(rate)
        bucket.set_capacity(capacity)

    def reset(self) -> None:
        with self._lock:
            self._buckets.clear()


class ThrottledExecutor:
    """Executes callables at a controlled rate using a token bucket."""

    def __init__(self, rate: float = 10.0, burst: int = 20) -> None:
        self._bucket = TokenBucket(rate, burst)

    def execute(self, fn: Callable[[], T]) -> T:
        self._bucket.consume()
        return fn()

    def try_execute(self, fn: Callable[[], T], default: Optional[T] = None) -> Optional[T]:
        if self._bucket.try_consume():
            return fn()
        return default

    def set_rate(self, rate: float, burst: Optional[int] = None) -> None:
        self._bucket.set_rate(rate)
        if burst is not None:
            self._bucket.set_capacity(burst)
