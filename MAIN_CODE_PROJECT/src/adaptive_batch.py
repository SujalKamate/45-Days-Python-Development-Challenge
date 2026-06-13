"""Adaptive batch processor — dynamically adjusts batch size based on throughput and latency."""

from __future__ import annotations

from typing import Any, Callable, List, Optional, TypeVar
import threading
import time


T = TypeVar('T')


class ThroughputMonitor:
    """Measures processing throughput (items/sec) over a sliding window."""

    def __init__(self, window: int = 10) -> None:
        self._samples: List[float] = []
        self._window = window
        self._lock = threading.Lock()

    def record(self, items: int, elapsed: float) -> None:
        rate = items / elapsed if elapsed > 0 else 0.0
        with self._lock:
            self._samples.append(rate)
            if len(self._samples) > self._window:
                self._samples.pop(0)

    @property
    def avg_throughput(self) -> float:
        with self._lock:
            if not self._samples:
                return 0.0
            return sum(self._samples) / len(self._samples)

    @property
    def p50(self) -> float:
        with self._lock:
            if not self._samples:
                return 0.0
            s = sorted(self._samples)
            return s[len(s) // 2]


class AdaptiveBatcher:
    """Dynamically adjusts batch size based on observed processing rates and latency targets.

    Uses additive-increase-multiplicative-decrease (AIMD) to converge
    on optimal batch size.
    """

    def __init__(self, min_batch: int = 1, max_batch: int = 1024,
                 target_latency: float = 0.5, target_throughput: float = 100.0,
                 adjustment_interval: float = 2.0) -> None:
        self._min = min_batch
        self._max = max_batch
        self._target_latency = target_latency
        self._target_throughput = target_throughput
        self._adjust_interval = adjustment_interval
        self._current = min_batch
        self._monitor = ThroughputMonitor()
        self._last_adjust = time.monotonic()
        self._lock = threading.Lock()

    @property
    def current(self) -> int:
        return self._current

    def update(self, batch_size: int, elapsed: float) -> None:
        self._monitor.record(batch_size, elapsed)
        now = time.monotonic()
        with self._lock:
            if now - self._last_adjust < self._adjust_interval:
                return
            self._last_adjust = now
            self._adjust()

    def _adjust(self) -> None:
        throughput = self._monitor.avg_throughput
        if throughput <= 0:
            return
        latency_per_item = 1.0 / throughput if throughput > 0 else 0.0
        if latency_per_item > self._target_latency and self._current > self._min:
            self._current = max(self._min, int(self._current * 0.75))
        elif throughput < self._target_throughput * 0.8:
            self._current = min(self._max, self._current + 1)
        elif throughput > self._target_throughput * 1.2:
            self._current = min(self._max, int(self._current * 1.25))
        else:
            self._current = min(self._max, self._current + 1)

    def resize(self, min_batch: Optional[int] = None,
               max_batch: Optional[int] = None) -> None:
        with self._lock:
            if min_batch is not None:
                self._min = min_batch
            if max_batch is not None:
                self._max = max_batch
            self._current = max(self._min, min(self._current, self._max))


class AdaptiveBatchProcessor:
    """Processes items in dynamically-sized batches using AdaptiveBatcher."""

    def __init__(self, processor_fn: Callable[[List[Any]], List[Any]],
                 min_batch: int = 1, max_batch: int = 1024,
                 target_latency: float = 0.5) -> None:
        self._fn = processor_fn
        self._batcher = AdaptiveBatcher(min_batch, max_batch, target_latency)
        self._lock = threading.Lock()

    def process(self, items: List[Any]) -> List[Any]:
        results: List[Any] = []
        idx = 0
        while idx < len(items):
            batch_size = min(self._batcher.current, len(items) - idx)
            batch = items[idx: idx + batch_size]
            start = time.monotonic()
            try:
                batch_results = self._fn(batch)
                results.extend(batch_results)
            except Exception:
                batch_results = []
                for item in batch:
                    try:
                        batch_results.append(self._fn([item])[0])
                    except Exception:
                        batch_results.append(None)
                results.extend(batch_results)
            elapsed = time.monotonic() - start
            self._batcher.update(batch_size, elapsed)
            idx += batch_size
        return results

    @property
    def batch_size(self) -> int:
        return self._batcher.current
