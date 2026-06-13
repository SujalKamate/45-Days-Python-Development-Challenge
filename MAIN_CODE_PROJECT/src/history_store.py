"""LFU-aware history retention — frequently accessed records survive eviction."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple
import threading
import time


class LFUCache:
    """Frequency-counting cache that evicts least-frequently used entries first.

    Ties are broken by recency (most recently accessed survives).
    """

    def __init__(self, maxsize: int = 1000) -> None:
        self._maxsize = maxsize
        self._data: Dict[str, Any] = {}
        self._freq: Dict[str, int] = {}
        self._last_access: Dict[str, float] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            val = self._data.get(key)
            if val is not None:
                self._freq[key] = self._freq.get(key, 0) + 1
                self._last_access[key] = time.monotonic()
            return val

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            if key not in self._data and len(self._data) >= self._maxsize:
                self._evict()
            self._data[key] = value
            self._freq[key] = self._freq.get(key, 0) + 1
            self._last_access[key] = time.monotonic()

    def _evict(self) -> None:
        if not self._data:
            return
        min_freq = min(self._freq.values())
        candidates = [k for k, f in self._freq.items() if f == min_freq]
        if len(candidates) == 1:
            evict_key = candidates[0]
        else:
            evict_key = min(candidates, key=lambda k: self._last_access.get(k, 0))
        self._data.pop(evict_key, None)
        self._freq.pop(evict_key, None)
        self._last_access.pop(evict_key, None)

    def delete(self, key: str) -> bool:
        with self._lock:
            existed = key in self._data
            self._data.pop(key, None)
            self._freq.pop(key, None)
            self._last_access.pop(key, None)
            return existed

    def items(self) -> List[Tuple[str, Any]]:
        with self._lock:
            return list(self._data.items())

    def keys(self) -> List[str]:
        with self._lock:
            return list(self._data.keys())

    def values(self) -> List[Any]:
        with self._lock:
            return list(self._data.values())

    def frequencies(self) -> Dict[str, int]:
        with self._lock:
            return dict(self._freq)

    def resize(self, new_maxsize: int) -> int:
        with self._lock:
            self._maxsize = max(1, new_maxsize)
            evicted = 0
            while len(self._data) > self._maxsize:
                self._evict()
                evicted += 1
            return evicted

    def clear(self) -> None:
        with self._lock:
            self._data.clear()
            self._freq.clear()
            self._last_access.clear()

    @property
    def size(self) -> int:
        return len(self._data)

    @property
    def maxsize(self) -> int:
        return self._maxsize


class HistoryStore:
    """Drop-in replacement for List[str] history with LFU-aware retention."""

    def __init__(self, max_entries: int = 1000) -> None:
        self._entries: List[str] = []
        self._cache = LFUCache(max_entries)
        self._max_entries = max_entries
        self._lock = threading.Lock()

    def append(self, entry: str) -> None:
        with self._lock:
            self._entries.append(entry)
            self._cache.set(str(len(self._entries)), entry)
            if len(self._entries) > self._max_entries:
                self._trim()

    def _trim(self) -> None:
        over = len(self._entries) - self._max_entries
        if over <= 0:
            return
        freqs = self._cache.frequencies()
        scored = [(freqs.get(str(i + 1), 0), i, self._entries[i])
                  for i in range(len(self._entries))]
        scored.sort(key=lambda x: (x[0], -x[1]))
        keep_indices = set(range(len(self._entries)))
        for _ in range(over):
            if scored:
                _, idx, _ = scored.pop(0)
                keep_indices.discard(idx)
        self._entries = [self._entries[i] for i in sorted(keep_indices)]
        for i, entry in enumerate(self._entries):
            self._cache.set(str(i + 1), entry)

    def tail(self, count: int = 5) -> List[str]:
        with self._lock:
            return self._entries[-count:]

    def all(self) -> List[str]:
        with self._lock:
            return list(self._entries)

    def __len__(self) -> int:
        return len(self._entries)

    def __getitem__(self, idx: int) -> str:
        return self._entries[idx]

    def __iter__(self):
        return iter(self._entries)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
            self._cache.clear()
