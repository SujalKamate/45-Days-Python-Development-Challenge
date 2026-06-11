"""Drift-corrected timing using monotonic clocks.

Replaces naive ``time.sleep(interval)`` loops — which accumulate
scheduler latency — with a ``time.perf_counter()`` based approach
that measures actual elapsed time and adjusts each sleep duration
to stay aligned with the real target.
"""

import time


class Stopwatch:
    """Monotonic stopwatch that never drifts from wall-clock time.

    Usage::

        sw = Stopwatch()
        sw.start()
        # ... work ...
        elapsed = sw.elapsed()          # seconds since start
        sw.lap()                        # mark and return lap time
    """

    def __init__(self) -> None:
        self._start: float | None = None
        self._last_lap: float | None = None

    def start(self) -> None:
        self._start = time.perf_counter()
        self._last_lap = self._start

    def elapsed(self) -> float:
        if self._start is None:
            return 0.0
        return time.perf_counter() - self._start

    def lap(self) -> float:
        now = time.perf_counter()
        lap_time = now - (self._last_lap or now)
        self._last_lap = now
        return lap_time

    def reset(self) -> None:
        self._start = None
        self._last_lap = None


class DriftCorrectedTimer:
    """Timer that uses ``time.perf_counter()`` to correct cumulative drift.

    Unlike ``for _ in range(n): time.sleep(interval)``, this keeps
    the *absolute* timeline accurate even when individual ``sleep()``
    calls overshoot due to scheduler latency.
    """

    def __init__(self, interval: float = 1.0) -> None:
        self.interval = interval
        self._next_tick: float | None = None

    def start(self) -> None:
        self._next_tick = time.perf_counter() + self.interval

    def wait_tick(self) -> float:
        """Sleep until the next tick and return the overshoot (drift).

        The method always sleeps for exactly the right duration to
        keep ticks aligned with the original ``start()`` time.
        """
        if self._next_tick is None:
            self.start()
        now = time.perf_counter()
        sleep_for = max(0.0, self._next_tick - now)
        if sleep_for > 0:
            time.sleep(sleep_for)
        now = time.perf_counter()
        drift = now - self._next_tick
        self._next_tick += self.interval
        return drift

    def elapsed(self) -> float:
        if self._next_tick is None:
            return 0.0
        return time.perf_counter() - (self._next_tick - self.interval)
