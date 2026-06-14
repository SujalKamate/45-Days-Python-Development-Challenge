"""Cuckoo filter membership verification with deletion and high load efficiency."""

from __future__ import annotations

from typing import Any, Dict, Hashable, List, Optional, Tuple
import hashlib
import json
import math
import random
import struct
import threading
import time


_FINGERPRINT_MASK: Dict[int, int] = {}


def _fp_mask(bits: int) -> int:
    if bits not in _FINGERPRINT_MASK:
        _FINGERPRINT_MASK[bits] = (1 << bits) - 1
    return _FINGERPRINT_MASK[bits]


def _fingerprint(item: Hashable, bits: int) -> int:
    h = hashlib.sha256(str(item).encode('utf-8'))
    return struct.unpack('<I', h.digest()[:4])[0] & _fp_mask(bits)


def _hash_index(item: Hashable, seed: int, num_buckets: int) -> int:
    h = hashlib.sha256(f'{seed}:{item}'.encode('utf-8'))
    return struct.unpack('<I', h.digest()[:4])[0] % num_buckets


def _alt_index(idx: int, fp: int, num_buckets: int) -> int:
    return (idx ^ _hash_index(fp, 0x5bd1e995, num_buckets)) % num_buckets


class CuckooBucket:
    """A single bucket holding up to *capacity* fingerprints."""

    def __init__(self, capacity: int) -> None:
        self.capacity = capacity
        self._slots: List[int] = [0] * capacity
        self._count: int = 0

    def insert(self, fp: int) -> bool:
        if self._count >= self.capacity:
            return False
        for i in range(self.capacity):
            if self._slots[i] == 0:
                self._slots[i] = fp
                self._count += 1
                return True
        return False

    def contains(self, fp: int) -> bool:
        for i in range(self.capacity):
            if self._slots[i] == fp:
                return True
        return False

    def delete(self, fp: int) -> bool:
        for i in range(self.capacity):
            if self._slots[i] == fp:
                self._slots[i] = 0
                self._count -= 1
                return True
        return False

    def evict_one(self) -> int:
        idx = random.randint(0, self.capacity - 1)
        fp = self._slots[idx]
        self._slots[idx] = 0
        self._count -= 1
        return fp

    def load(self) -> float:
        return self._count / self.capacity if self.capacity else 0.0

    def is_full(self) -> bool:
        return self._count >= self.capacity

    def copy(self) -> CuckooBucket:
        b = CuckooBucket(self.capacity)
        b._slots = list(self._slots)
        b._count = self._count
        return b

    def to_dict(self) -> Dict[str, Any]:
        return {
            'capacity': self.capacity,
            'count': self._count,
            'slots': list(self._slots),
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> CuckooBucket:
        b = CuckooBucket(data['capacity'])
        b._count = data['count']
        b._slots = list(data['slots'])
        return b


class CuckooFilter:
    """Compact approximate membership filter with insertion, lookup, deletion.

    Uses cuckoo hashing with two candidate buckets per fingerprint and
    relocation-based insertion up to *max_relocations* kicks.
    """

    def __init__(self, capacity: int = 100000, fingerprint_bits: int = 8,
                 bucket_capacity: int = 4, max_relocations: int = 500) -> None:
        if fingerprint_bits < 4 or fingerprint_bits > 32:
            raise ValueError('fingerprint_bits must be between 4 and 32')
        num_buckets = _next_pow2(capacity // bucket_capacity * 2)
        self.num_buckets: int = num_buckets
        self.fingerprint_bits: int = fingerprint_bits
        self.bucket_capacity: int = bucket_capacity
        self.max_relocations: int = max_relocations
        self._buckets: List[CuckooBucket] = [CuckooBucket(bucket_capacity)
                                              for _ in range(num_buckets)]
        self._count: int = 0
        self._lock = threading.Lock()
        self._uid = f'cf:{id(self):x}'

    def _bucket_a(self, item: Hashable) -> int:
        return _hash_index(item, 0x9747b28c, self.num_buckets)

    def _bucket_b(self, fp: int, idx_a: int) -> int:
        return _alt_index(idx_a, fp, self.num_buckets)

    def insert(self, item: Hashable) -> bool:
        fp = _fingerprint(item, self.fingerprint_bits)
        if fp == 0:
            fp = 1
        with self._lock:
            i1 = self._bucket_a(item)
            i2 = self._bucket_b(fp, i1)
            if self._buckets[i1].insert(fp):
                self._count += 1
                return True
            if self._buckets[i2].insert(fp):
                self._count += 1
                return True
            cur = i1 if random.randint(0, 1) == 0 else i2
            for _ in range(self.max_relocations):
                evicted = self._buckets[cur].evict_one()
                cur = _alt_index(cur, evicted, self.num_buckets)
                if self._buckets[cur].insert(evicted):
                    self._buckets[cur].insert(fp)
                    self._count += 1
                    return True
                cur = _alt_index(cur, fp, self.num_buckets)
            return False

    def contains(self, item: Hashable) -> bool:
        fp = _fingerprint(item, self.fingerprint_bits)
        if fp == 0:
            fp = 1
        with self._lock:
            i1 = self._bucket_a(item)
            if self._buckets[i1].contains(fp):
                return True
            i2 = self._bucket_b(fp, i1)
            return self._buckets[i2].contains(fp)

    def delete(self, item: Hashable) -> bool:
        fp = _fingerprint(item, self.fingerprint_bits)
        if fp == 0:
            fp = 1
        with self._lock:
            i1 = self._bucket_a(item)
            if self._buckets[i1].delete(fp):
                self._count -= 1
                return True
            i2 = self._bucket_b(fp, i1)
            if self._buckets[i2].delete(fp):
                self._count -= 1
                return True
            return False

    def load_factor(self) -> float:
        total_slots = self.num_buckets * self.bucket_capacity
        if total_slots == 0:
            return 0.0
        return self._count / total_slots

    def count(self) -> int:
        return self._count

    def clear(self) -> None:
        with self._lock:
            self._buckets = [CuckooBucket(self.bucket_capacity)
                             for _ in range(self.num_buckets)]
            self._count = 0

    def copy(self) -> CuckooFilter:
        cf = CuckooFilter(0, self.fingerprint_bits,
                          self.bucket_capacity, self.max_relocations)
        cf.num_buckets = self.num_buckets
        cf._buckets = [b.copy() for b in self._buckets]
        cf._count = self._count
        return cf

    def to_dict(self) -> Dict[str, Any]:
        with self._lock:
            return {
                'num_buckets': self.num_buckets,
                'fingerprint_bits': self.fingerprint_bits,
                'bucket_capacity': self.bucket_capacity,
                'max_relocations': self.max_relocations,
                'count': self._count,
                'buckets': [b.to_dict() for b in self._buckets],
            }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> CuckooFilter:
        cf = CuckooFilter(0, data['fingerprint_bits'],
                          data['bucket_capacity'], data['max_relocations'])
        cf.num_buckets = data['num_buckets']
        cf._count = data.get('count', 0)
        cf._buckets = [CuckooBucket.from_dict(b) for b in data.get('buckets', [])]
        return cf


def _next_pow2(x: int) -> int:
    if x <= 0:
        return 1
    return 1 << (x - 1).bit_length()


class CuckooFilterEngine:
    """Top-level engine managing multiple cuckoo filters."""

    def __init__(self) -> None:
        self._filters: Dict[str, CuckooFilter] = {}
        self._default_filter: Optional[CuckooFilter] = None
        self._lock = threading.Lock()

    def create(self, name: str = 'default', capacity: int = 100000,
               fingerprint_bits: int = 8, bucket_capacity: int = 4,
               max_relocations: int = 500) -> CuckooFilter:
        cf = CuckooFilter(capacity, fingerprint_bits, bucket_capacity, max_relocations)
        with self._lock:
            self._filters[name] = cf
            if name == 'default':
                self._default_filter = cf
        return cf

    def get(self, name: str = 'default') -> CuckooFilter:
        with self._lock:
            if name in self._filters:
                return self._filters[name]
            if self._default_filter is None:
                self._default_filter = self.create()
            return self._default_filter

    def remove(self, name: str) -> bool:
        with self._lock:
            if name in self._filters:
                del self._filters[name]
                if name == 'default':
                    self._default_filter = None
                return True
            return False

    def list(self) -> List[str]:
        with self._lock:
            return list(self._filters.keys())

    def insert(self, item: Hashable, name: str = 'default') -> bool:
        return self.get(name).insert(item)

    def contains(self, item: Hashable, name: str = 'default') -> bool:
        return self.get(name).contains(item)

    def delete(self, item: Hashable, name: str = 'default') -> bool:
        return self.get(name).delete(item)

    def load_factor(self, name: str = 'default') -> float:
        return self.get(name).load_factor()

    def count(self, name: str = 'default') -> int:
        return self.get(name).count()

    def clear(self, name: str = 'default') -> None:
        self.get(name).clear()

    def clear_all(self) -> None:
        with self._lock:
            for cf in self._filters.values():
                cf.clear()

    def summary(self) -> Dict[str, Any]:
        with self._lock:
            return {
                'filter_count': len(self._filters),
                'filter_names': list(self._filters.keys()),
            }
