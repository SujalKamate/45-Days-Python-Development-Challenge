"""
Rate Limiter and Exponential Backoff Retry Mechanism with Mock API Simulation
Implements N calls/second rate limiter, retry with backoff, mock API, full logging.
"""

import time
import random
import threading
import functools
from datetime import datetime
from collections import deque


# ── Rate Limiter ──────────────────────────────────────────────────────────────
class RateLimiter:
    """
    Token-bucket style rate limiter.
    Allows up to `max_calls` per `period` seconds.
    """
    def __init__(self, max_calls: int, period: float = 1.0):
        self.max_calls = max_calls
        self.period    = period
        self._lock     = threading.Lock()
        self._calls: deque = deque()   # timestamps of recent calls

    def acquire(self, block=True):
        """
        Acquire a slot. If block=True, waits until a slot is available.
        Returns True if acquired, False if not blocking and no slot.
        """
        while True:
            with self._lock:
                now = time.monotonic()
                # Remove calls outside the window
                while self._calls and now - self._calls[0] >= self.period:
                    self._calls.popleft()

                if len(self._calls) < self.max_calls:
                    self._calls.append(now)
                    return True
                else:
                    if not block:
                        return False
                    # Calculate wait time
                    oldest = self._calls[0]
                    wait   = self.period - (now - oldest)

            if wait > 0:
                time.sleep(wait)

    def __call__(self, func):
        """Use as decorator: @rate_limiter"""
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            self.acquire()
            return func(*args, **kwargs)
        return wrapper

    @property
    def current_usage(self):
        with self._lock:
            now = time.monotonic()
            return sum(1 for t in self._calls if now - t < self.period)


# ── Exponential Backoff ───────────────────────────────────────────────────────
class RetryError(Exception):
    pass


def retry_with_backoff(
    func,
    max_retries:   int   = 5,
    base_delay:    float = 0.5,
    max_delay:     float = 30.0,
    backoff_factor: float = 2.0,
    jitter:        bool  = True,
    exceptions:    tuple = (Exception,),
    on_retry=None,
    logger=None,
):
    """
    Calls func(); on failure retries with exponential backoff.
    Returns result or raises RetryError after max_retries.
    """
    attempt = 0
    delay   = base_delay

    while attempt <= max_retries:
        try:
            result = func()
            if logger:
                logger(f"[attempt {attempt+1}] SUCCESS")
            return result

        except exceptions as e:
            attempt += 1
            if attempt > max_retries:
                msg = f"All {max_retries} retries exhausted. Last error: {e}"
                if logger:
                    logger(f"[attempt {attempt}] FAILED PERMANENTLY: {e}")
                raise RetryError(msg) from e

            actual_delay = min(delay, max_delay)
            if jitter:
                actual_delay *= (0.5 + random.random())

            if logger:
                logger(f"[attempt {attempt}] FAILED ({e}) — retrying in {actual_delay:.2f}s")
            if on_retry:
                on_retry(attempt, e, actual_delay)

            time.sleep(actual_delay)
            delay *= backoff_factor


# ── Mock API ──────────────────────────────────────────────────────────────────
class MockAPI:
    """
    Simulates an unreliable HTTP API.
    Fails with given probability, tracks call counts.
    """
    def __init__(self, fail_rate=0.6, latency=(0.01, 0.05)):
        self.fail_rate    = fail_rate
        self.latency      = latency
        self.call_count   = 0
        self.success_count = 0
        self.fail_count    = 0
        self._lock        = threading.Lock()

    def call(self, endpoint="/data", payload=None):
        with self._lock:
            self.call_count += 1

        time.sleep(random.uniform(*self.latency))   # simulate network

        if random.random() < self.fail_rate:
            with self._lock:
                self.fail_count += 1
            error_codes = [429, 500, 502, 503, 504]
            code = random.choice(error_codes)
            raise ConnectionError(f"HTTP {code} — {'Rate limited' if code==429 else 'Server error'}")

        with self._lock:
            self.success_count += 1

        return {
            "status":    "ok",
            "endpoint":  endpoint,
            "data":      f"payload_{random.randint(1000, 9999)}",
            "timestamp": datetime.now().isoformat(),
        }

    def stats(self):
        return {
            "total":    self.call_count,
            "success":  self.success_count,
            "failures": self.fail_count,
            "rate":     f"{self.success_count/max(self.call_count,1)*100:.1f}%",
        }


# ── Combined: Rate-Limited + Retry Wrapper ────────────────────────────────────
class APIClient:
    def __init__(self, api: MockAPI, rate_limit: int = 3, period: float = 1.0):
        self.api     = api
        self.limiter = RateLimiter(rate_limit, period)
        self.log     = []
        self._lock   = threading.Lock()

    def _log(self, msg):
        ts = datetime.now().strftime("%H:%M:%S.%f")[:12]
        entry = f"[{ts}] {msg}"
        with self._lock:
            self.log.append(entry)
        print(f"  {entry}")

    def fetch(self, endpoint="/data", max_retries=4):
        self.limiter.acquire()
        self._log(f"→ Calling {endpoint}  (usage={self.limiter.current_usage}/{self.limiter.max_calls})")

        def attempt():
            return self.api.call(endpoint)

        try:
            result = retry_with_backoff(
                attempt,
                max_retries=max_retries,
                base_delay=0.2,
                backoff_factor=2.0,
                jitter=True,
                exceptions=(ConnectionError,),
                logger=self._log,
            )
            self._log(f"✓ Got: {result['data']}")
            return result
        except RetryError as e:
            self._log(f"✗ Gave up: {e}")
            return None

    def bulk_fetch(self, endpoints, max_retries=3):
        results = []
        for ep in endpoints:
            r = self.fetch(ep, max_retries)
            results.append((ep, r))
        return results


# ── Print helpers ─────────────────────────────────────────────────────────────
def print_divider(title=""):
    print(f"\n  {'═'*55}")
    if title:
        print(f"  {title}")
        print(f"  {'─'*55}")


def print_api_stats(api: MockAPI, label="API Stats"):
    s = api.stats()
    print(f"\n  {label}:")
    print(f"    Total calls : {s['total']}")
    print(f"    Successes   : {s['success']}")
    print(f"    Failures    : {s['failures']}")
    print(f"    Success rate: {s['rate']}")


def demo_rate_limiter():
    print_divider("Demo 1: Rate Limiter (3 calls/sec)")
    limiter = RateLimiter(max_calls=3, period=1.0)
    timestamps = []

    for i in range(9):
        limiter.acquire()
        now = time.time()
        timestamps.append(now)
        print(f"  Call {i+1:>2} granted at t={now:.3f}")

    # Show that calls were spaced correctly
    gaps = [timestamps[i+1] - timestamps[i] for i in range(len(timestamps)-1)]
    print(f"\n  Gaps between calls: {[f'{g:.3f}s' for g in gaps]}")
    print(f"  (Gaps ≥0.33s every 3rd call confirms rate limiting)")


def demo_backoff():
    print_divider("Demo 2: Exponential Backoff (always-fail function)")
    attempts_log = []

    def always_fail():
        raise ConnectionError("Simulated permanent failure")

    delays = []

    def on_retry(attempt, error, delay):
        delays.append(delay)
        attempts_log.append(attempt)

    try:
        retry_with_backoff(
            always_fail,
            max_retries=5,
            base_delay=0.1,
            backoff_factor=2.0,
            jitter=False,
            exceptions=(ConnectionError,),
            on_retry=on_retry,
            logger=lambda m: print(f"  {m}"),
        )
    except RetryError as e:
        print(f"\n  ✗ RetryError raised as expected.")

    print(f"\n  Retry delays: {[f'{d:.2f}s' for d in delays]}")
    print(f"  (Each ~2× previous — exponential backoff confirmed)")


def demo_combined():
    print_divider("Demo 3: Rate-Limited API Client (fail_rate=50%)")
    api    = MockAPI(fail_rate=0.5, latency=(0.005, 0.02))
    client = APIClient(api, rate_limit=4, period=1.0)

    endpoints = [f"/api/resource/{i}" for i in range(1, 9)]
    print(f"  Fetching {len(endpoints)} endpoints with rate=4/sec, retries=3\n")

    start = time.time()
    results = client.bulk_fetch(endpoints, max_retries=3)
    elapsed = time.time() - start

    success = sum(1 for _, r in results if r)
    print(f"\n  Results: {success}/{len(results)} successful")
    print(f"  Time   : {elapsed:.2f}s")
    print_api_stats(api, "Final API Stats")


def main():
    print("╔══════════════════════════════════════════╗")
    print("║   Rate Limiter & Retry Mechanism v1.0   ║")
    print("╚══════════════════════════════════════════╝")

    demo_rate_limiter()
    demo_backoff()
    demo_combined()

    print("\n  All demos complete.")


if __name__ == "__main__":
    main()
