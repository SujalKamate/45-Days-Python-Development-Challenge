"""Speculative execution — hedged requests to mitigate straggler tasks."""

from __future__ import annotations

from typing import Any, Callable, List, Optional, TypeVar
import threading
import time


T = TypeVar('T')


class SpeculativeTask:
    """A task that can be speculatively re-executed if the first attempt is slow."""

    def __init__(self, fn: Callable[[], T], slow_threshold: float = 1.0,
                 max_specs: int = 2) -> None:
        self._fn = fn
        self._slow_threshold = slow_threshold
        self._max_specs = max_specs
        self._result: Optional[T] = None
        self._error: Optional[Exception] = None
        self._done = threading.Event()
        self._started = False
        self._lock = threading.Lock()

    def _run(self, result_container: list) -> None:
        try:
            result_container.append(self._fn())
        except Exception as e:
            result_container.append(e)

    def execute(self) -> T:
        results: list = []
        threads: list = []
        deadline = time.monotonic() + self._slow_threshold

        t = threading.Thread(target=self._run, args=(results,), daemon=True)
        t.start()
        threads.append(t)

        specs_launched = 0
        while True:
            if results:
                winner = results.pop(0)
                if isinstance(winner, Exception):
                    raise winner
                return winner

            elapsed = time.monotonic()
            if specs_launched < self._max_specs and elapsed >= deadline:
                specs_launched += 1
                st = threading.Thread(target=self._run, args=(results,), daemon=True)
                st.start()
                threads.append(st)
                deadline = elapsed + self._slow_threshold

            if all(not t.is_alive() for t in threads):
                break

            time.sleep(0.001)

        if results:
            winner = results[0]
            if isinstance(winner, Exception):
                raise winner
            return winner

        raise RuntimeError('Speculative execution produced no result')


class StragglerDetector:
    """Monitors task durations and identifies stragglers based on statistics."""

    def __init__(self, window: int = 20, multiplier: float = 2.0) -> None:
        self._durations: List[float] = []
        self._window = window
        self._multiplier = multiplier
        self._lock = threading.Lock()

    def record(self, duration: float) -> None:
        with self._lock:
            self._durations.append(duration)
            if len(self._durations) > self._window:
                self._durations.pop(0)

    def is_straggler(self, elapsed: float) -> bool:
        with self._lock:
            if len(self._durations) < 2:
                return elapsed > 1.0
            avg = sum(self._durations) / len(self._durations)
            return elapsed > avg * self._multiplier

    @property
    def p50(self) -> float:
        with self._lock:
            if not self._durations:
                return 0.0
            s = sorted(self._durations)
            return s[len(s) // 2]


class HedgedExecutor:
    """Executes tasks with speculative hedged requests for straggler mitigation."""

    def __init__(self, slow_threshold: float = 1.0, max_specs: int = 2,
                 slow_multiplier: float = 2.0) -> None:
        self._slow_threshold = slow_threshold
        self._max_specs = max_specs
        self._detector = StragglerDetector(multiplier=slow_multiplier)

    def execute(self, fn: Callable[[], T]) -> T:
        start = time.monotonic()
        threshold = self._slow_threshold
        if self._detector.is_straggler(0):
            threshold *= 0.5
        task = SpeculativeTask(fn, threshold, self._max_specs)
        try:
            result = task.execute()
            elapsed = time.monotonic() - start
            self._detector.record(elapsed)
            return result
        except Exception:
            elapsed = time.monotonic() - start
            self._detector.record(elapsed)
            raise

    def map(self, fns: List[Callable[[], Any]]) -> List[Any]:
        return [self.execute(fn) for fn in fns]
