"""Predictive state pre-loading with machine learning optimization framework."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Set, Tuple
import datetime
import json
import os
import threading
import time
import uuid
from collections import defaultdict


class AccessRecord:
    """Record of a single data access event."""

    def __init__(self, key: str, module: str = '',
                 access_type: str = 'read', elapsed_ms: float = 0.0) -> None:
        self.key = key
        self.module = module
        self.access_type = access_type
        self.elapsed_ms = elapsed_ms
        self.timestamp = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            'key': self.key,
            'module': self.module,
            'access_type': self.access_type,
            'elapsed_ms': round(self.elapsed_ms, 2),
            'timestamp': datetime.datetime.fromtimestamp(
                self.timestamp, datetime.timezone.utc
            ).isoformat(),
        }


class AccessPatternTracker:
    """Track historical data access patterns with temporal features."""

    def __init__(self) -> None:
        self._access_log: List[AccessRecord] = []
        self._lock = threading.Lock()
        self._frequency: Dict[str, int] = defaultdict(int)
        self._recency: Dict[str, float] = {}
        self._co_access: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))

    def record(self, key: str, module: str = '',
               access_type: str = 'read', elapsed_ms: float = 0.0) -> None:
        record = AccessRecord(key, module, access_type, elapsed_ms)
        with self._lock:
            self._access_log.append(record)
            self._frequency[key] += 1
            self._recency[key] = record.timestamp
            if self._access_log:
                prev = self._access_log[-2].key if len(self._access_log) >= 2 else None
                if prev and prev != key:
                    self._co_access[prev][key] += 1
                    self._co_access[key][prev] += 1

    def frequency(self, key: str) -> int:
        with self._lock:
            return self._frequency.get(key, 0)

    def recency(self, key: str) -> float:
        with self._lock:
            return self._recency.get(key, 0.0)

    def co_access_score(self, key: str, candidate: str) -> int:
        with self._lock:
            return self._co_access.get(key, {}).get(candidate, 0)

    def top_frequent(self, n: int = 10) -> List[Tuple[str, int]]:
        with self._lock:
            return sorted(self._frequency.items(), key=lambda x: -x[1])[:n]

    def recent_keys(self, seconds: float = 300.0) -> Set[str]:
        cutoff = time.time() - seconds
        with self._lock:
            return {k for k, t in self._recency.items() if t >= cutoff}

    def access_count(self) -> int:
        with self._lock:
            return len(self._access_log)


class FeatureExtractor:
    """Extract features from access patterns for prediction."""

    def __init__(self, tracker: AccessPatternTracker) -> None:
        self._tracker = tracker

    def score(self, key: str, context_key: Optional[str] = None) -> float:
        freq = self._tracker.frequency(key)
        recency = self._tracker.recency(key)
        age = time.time() - recency if recency > 0 else float('inf')
        recency_score = max(0.0, 1.0 - (age / 3600.0))
        co_score = 0.0
        if context_key:
            co_score = self._tracker.co_access_score(context_key, key) * 2.0
        freq_score = min(1.0, freq / 100.0) * 3.0
        return freq_score + recency_score + co_score


class LightweightPredictor:
    """Simple frequency + recency + co-access predictor."""

    def __init__(self, tracker: AccessPatternTracker) -> None:
        self._tracker = tracker
        self._extractor = FeatureExtractor(tracker)
        self._prediction_history: List[Dict[str, Any]] = []

    def predict(self, top_n: int = 10,
                context_key: Optional[str] = None) -> List[str]:
        with self._tracker._lock:
            all_keys = set(self._tracker._frequency.keys())
        scored = [(k, self._extractor.score(k, context_key)) for k in all_keys]
        scored.sort(key=lambda x: -x[1])
        predictions = [k for k, s in scored[:top_n] if s > 0]
        self._prediction_history.append({
            'context': context_key,
            'predictions': predictions,
            'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        })
        return predictions

    def predict_from_recent(self, top_n: int = 10) -> List[str]:
        recent = self._tracker.recent_keys(seconds=300)
        if not recent:
            return self.predict(top_n // 2)
        context_key = max(recent, key=lambda k: self._tracker.recency(k))
        return self.predict(top_n, context_key)

    def prediction_accuracy(self, actual_keys: Set[str],
                            predicted_keys: List[str]) -> float:
        if not predicted_keys:
            return 0.0
        hits = sum(1 for k in predicted_keys if k in actual_keys)
        return hits / len(predicted_keys)


class PredictiveCache:
    """Cache that pre-loads predicted records."""

    def __init__(self) -> None:
        self._cache: Dict[str, Any] = {}
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0
        self._pre_load_count = 0

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            if key in self._cache:
                self._hits += 1
                return self._cache[key]
            self._misses += 1
            return None

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._cache[key] = value

    def pre_load(self, keys: List[str],
                 loader: Callable[[str], Any]) -> int:
        loaded = 0
        for k in keys:
            if k not in self._cache:
                try:
                    self._cache[k] = loader(k)
                    loaded += 1
                except Exception:
                    pass
        with self._lock:
            self._pre_load_count += loaded
        return loaded

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()

    @property
    def hit_rate(self) -> float:
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._cache)

    def metrics(self) -> Dict[str, Any]:
        with self._lock:
            return {
                'size': len(self._cache),
                'hits': self._hits,
                'misses': self._misses,
                'hit_rate': round(self.hit_rate, 4),
                'pre_load_count': self._pre_load_count,
            }


class OnlineLearner:
    """Update prediction model online after each execution cycle."""

    def __init__(self, tracker: AccessPatternTracker) -> None:
        self._tracker = tracker
        self._cycles = 0

    def record_cycle(self, accessed_keys: List[str],
                     module: str = '') -> None:
        self._cycles += 1
        for key in accessed_keys:
            self._tracker.record(key, module)

    def cycle_count(self) -> int:
        return self._cycles


class PredictiveCacheEngine:
    """Top-level predictive state pre-loading engine."""

    def __init__(self) -> None:
        self._tracker = AccessPatternTracker()
        self._predictor = LightweightPredictor(self._tracker)
        self._cache = PredictiveCache()
        self._learner = OnlineLearner(self._tracker)

    @property
    def tracker(self) -> AccessPatternTracker:
        return self._tracker

    @property
    def predictor(self) -> LightweightPredictor:
        return self._predictor

    @property
    def cache(self) -> PredictiveCache:
        return self._cache

    def record_access(self, key: str, module: str = '',
                      access_type: str = 'read', elapsed_ms: float = 0.0) -> None:
        self._tracker.record(key, module, access_type, elapsed_ms)

    def predict_and_preload(self, loader: Callable[[str], Any],
                            top_n: int = 10,
                            context_key: Optional[str] = None) -> List[str]:
        predictions = self._predictor.predict(top_n, context_key)
        self._cache.pre_load(predictions, loader)
        return predictions

    def get(self, key: str, loader: Optional[Callable[[str], Any]] = None) -> Any:
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        if loader:
            value = loader(key)
            self._cache.set(key, value)
            return value
        return None

    def record_cycle(self, accessed_keys: List[str], module: str = '') -> None:
        self._learner.record_cycle(accessed_keys, module)

    def evaluate_accuracy(self, actual_keys: Set[str],
                          predicted_keys: List[str]) -> float:
        return self._predictor.prediction_accuracy(actual_keys, predicted_keys)

    def summary(self) -> Dict[str, Any]:
        return {
            'access_log_count': self._tracker.access_count(),
            'cache': self._cache.metrics(),
            'unique_keys_tracked': len(self._tracker._frequency),
            'learning_cycles': self._learner.cycle_count(),
        }

    def report_text(self) -> str:
        s = self.summary()
        c = s['cache']
        return (
            f'Predictive Cache Engine\n'
            f'  Access log: {s["access_log_count"]} records\n'
            f'  Unique keys: {s["unique_keys_tracked"]}\n'
            f'  Cache: {c["size"]} items, hit rate {c["hit_rate"]:.1%}\n'
            f'  Pre-loads: {c["pre_load_count"]}'
        )

    def export_artifacts(self, dir: str) -> List[str]:
        os.makedirs(dir, exist_ok=True)
        paths = []
        sp = os.path.join(dir, 'predictive_cache.json')
        with open(sp, 'w') as f:
            json.dump(self.summary(), f, indent=2)
        paths.append(sp)
        return paths
