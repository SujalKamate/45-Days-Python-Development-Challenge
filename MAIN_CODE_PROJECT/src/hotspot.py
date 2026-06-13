"""Hotspot detection and automatic rebalancing for skewed partition distribution."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple
import threading
import time


class LoadSample:
    __slots__ = ('key', 'count', 'timestamp')

    def __init__(self, key: str, count: int) -> None:
        self.key = key
        self.count = count
        self.timestamp = time.monotonic()


class HotspotDetector:
    """Detects skewed keys based on access frequency relative to distribution."""

    def __init__(self, window: int = 100, threshold: float = 3.0) -> None:
        self._window = window
        self._threshold = threshold
        self._freq: Dict[str, int] = {}
        self._total = 0
        self._lock = threading.Lock()

    def record(self, key: str, count: int = 1) -> None:
        with self._lock:
            self._freq[key] = self._freq.get(key, 0) + count
            self._total += count
            if self._total > self._window * 2:
                self._decay()

    def _decay(self) -> None:
        factor = 0.5
        for k in list(self._freq.keys()):
            self._freq[k] = max(1, int(self._freq[k] * factor))
        self._total = sum(self._freq.values())

    def hotspots(self) -> List[Tuple[str, int, float]]:
        with self._lock:
            if not self._freq or self._total == 0:
                return []
            n = len(self._freq)
            mean = self._total / n
            results: List[Tuple[str, int, float]] = []
            for key, count in sorted(self._freq.items(), key=lambda x: -x[1]):
                ratio = count / mean if mean > 0 else float(count)
                if ratio >= self._threshold:
                    results.append((key, count, ratio))
            return results

    @property
    def is_skewed(self) -> bool:
        return len(self.hotspots()) > 0


class PartitionRebalancer:
    """Monitors partition sizes and triggers rebalancing when skew exceeds threshold."""

    def __init__(self, max_skew: float = 1.5, min_rebalance_interval: float = 10.0) -> None:
        self._max_skew = max_skew
        self._min_interval = min_rebalance_interval
        self._last_rebalance = 0.0
        self._lock = threading.Lock()

    def compute_skew(self, partition_sizes: Dict[int, int]) -> float:
        if not partition_sizes:
            return 0.0
        sizes = list(partition_sizes.values())
        if len(sizes) < 2:
            return 0.0
        max_size = max(sizes)
        min_size = min(sizes)
        if min_size == 0:
            return float(max_size)
        return max_size / min_size

    def needs_rebalance(self, partition_sizes: Dict[int, int]) -> bool:
        now = time.monotonic()
        with self._lock:
            if now - self._last_rebalance < self._min_interval:
                return False
            skew = self.compute_skew(partition_sizes)
            return skew > self._max_skew

    def mark_rebalanced(self) -> None:
        with self._lock:
            self._last_rebalance = time.monotonic()


class KeySplitter:
    """Splits hot keys into sub-keys for distribution across partitions."""

    def __init__(self, suffix_count: int = 4) -> None:
        self._suffix_count = suffix_count

    def split(self, key: str) -> List[str]:
        return [f'{key}:shard:{i}' for i in range(self._suffix_count)]

    def merge(self, sub_keys: List[str], values: Dict[str, Any]) -> Any:
        return values.get(sub_keys[0])


class AutoRebalancer:
    """Combines detection + rebalancing for automatic skew mitigation."""

    def __init__(self, rebalance_fn: Callable[[], int],
                 max_skew: float = 1.5, check_interval: float = 5.0) -> None:
        self._detector = HotspotDetector()
        self._rebalancer = PartitionRebalancer(max_skew)
        self._rebalance_fn = rebalance_fn
        self._check_interval = check_interval
        self._last_check = 0.0
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def record_access(self, key: str) -> None:
        self._detector.record(key)

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False

    def _loop(self) -> None:
        while self._running:
            now = time.monotonic()
            if now - self._last_check >= self._check_interval:
                self._last_check = now
                if self._detector.is_skewed:
                    self._rebalance_fn()
                    self._rebalancer.mark_rebalanced()
            time.sleep(1.0)

    def check_and_rebalance(self, partition_sizes: Dict[int, int]) -> bool:
        if self._rebalancer.needs_rebalance(partition_sizes):
            moved = self._rebalance_fn()
            self._rebalancer.mark_rebalanced()
            return moved > 0
        return False
