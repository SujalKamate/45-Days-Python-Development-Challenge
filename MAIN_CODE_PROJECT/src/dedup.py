"""Incremental deduplication — fingerprint-based duplicate detection to skip reprocessing."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Set, Tuple
import hashlib
import json
import threading
import time


class BloomFilter:
    """Space-efficient probabilistic membership test with configurable false-positive rate."""

    def __init__(self, capacity: int = 100000, error_rate: float = 0.01) -> None:
        import math
        self._capacity = capacity
        self._error_rate = error_rate
        self._bit_count = int(-capacity * math.log(error_rate) / (math.log(2) ** 2))
        self._hash_count = max(1, int(self._bit_count / capacity * math.log(2)))
        self._bits = bytearray((self._bit_count + 7) // 8)
        self._inserted = 0
        self._lock = threading.Lock()

    def _hashes(self, item: str) -> List[int]:
        h = hashlib.sha256(item.encode('utf-8')).digest()
        return [int.from_bytes(h[i:i+4], 'little') % self._bit_count
                for i in range(0, min(len(h), self._hash_count * 4), 4)]

    def add(self, item: str) -> None:
        with self._lock:
            for pos in self._hashes(item):
                byte_idx = pos // 8
                bit_idx = pos % 8
                self._bits[byte_idx] |= 1 << bit_idx
            self._inserted += 1

    def contains(self, item: str) -> bool:
        for pos in self._hashes(item):
            byte_idx = pos // 8
            bit_idx = pos % 8
            if not (self._bits[byte_idx] & (1 << bit_idx)):
                return False
        return True


class Fingerprint:
    """Canonical fingerprint for a data record using SHA-256 of sorted JSON."""

    @staticmethod
    def compute(record: Any) -> str:
        canonical = json.dumps(record, sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


class DedupTracker:
    """Tracks processed records using fingerprints for incremental deduplication.

    Combines a Bloom filter (fast check) with an exact set (for confirmation
    and persistence). Records are skipped if already seen.
    """

    def __init__(self, bloom_capacity: int = 100000) -> None:
        self._bloom = BloomFilter(bloom_capacity)
        self._exact: Set[str] = set()
        self._lock = threading.Lock()
        self._skipped = 0
        self._processed = 0

    def is_duplicate(self, record: Any) -> bool:
        fp = Fingerprint.compute(record)
        if self._bloom.contains(fp):
            with self._lock:
                if fp in self._exact:
                    self._skipped += 1
                    return True
        return False

    def mark_processed(self, record: Any) -> None:
        fp = Fingerprint.compute(record)
        self._bloom.add(fp)
        with self._lock:
            self._exact.add(fp)
            self._processed += 1

    def filter(self, records: List[Any]) -> Tuple[List[Any], List[Any]]:
        new_records: List[Any] = []
        dups: List[Any] = []
        for r in records:
            if self.is_duplicate(r):
                dups.append(r)
            else:
                new_records.append(r)
        for r in new_records:
            self.mark_processed(r)
        return new_records, dups

    def export(self) -> Dict[str, Any]:
        with self._lock:
            return {
                'fingerprints': sorted(self._exact),
                'processed': self._processed,
                'skipped': self._skipped,
            }

    def load(self, data: Dict[str, Any]) -> None:
        fps = set(data.get('fingerprints', []))
        with self._lock:
            self._exact = fps
            for fp in fps:
                self._bloom.add(fp)
            self._processed = data.get('processed', len(fps))
            self._skipped = data.get('skipped', 0)

    def reset(self) -> None:
        with self._lock:
            self._exact.clear()
            self._bloom = BloomFilter()
            self._processed = 0
            self._skipped = 0

    @property
    def stats(self) -> Dict[str, int]:
        return {'processed': self._processed, 'skipped': self._skipped}


class ContentAddressedStore:
    """Deduplicated store that skips writes for unchanged content."""

    def __init__(self) -> None:
        self._fingerprints: Dict[str, str] = {}
        self._lock = threading.Lock()

    def put(self, key: str, value: Any) -> bool:
        fp = Fingerprint.compute(value)
        with self._lock:
            if self._fingerprints.get(key) == fp:
                return False
            self._fingerprints[key] = fp
            return True

    def has_changed(self, key: str, value: Any) -> bool:
        fp = Fingerprint.compute(value)
        with self._lock:
            return self._fingerprints.get(key) != fp
