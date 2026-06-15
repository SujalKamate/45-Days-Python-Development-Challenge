"""T-Digest streaming quantile estimation and online percentile analytics."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
import heapq
import json
import math
import threading
import time


class Centroid:
    """Weighted centroid representing a cluster of nearby values."""

    def __init__(self, mean: float, weight: float = 1.0) -> None:
        self.mean = mean
        self.weight = weight

    def add(self, value: float, w: float = 1.0) -> None:
        total = self.weight + w
        self.mean = self.mean + (value - self.mean) * w / total
        self.weight = total

    def distance(self, value: float) -> float:
        return abs(self.mean - value)

    def to_dict(self) -> Dict[str, float]:
        return {'mean': self.mean, 'weight': self.weight}

    @staticmethod
    def from_dict(data: Dict[str, float]) -> Centroid:
        return Centroid(data['mean'], data['weight'])


def _scale(k: int, compression: float) -> float:
    """Scale function that determines cluster size based on quantile."""
    return 2.0 * compression / (k + 1.0)


class TDigest:
    """T-Digest for streaming quantile estimation with bounded memory.

    Maintains sorted centroids dynamically merged using a scale function
    for tail-sensitive accuracy.
    """

    def __init__(self, compression: float = 100.0) -> None:
        if compression < 1:
            raise ValueError('Compression must be >= 1')
        self.compression: float = compression
        self._centroids: List[Centroid] = []
        self._total_weight: float = 0.0
        self._min: float = float('inf')
        self._max: float = float('-inf')
        self._lock = threading.Lock()
        self._uid = f'td:{id(self):x}'

    def add(self, value: float, weight: float = 1.0) -> None:
        if weight <= 0:
            return
        with self._lock:
            self._total_weight += weight
            if value < self._min:
                self._min = value
            if value > self._max:
                self._max = value
            nearest = self._find_nearest(value)
            if nearest is not None:
                nearest.add(value, weight)
            else:
                self._centroids.append(Centroid(value, weight))
            if len(self._centroids) > self.compression * 2:
                self._compress()

    def _find_nearest(self, value: float) -> Optional[Centroid]:
        best: Optional[Centroid] = None
        best_dist = float('inf')
        for c in self._centroids:
            d = c.distance(value)
            if d < best_dist:
                best_dist = d
                best = c
        return best

    def _compress(self) -> None:
        if not self._centroids:
            return
        self._centroids.sort(key=lambda c: c.mean)
        centroids = self._centroids
        total = self._total_weight
        compression = self.compression
        merged: List[Centroid] = []
        q0 = 0.0
        for c in centroids:
            q1 = q0 + c.weight / total
            for m in merged[::-1]:
                qm = (q1 - m.weight / total) if len(merged) > 0 else q0
                if m.weight + c.weight <= _scale(len(merged), compression) * total:
                    m.add(c.mean, c.weight)
                    c = m
                    merged.pop()
                else:
                    break
            merged.append(c)
            q0 = q1
        self._centroids = merged

    def percentile(self, p: float) -> float:
        if not self._centroids:
            return 0.0
        if p <= 0:
            return self._min if math.isfinite(self._min) else 0.0
        if p >= 100:
            return self._max if math.isfinite(self._max) else 0.0
        with self._lock:
            sorted_c = sorted(self._centroids, key=lambda c: c.mean)
            total = self._total_weight
            target = p / 100.0 * total
            cumulative = 0.0
            for i, c in enumerate(sorted_c):
                cumulative += c.weight
                if cumulative >= target:
                    if i == 0:
                        return c.mean
                    prev = sorted_c[i - 1]
                    prev_total = cumulative - c.weight
                    frac = (target - prev_total) / c.weight
                    return prev.mean + (c.mean - prev.mean) * frac
            return sorted_c[-1].mean

    def cdf(self, value: float) -> float:
        if not self._centroids or not math.isfinite(value):
            return 0.0
        with self._lock:
            sorted_c = sorted(self._centroids, key=lambda c: c.mean)
            total = self._total_weight
            if value <= sorted_c[0].mean:
                return 0.0
            if value >= sorted_c[-1].mean:
                return 1.0
            cumulative = 0.0
            for i, c in enumerate(sorted_c):
                if value <= c.mean:
                    prev = sorted_c[i - 1]
                    frac = (value - prev.mean) / (c.mean - prev.mean) if c.mean != prev.mean else 0.0
                    return (cumulative - c.weight + c.weight * frac) / total
                cumulative += c.weight
            return 1.0

    def merge(self, other: TDigest) -> None:
        with self._lock, other._lock:
            for c in other._centroids:
                nearest = self._find_nearest(c.mean)
                if nearest is not None:
                    nearest.add(c.mean, c.weight)
                else:
                    self._centroids.append(Centroid(c.mean, c.weight))
            self._total_weight += other._total_weight
            if other._min < self._min:
                self._min = other._min
            if other._max > self._max:
                self._max = other._max
            self._compress()

    def count(self) -> int:
        return int(self._total_weight)

    def centroids_count(self) -> int:
        return len(self._centroids)

    def clear(self) -> None:
        with self._lock:
            self._centroids.clear()
            self._total_weight = 0.0
            self._min = float('inf')
            self._max = float('-inf')

    def to_dict(self) -> Dict[str, Any]:
        with self._lock:
            return {
                'compression': self.compression,
                'total_weight': self._total_weight,
                'min': self._min,
                'max': self._max,
                'centroids': [c.to_dict() for c in self._centroids],
            }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> TDigest:
        td = TDigest(data['compression'])
        td._total_weight = data.get('total_weight', 0.0)
        td._min = data.get('min', float('inf'))
        td._max = data.get('max', float('-inf'))
        td._centroids = [Centroid.from_dict(c) for c in data.get('centroids', [])]
        return td


class TDigestHistorian:
    """Snapshot history for T-Digest instances."""

    def __init__(self, max_snapshots: int = 100) -> None:
        self.max_snapshots = max_snapshots
        self._snapshots: List[Dict[str, Any]] = []
        self._lock = threading.Lock()

    def snapshot(self, digest: TDigest) -> int:
        with self._lock:
            self._snapshots.append({
                'time': time.time(),
                'data': digest.to_dict(),
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


class TDigestEngine:
    """Top-level engine managing multiple T-Digest instances."""

    def __init__(self) -> None:
        self._digests: Dict[str, TDigest] = {}
        self._default_digest: Optional[TDigest] = None
        self._historian = TDigestHistorian()
        self._lock = threading.Lock()

    def create(self, name: str = 'default', compression: float = 100.0) -> TDigest:
        td = TDigest(compression)
        with self._lock:
            self._digests[name] = td
            if name == 'default':
                self._default_digest = td
        return td

    def get(self, name: str = 'default') -> TDigest:
        with self._lock:
            if name in self._digests:
                return self._digests[name]
            if self._default_digest is None:
                self._default_digest = self.create()
            return self._default_digest

    def remove(self, name: str) -> bool:
        with self._lock:
            if name in self._digests:
                del self._digests[name]
                if name == 'default':
                    self._default_digest = None
                return True
            return False

    def list(self) -> List[str]:
        with self._lock:
            return list(self._digests.keys())

    def add(self, value: float, weight: float = 1.0, name: str = 'default') -> None:
        self.get(name).add(value, weight)

    def add_batch(self, values: List[float], name: str = 'default') -> None:
        td = self.get(name)
        for v in values:
            td.add(v)

    def percentile(self, p: float, name: str = 'default') -> float:
        return self.get(name).percentile(p)

    def cdf(self, value: float, name: str = 'default') -> float:
        return self.get(name).cdf(value)

    def merge(self, dst: str, src: str) -> bool:
        with self._lock:
            if dst not in self._digests or src not in self._digests:
                return False
            self._digests[dst].merge(self._digests[src])
            return True

    def count(self, name: str = 'default') -> int:
        return self.get(name).count()

    def centroids_count(self, name: str = 'default') -> int:
        return self.get(name).centroids_count()

    def clear(self, name: str = 'default') -> None:
        self.get(name).clear()

    def clear_all(self) -> None:
        with self._lock:
            for td in self._digests.values():
                td.clear()

    def snapshot(self, name: str = 'default') -> int:
        return self._historian.snapshot(self.get(name))

    def history(self, n: int = 10) -> List[Dict[str, Any]]:
        return self._historian.history(n)

    def summary(self) -> Dict[str, Any]:
        with self._lock:
            return {
                'digest_count': len(self._digests),
                'digest_names': list(self._digests.keys()),
                'historian_snapshots': len(self._historian._snapshots),
            }
