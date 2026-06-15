"""Count-Min Sketch with Top-K Heavy Hitters and Approximate Frequency Estimation."""

from __future__ import annotations

from typing import Any, Dict, Hashable, List, Optional, Tuple
import hashlib
import heapq
import json
import math
import random
import threading
import time


_CM_COUNTER: int = 0


def _cm_uid() -> str:
    global _CM_COUNTER
    _CM_COUNTER += 1
    return f'cm:{_CM_COUNTER:x}'


def _hash(item: Hashable, seed: int) -> int:
    """Pairwise-independent hash via SHA-256 with a per-row seed."""
    h = hashlib.sha256(f'{seed}:{item}'.encode('utf-8'))
    return int(h.hexdigest(), 16)


def _estimate_params(epsilon: float, delta: float) -> Tuple[int, int]:
    """Return (width w, depth d) for given accuracy guarantees."""
    w = math.ceil(math.e / epsilon)
    d = math.ceil(math.log(1.0 / delta))
    return w, d


class CountMinSketch:
    """Probabilistic frequency estimation with configurable epsilon/delta.

    Provides approximate point queries, range queries, inner-product
    estimation, merge, and confidence intervals.
    """

    def __init__(self, epsilon: float = 0.01, delta: float = 0.99,
                 d: Optional[int] = None, w: Optional[int] = None) -> None:
        if d is None or w is None:
            w, d = _estimate_params(epsilon, delta)
        self.w: int = w
        self.d: int = d
        self._counters: List[List[int]] = [[0] * w for _ in range(d)]
        self._seeds: List[int] = [random.randint(0, 1 << 31) for _ in range(d)]
        self._total: int = 0
        self._lock = threading.Lock()
        self._uid = _cm_uid()

    def add(self, item: Hashable, count: int = 1) -> None:
        if count < 1:
            return
        with self._lock:
            for i in range(self.d):
                idx = _hash(item, self._seeds[i]) % self.w
                self._counters[i][idx] += count
            self._total += count

    def estimate(self, item: Hashable) -> int:
        """Return the approximate frequency of *item* (over-estimate bound)."""
        vals = []
        for i in range(self.d):
            idx = _hash(item, self._seeds[i]) % self.w
            vals.append(self._counters[i][idx])
        return min(vals)

    def estimate_confidence(self, item: Hashable) -> Dict[str, float]:
        """Return point estimate + median-based confidence interval."""
        vals = []
        for i in range(self.d):
            idx = _hash(item, self._seeds[i]) % self.w
            vals.append(self._counters[i][idx])
        sorted_vals = sorted(vals)
        median = sorted_vals[len(sorted_vals) // 2]
        return {
            'estimate': int(min(vals)),
            'median': median,
            'min': int(sorted_vals[0]),
            'max': int(sorted_vals[-1]),
        }

    def total(self) -> int:
        return self._total

    def merge(self, other: CountMinSketch) -> CountMinSketch:
        if self.w != other.w or self.d != other.d:
            raise ValueError('Sketch dimensions must match for merge')
        merged = CountMinSketch(w=self.w, d=self.d)
        for i in range(self.d):
            for j in range(self.w):
                merged._counters[i][j] = self._counters[i][j] + other._counters[i][j]
        merged._total = self._total + other._total
        return merged

    def inner_product(self, other: CountMinSketch) -> int:
        """Approximate inner product of two frequency vectors."""
        if self.w != other.w or self.d != other.d:
            raise ValueError('Sketch dimensions must match for inner product')
        vals = []
        for i in range(self.d):
            ip = sum(self._counters[i][j] * other._counters[i][j] for j in range(self.w))
            vals.append(ip)
        return min(vals)

    def clear(self) -> None:
        with self._lock:
            for i in range(self.d):
                self._counters[i] = [0] * self.w
            self._total = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'uid': self._uid,
            'w': self.w,
            'd': self.d,
            'total': self._total,
            'seeds': list(self._seeds),
            'counters': [list(row) for row in self._counters],
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> CountMinSketch:
        sketch = CountMinSketch(w=data['w'], d=data['d'])
        sketch._uid = data.get('uid', _cm_uid())
        sketch._total = data.get('total', 0)
        sketch._seeds = list(data.get('seeds', [random.randint(0, 1 << 31) for _ in range(sketch.d)]))
        for i in range(sketch.d):
            sketch._counters[i] = list(data['counters'][i])
        return sketch


class HeavyHitter:
    """Representation of a heavy hitter with estimated count."""

    def __init__(self, item: Hashable, estimate: int) -> None:
        self.item = item
        self.estimate = estimate

    def __lt__(self, other: HeavyHitter) -> bool:
        return self.estimate < other.estimate

    def to_dict(self) -> Dict[str, Any]:
        return {'item': str(self.item), 'estimate': self.estimate}


class TopKTracker:
    """Bounded min-heap tracking the top-K heavy hitters via sketch estimates."""

    def __init__(self, k: int, min_estimate: int = 1) -> None:
        self.k = k
        self.min_estimate = min_estimate
        self._heap: List[HeavyHitter] = []
        self._seen: set[Hashable] = set()
        self._lock = threading.Lock()

    def update(self, item: Hashable, estimate: int) -> None:
        if estimate < self.min_estimate or not isinstance(item, Hashable):
            return
        with self._lock:
            item_key = _make_key(item)
            if item_key in self._seen:
                return
            if len(self._heap) < self.k:
                heapq.heappush(self._heap, HeavyHitter(item, estimate))
                self._seen.add(item_key)
            elif estimate > self._heap[0].estimate:
                smallest = heapq.heappop(self._heap)
                self._seen.discard(_make_key(smallest.item))
                heapq.heappush(self._heap, HeavyHitter(item, estimate))
                self._seen.add(item_key)

    def top_k(self) -> List[HeavyHitter]:
        with self._lock:
            return sorted(self._heap, key=lambda h: h.estimate, reverse=True)

    def clear(self) -> None:
        with self._lock:
            self._heap.clear()
            self._seen.clear()

    def to_dict(self) -> Dict[str, Any]:
        return {
            'k': self.k,
            'min_estimate': self.min_estimate,
            'items': [h.to_dict() for h in self.top_k()],
        }


def _make_key(item: Any) -> int:
    try:
        return hash(item)
    except TypeError:
        return hash(str(item))


class FrequencyEstimator:
    """High-level frequency estimation facade with sketch + top-k integration."""

    def __init__(self, epsilon: float = 0.01, delta: float = 0.99,
                 top_k: int = 20) -> None:
        self.sketch = CountMinSketch(epsilon, delta)
        self.tracker = TopKTracker(top_k)
        self._history: List[Dict[str, Any]] = []
        self._lock = threading.Lock()
        self._uid = _cm_uid()

    def add(self, item: Hashable, count: int = 1) -> None:
        self.sketch.add(item, count)
        est = self.sketch.estimate(item)
        self.tracker.update(item, est)

    def estimate(self, item: Hashable) -> int:
        return self.sketch.estimate(item)

    def estimate_confidence(self, item: Hashable) -> Dict[str, float]:
        return self.sketch.estimate_confidence(item)

    def top_k(self) -> List[HeavyHitter]:
        return self.tracker.top_k()

    def total(self) -> int:
        return self.sketch.total()

    def merge(self, other: FrequencyEstimator) -> FrequencyEstimator:
        merged = FrequencyEstimator(top_k=max(self.tracker.k, other.tracker.k))
        merged.sketch = self.sketch.merge(other.sketch)
        for hh in self.top_k() + other.top_k():
            merged.tracker.update(hh.item, hh.estimate)
        return merged

    def inner_product(self, other: FrequencyEstimator) -> int:
        return self.sketch.inner_product(other.sketch)

    def add_batch(self, items: List[Hashable]) -> None:
        for item in items:
            self.add(item)

    def clear(self) -> None:
        self.sketch.clear()
        self.tracker.clear()

    def to_dict(self) -> Dict[str, Any]:
        return {
            'uid': self._uid,
            'sketch': self.sketch.to_dict(),
            'top_k': self.tracker.to_dict(),
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> FrequencyEstimator:
        sketch = CountMinSketch.from_dict(data['sketch'])
        top_k_data = data.get('top_k', {})
        tracker = TopKTracker(top_k_data.get('k', 20), top_k_data.get('min_estimate', 1))
        for hd in top_k_data.get('items', []):
            tracker.update(hd.get('item', ''), hd.get('estimate', 0))
        est = FrequencyEstimator(top_k=tracker.k)
        est.sketch = sketch
        est.tracker = tracker
        est._uid = data.get('uid', _cm_uid())
        return est


class FreqHistorian:
    """Snapshot history for frequency estimators."""

    def __init__(self, max_snapshots: int = 100) -> None:
        self.max_snapshots = max_snapshots
        self._snapshots: List[Dict[str, Any]] = []
        self._lock = threading.Lock()

    def snapshot(self, estimator: FrequencyEstimator) -> int:
        with self._lock:
            self._snapshots.append({
                'time': time.time(),
                'data': estimator.to_dict(),
            })
            if len(self._snapshots) > self.max_snapshots:
                self._snapshots.pop(0)
            return len(self._snapshots)

    def history(self, n: int = 10) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._snapshots[-n:])

    def clear(self) -> None:
        with self._lock:
            self._snapshots.clear()


class CountMinSketchEngine:
    """Top-level engine exposing all count-min sketch operations."""

    def __init__(self) -> None:
        self._estimators: Dict[str, FrequencyEstimator] = {}
        self._default_est: Optional[FrequencyEstimator] = None
        self._historian = FreqHistorian()
        self._lock = threading.Lock()

    def create_estimator(self, name: str = 'default', epsilon: float = 0.01,
                         delta: float = 0.99, top_k: int = 20) -> FrequencyEstimator:
        est = FrequencyEstimator(epsilon, delta, top_k)
        with self._lock:
            self._estimators[name] = est
            if name == 'default':
                self._default_est = est
        return est

    def get_estimator(self, name: str = 'default') -> FrequencyEstimator:
        with self._lock:
            if name in self._estimators:
                return self._estimators[name]
            if self._default_est is None:
                self._default_est = self.create_estimator()
            return self._default_est

    def remove_estimator(self, name: str) -> bool:
        with self._lock:
            if name in self._estimators:
                del self._estimators[name]
                if name == 'default':
                    self._default_est = None
                return True
            return False

    def list_estimators(self) -> List[str]:
        with self._lock:
            return list(self._estimators.keys())

    def add(self, item: Hashable, count: int = 1, name: str = 'default') -> None:
        self.get_estimator(name).add(item, count)

    def add_batch(self, items: List[Hashable], name: str = 'default') -> None:
        self.get_estimator(name).add_batch(items)

    def estimate(self, item: Hashable, name: str = 'default') -> int:
        return self.get_estimator(name).estimate(item)

    def estimate_confidence(self, item: Hashable, name: str = 'default') -> Dict[str, float]:
        return self.get_estimator(name).estimate_confidence(item)

    def top_k(self, name: str = 'default') -> List[HeavyHitter]:
        return self.get_estimator(name).top_k()

    def total(self, name: str = 'default') -> int:
        return self.get_estimator(name).total()

    def merge(self, dst: str, src: str) -> bool:
        with self._lock:
            if dst not in self._estimators or src not in self._estimators:
                return False
            merged = self._estimators[dst].merge(self._estimators[src])
            self._estimators[dst] = merged
            return True

    def inner_product(self, name_a: str, name_b: str) -> Optional[int]:
        with self._lock:
            if name_a not in self._estimators or name_b not in self._estimators:
                return None
            return self._estimators[name_a].inner_product(self._estimators[name_b])

    def clear(self, name: str = 'default') -> None:
        self.get_estimator(name).clear()

    def clear_all(self) -> None:
        with self._lock:
            for est in self._estimators.values():
                est.clear()

    def snapshot(self, name: str = 'default') -> int:
        est = self.get_estimator(name)
        return self._historian.snapshot(est)

    def history(self, n: int = 10) -> List[Dict[str, Any]]:
        return self._historian.history(n)

    def summary(self) -> Dict[str, Any]:
        with self._lock:
            return {
                'estimator_count': len(self._estimators),
                'estimator_names': list(self._estimators.keys()),
                'historian_snapshots': len(self._historian._snapshots),
            }
