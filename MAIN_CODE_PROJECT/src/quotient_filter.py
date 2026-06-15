"""Quotient filter approximate membership with fingerprint decomposition and cluster storage."""

from __future__ import annotations

from typing import Any, Dict, Hashable, List, Optional, Tuple
import hashlib
import json
import math
import struct
import threading
import time


def _qf_hash(item: Hashable) -> int:
    h = hashlib.sha256(str(item).encode('utf-8'))
    return struct.unpack('<Q', h.digest()[:8])[0]


class QuotientFilter:
    """Approximate membership filter using quotient/remainder decomposition.

    Each fingerprint is split into a *quotient* (bucket index) and *remainder*
    (stored value).  Slots carry 3 metadata bits: *occupied*, *continuation*,
    *shifted* — enabling cluster reconstruction without pointers.
    """

    def __init__(self, q: int = 14, r: int = 8) -> None:
        if q < 4 or q > 32:
            raise ValueError('q (quotient bits) must be between 4 and 32')
        if r < 4 or r > 32:
            raise ValueError('r (remainder bits) must be between 4 and 32')
        self.q: int = q
        self.r: int = r
        self.m: int = 1 << q
        self._fingerprint_mask: int = (1 << (q + r)) - 1
        self._remainder_mask: int = (1 << r) - 1
        self._occupied: List[bool] = [False] * self.m
        self._continuation: List[bool] = [False] * self.m
        self._shifted: List[bool] = [False] * self.m
        self._remainders: List[int] = [0] * self.m
        self._count: int = 0
        self._lock = threading.Lock()
        self._uid = f'qf:{id(self):x}'

    def _fingerprint(self, item: Hashable) -> int:
        return _qf_hash(item) & self._fingerprint_mask

    def _quotient(self, fp: int) -> int:
        return fp >> self.r

    def _remainder(self, fp: int) -> int:
        return fp & self._remainder_mask

    def _find_cluster_start(self, quotient: int) -> int:
        start = quotient
        while self._shifted[start]:
            start = (start - 1) % self.m
        return start

    def _find_run_end(self, start: int) -> int:
        end = start
        while self._continuation[end]:
            end = (end + 1) % self.m
        return end

    def _is_empty(self, idx: int) -> bool:
        return not (self._occupied[idx] or self._continuation[idx] or self._shifted[idx])

    def insert(self, item: Hashable) -> bool:
        fp = self._fingerprint(item)
        quot = self._quotient(fp)
        rem = self._remainder(fp)
        with self._lock:
            self._occupied[quot] = True
            cluster_start = self._find_cluster_start(quot)
            run_end = self._find_run_end(cluster_start)
            insert_at = cluster_start
            found = False
            for i in range(cluster_start, run_end + 1):
                idx = i % self.m
                if not self._continuation[idx] and not self._shifted[idx]:
                    break
                if not self._shifted[idx] and not found:
                    si = cluster_start
                    while si != idx:
                        if not self._shifted[si]:
                            si = (si + 1) % self.m
                        else:
                            break
                    if self._remainders[si] >= rem and not found:
                        insert_at = si
                        found = True
                        break
            if not found:
                insert_at = (run_end + 1) % self.m
            if insert_at != quot:
                self._shifted[insert_at] = True
            if insert_at <= run_end and insert_at >= cluster_start:
                self._shift_elements_right(insert_at, run_end)
            self._remainders[insert_at] = rem
            if insert_at != cluster_start:
                self._continuation[insert_at] = True
            self._count += 1
            return True

    def _shift_elements_right(self, start: int, end: int) -> None:
        i = end
        while i >= start:
            src = i % self.m
            dst = (i + 1) % self.m
            self._remainders[dst] = self._remainders[src]
            self._continuation[dst] = self._continuation[src]
            self._shifted[dst] = True
            i -= 1

    def contains(self, item: Hashable) -> bool:
        fp = self._fingerprint(item)
        quot = self._quotient(fp)
        rem = self._remainder(fp)
        with self._lock:
            if not self._occupied[quot]:
                return False
            cluster_start = self._find_cluster_start(quot)
            run_end = self._find_run_end(cluster_start)
            for i in range(cluster_start, run_end + 1):
                idx = i % self.m
                if self._remainders[idx] == rem and not self._is_empty(idx):
                    if i == quot or self._shifted[idx]:
                        return True
            return False

    def delete(self, item: Hashable) -> bool:
        fp = self._fingerprint(item)
        quot = self._quotient(fp)
        rem = self._remainder(fp)
        with self._lock:
            if not self._occupied[quot]:
                return False
            cluster_start = self._find_cluster_start(quot)
            run_end = self._find_run_end(cluster_start)
            delete_idx = -1
            for i in range(cluster_start, run_end + 1):
                idx = i % self.m
                if self._remainders[idx] == rem and not self._is_empty(idx):
                    if i == quot or self._shifted[idx]:
                        delete_idx = idx
                        break
            if delete_idx == -1:
                return False
            self._shift_elements_left(delete_idx, run_end)
            self._count -= 1
            return True

    def _shift_elements_left(self, start: int, end: int) -> None:
        for i in range(start, end):
            src = (i + 1) % self.m
            dst = i % self.m
            self._remainders[dst] = self._remainders[src]
            self._continuation[dst] = self._continuation[src]
            self._shifted[dst] = self._shifted[src]
        self._remainders[end % self.m] = 0
        self._continuation[end % self.m] = False
        self._shifted[end % self.m] = False

    def merge(self, other: QuotientFilter) -> None:
        if self.q != other.q or self.r != other.r:
            raise ValueError('Quotient and remainder bits must match for merge')
        with self._lock, other._lock:
            for i in range(self.m):
                if other._occupied[i]:
                    self._occupied[i] = True
                if not self._is_empty(i) and not other._is_empty(i):
                    self._remainders[i] = min(self._remainders[i], other._remainders[i])
                elif other._is_empty(i) and not self._is_empty(i):
                    pass
                elif not other._is_empty(i):
                    self._remainders[i] = other._remainders[i]
                    self._continuation[i] = other._continuation[i]
                    self._shifted[i] = other._shifted[i]
            self._count = max(self._count, other._count)

    def intersection_estimate(self, other: QuotientFilter) -> float:
        if self.q != other.q or self.r != other.r:
            raise ValueError('Filters must have same q/r for intersection estimate')
        with self._lock, other._lock:
            matches = 0
            non_zero = 0
            for i in range(self.m):
                if not self._is_empty(i) and not other._is_empty(i):
                    non_zero += 1
                    if self._remainders[i] == other._remainders[i]:
                        matches += 1
                elif not self._is_empty(i) or not other._is_empty(i):
                    non_zero += 1
            return matches / non_zero if non_zero else 0.0

    def size_in_bytes(self) -> int:
        bits = self.m * (self.r + 3)
        return (bits + 7) >> 3

    def load_factor(self) -> float:
        return self._count / self.m if self.m else 0.0

    def count(self) -> int:
        return self._count

    def clear(self) -> None:
        with self._lock:
            self._occupied = [False] * self.m
            self._continuation = [False] * self.m
            self._shifted = [False] * self.m
            self._remainders = [0] * self.m
            self._count = 0

    def resize(self, new_q: int) -> None:
        if new_q <= self.q:
            raise ValueError('new_q must be larger than current q')
        old = self.copy()
        self.q = new_q
        self.m = 1 << new_q
        self._fingerprint_mask = (1 << (new_q + self.r)) - 1
        self._occupied = [False] * self.m
        self._continuation = [False] * self.m
        self._shifted = [False] * self.m
        self._remainders = [0] * self.m
        self._count = 0
        for i in range(old.m):
            if not old._is_empty(i):
                fp = (i << self.r) | old._remainders[i]
                quot = fp >> self.r
                rem = fp & self._remainder_mask
                self._occupied[quot] = True
                cluster_start = self._find_cluster_start(quot)
                run_end = self._find_run_end(cluster_start)
                insert_at = (run_end + 1) % self.m
                if insert_at != quot:
                    self._shifted[insert_at] = True
                if insert_at != cluster_start:
                    self._continuation[insert_at] = True
                self._remainders[insert_at] = rem
                self._count += 1

    def copy(self) -> QuotientFilter:
        qf = QuotientFilter(self.q, self.r)
        qf._occupied = list(self._occupied)
        qf._continuation = list(self._continuation)
        qf._shifted = list(self._shifted)
        qf._remainders = list(self._remainders)
        qf._count = self._count
        return qf

    def to_dict(self) -> Dict[str, Any]:
        with self._lock:
            return {
                'q': self.q, 'r': self.r, 'm': self.m,
                'count': self._count,
                'occupied': [int(b) for b in self._occupied],
                'continuation': [int(b) for b in self._continuation],
                'shifted': [int(b) for b in self._shifted],
                'remainders': list(self._remainders),
            }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> QuotientFilter:
        qf = QuotientFilter(data['q'], data['r'])
        qf._count = data.get('count', 0)
        occ = data.get('occupied', [])
        con = data.get('continuation', [])
        shf = data.get('shifted', [])
        rem = data.get('remainders', [])
        if occ:
            qf._occupied = [bool(b) for b in occ]
        if con:
            qf._continuation = [bool(b) for b in con]
        if shf:
            qf._shifted = [bool(b) for b in shf]
        if rem:
            qf._remainders = list(rem)
        return qf


class QuotientFilterEngine:
    """Top-level engine managing multiple quotient filters."""

    def __init__(self) -> None:
        self._filters: Dict[str, QuotientFilter] = {}
        self._default_filter: Optional[QuotientFilter] = None
        self._lock = threading.Lock()

    def create(self, name: str = 'default', q: int = 14, r: int = 8) -> QuotientFilter:
        qf = QuotientFilter(q, r)
        with self._lock:
            self._filters[name] = qf
            if name == 'default':
                self._default_filter = qf
        return qf

    def get(self, name: str = 'default') -> QuotientFilter:
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

    def merge(self, dst: str, src: str) -> bool:
        with self._lock:
            if dst not in self._filters or src not in self._filters:
                return False
            self._filters[dst].merge(self._filters[src])
            return True

    def intersection_estimate(self, name_a: str, name_b: str) -> Optional[float]:
        with self._lock:
            if name_a not in self._filters or name_b not in self._filters:
                return None
            return self._filters[name_a].intersection_estimate(self._filters[name_b])

    def load_factor(self, name: str = 'default') -> float:
        return self.get(name).load_factor()

    def size_in_bytes(self, name: str = 'default') -> int:
        return self.get(name).size_in_bytes()

    def count(self, name: str = 'default') -> int:
        return self.get(name).count()

    def clear(self, name: str = 'default') -> None:
        self.get(name).clear()

    def clear_all(self) -> None:
        with self._lock:
            for qf in self._filters.values():
                qf.clear()

    def resize(self, new_q: int, name: str = 'default') -> None:
        self.get(name).resize(new_q)

    def summary(self) -> Dict[str, Any]:
        with self._lock:
            return {
                'filter_count': len(self._filters),
                'filter_names': list(self._filters.keys()),
            }
