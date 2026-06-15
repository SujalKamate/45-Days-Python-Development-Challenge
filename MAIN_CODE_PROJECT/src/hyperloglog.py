"""HyperLogLog++ cardinality estimation with sparse registers and bias correction."""

from __future__ import annotations

from typing import Any, Dict, Hashable, List, Optional, Set, Tuple
import hashlib
import json
import math
import struct
import threading
import time


_POW2_32 = 2.0 ** 32
_POW2_64 = 2.0 ** 64
_HLL_BIAS: Optional[List[float]] = None
_HLL_BIAS_VECS: Optional[List[List[float]]] = None


def _init_bias() -> None:
    global _HLL_BIAS, _HLL_BIAS_VECS
    if _HLL_BIAS is not None:
        return
    _HLL_BIAS_VECS = [
        [10.0, 10.0, 10.0, 10.0, 10.0, 9.9, 9.8, 9.7, 9.5, 9.1,
         8.6, 8.1, 7.5, 6.8, 6.1, 5.4, 4.7, 4.1, 3.5, 3.0,
         2.5, 2.1, 1.7, 1.4, 1.1, 0.9, 0.7, 0.5, 0.3, 0.1],
        [5.0, 5.0, 5.0, 5.0, 5.0, 4.9, 4.8, 4.7, 4.5, 4.2,
         3.9, 3.5, 3.1, 2.7, 2.3, 1.9, 1.6, 1.3, 1.0, 0.8,
         0.6, 0.5, 0.3, 0.2, 0.1, 0.1, 0.0, 0.0, 0.0, 0.0],
        [2.5, 2.5, 2.5, 2.5, 2.5, 2.4, 2.3, 2.2, 2.0, 1.8,
         1.6, 1.4, 1.2, 1.0, 0.8, 0.6, 0.5, 0.4, 0.3, 0.2,
         0.1, 0.1, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    ]
    _HLL_BIAS = [
        0.0, 0.0, 0.0, 0.0, 0.0, 0.1, 0.2, 0.3, 0.5, 0.9,
        1.4, 1.9, 2.5, 3.2, 3.9, 4.6, 5.3, 5.9, 6.5, 7.0,
        7.5, 7.9, 8.3, 8.6, 8.9, 9.1, 9.3, 9.5, 9.7, 9.9,
    ]


def _hll_hash(item: Hashable) -> int:
    h = hashlib.sha256(str(item).encode('utf-8'))
    return struct.unpack('<Q', h.digest()[:8])[0]


def _leading_zeros(x: int, bits: int = 64) -> int:
    if x == 0:
        return bits
    return x.bit_length() ^ (bits - 1) if x.bit_length() < bits else 0


def _rho(hash_val: int, p: int) -> Tuple[int, int]:
    idx = hash_val >> (64 - p)
    remaining = hash_val << p
    lz = _leading_zeros(remaining, 64) + 1
    return idx, lz


def _alpha(p: int) -> float:
    if p == 4:
        return 0.673
    if p == 5:
        return 0.697
    if p == 6:
        return 0.709
    return 0.7213 / (1.0 + 1.079 / (1 << p))


_SPARSE_THRESHOLD_FACTOR = 0.6
_LINEAR_COUNT_THRESHOLD = 5.0


class HyperLogLog:
    """HyperLogLog++ cardinality estimator with sparse/dense storage."""

    def __init__(self, p: int = 14, sparse: bool = True) -> None:
        if p < 4 or p > 18:
            raise ValueError('Precision p must be between 4 and 18')
        self.p: int = p
        self.m: int = 1 << p
        self._alpha = _alpha(p)
        self._sparse_enabled = sparse
        self._sparse_max = int(self.m * _SPARSE_THRESHOLD_FACTOR) if sparse else 0
        self._sparse: Dict[int, int] = {} if sparse else None
        self._registers: Optional[bytearray] = None
        self._lock = threading.Lock()
        self._uid = f'hll:{id(self):x}'
        _init_bias()

    def add(self, item: Hashable) -> None:
        h = _hll_hash(item)
        idx, lz = _rho(h, self.p)
        with self._lock:
            if self._registers is not None:
                self._update_dense(idx, lz)
            elif self._sparse_enabled:
                self._update_sparse(idx, lz)
            else:
                self._ensure_dense()
                self._update_dense(idx, lz)

    def _update_sparse(self, idx: int, lz: int) -> None:
        existing = self._sparse.get(idx, 0)
        if lz > existing:
            self._sparse[idx] = lz
        if len(self._sparse) > self._sparse_max:
            self._convert_to_dense()

    def _update_dense(self, idx: int, lz: int) -> None:
        existing = self._get_register(idx)
        if lz > existing:
            self._set_register(idx, lz)

    def _get_register(self, idx: int) -> int:
        pos = idx >> 1
        if idx & 1:
            return (self._registers[pos] >> 4) & 0x3F
        return self._registers[pos] & 0x3F

    def _set_register(self, idx: int, val: int) -> None:
        pos = idx >> 1
        if idx & 1:
            self._registers[pos] = (self._registers[pos] & 0x0F) | (val << 4)
        else:
            self._registers[pos] = (self._registers[pos] & 0xF0) | val

    def _ensure_dense(self) -> None:
        if self._registers is not None:
            return
        self._registers = bytearray((self.m + 1) >> 1)
        if self._sparse:
            for idx, val in self._sparse.items():
                self._update_dense(idx, val)
            self._sparse = None

    def _convert_to_dense(self) -> None:
        self._ensure_dense()

    def estimate(self) -> float:
        with self._lock:
            if self._registers is not None:
                return self._estimate_dense()
            return self._estimate_sparse()

    def _estimate_sparse(self) -> float:
        return float(len(self._sparse))

    def _estimate_dense(self) -> float:
        raw = self._raw_estimate()
        if raw <= self.m * _LINEAR_COUNT_THRESHOLD:
            zero_count = self._count_zero_registers()
            if zero_count > 0:
                linear = self.m * math.log(self.m / max(zero_count, 1))
                return linear
        corrected = self._bias_correct(raw)
        if corrected > _POW2_32 / 30.0:
            return -_POW2_32 * math.log(1.0 - corrected / _POW2_32)
        return corrected

    def _raw_estimate(self) -> float:
        if self._registers is None:
            return 0.0
        inv_sum = 0.0
        for i in range(self.m):
            val = self._get_register(i)
            inv_sum += 1.0 / (1 << val)
        return self._alpha * self.m * self.m / inv_sum

    def _count_zero_registers(self) -> int:
        if self._registers is None:
            return self.m
        count = 0
        for i in range(self.m):
            if self._get_register(i) == 0:
                count += 1
        return count

    def _bias_correct(self, raw: float) -> float:
        if self.p < 4 or self.p > 14:
            return raw
        idx = int(raw / (self.m * 0.5))
        if idx < 0:
            return raw
        bias_table = _HLL_BIAS_VECS[0] if self.p < 7 else \
                     (_HLL_BIAS_VECS[1] if self.p < 10 else _HLL_BIAS_VECS[2])
        if idx >= len(bias_table):
            return raw
        return raw - bias_table[idx] * self.m

    def merge(self, other: HyperLogLog) -> None:
        if self.p != other.p:
            raise ValueError('Precision must match for merge')
        other._ensure_dense()
        self._ensure_dense()
        with self._lock, other._lock:
            for i in range(self.m):
                ov = other._get_register(i)
                sv = self._get_register(i)
                if ov > sv:
                    self._set_register(i, ov)

    def register_count(self) -> int:
        return self.m

    def copy(self) -> HyperLogLog:
        hll = HyperLogLog(self.p, sparse=False)
        self._ensure_dense()
        hll._registers = bytearray(self._registers)
        return hll

    def clear(self) -> None:
        with self._lock:
            if self._sparse is not None:
                self._sparse.clear()
            if self._registers is not None:
                self._registers = bytearray((self.m + 1) >> 1)

    def to_dict(self) -> Dict[str, Any]:
        with self._lock:
            self._ensure_dense()
            return {
                'p': self.p,
                'm': self.m,
                'registers': list(self._registers),
            }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> HyperLogLog:
        hll = HyperLogLog(data['p'], sparse=False)
        hll._registers = bytearray(data['registers'])
        return hll


class HyperLogLogPlusPlus:
    """Enhanced HLL++ with bias correction, sparse optimization, and linear counting."""

    def __init__(self, p: int = 14) -> None:
        self._hll = HyperLogLog(p, sparse=True)
        self._uid = f'hllpp:{id(self):x}'

    @property
    def p(self) -> int:
        return self._hll.p

    def add(self, item: Hashable) -> None:
        self._hll.add(item)

    def estimate(self) -> float:
        return self._hll.estimate()

    def merge(self, other: HyperLogLogPlusPlus) -> None:
        self._hll.merge(other._hll)

    def register_count(self) -> int:
        return self._hll.register_count()

    def copy(self) -> HyperLogLogPlusPlus:
        pp = HyperLogLogPlusPlus(self._hll.p)
        pp._hll = self._hll.copy()
        return pp

    def clear(self) -> None:
        self._hll.clear()

    def to_dict(self) -> Dict[str, Any]:
        return self._hll.to_dict()

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> HyperLogLogPlusPlus:
        hll = HyperLogLog.from_dict(data)
        pp = HyperLogLogPlusPlus(hll.p)
        pp._hll = hll
        return pp


class HLLHistorian:
    """Snapshot history for HLL estimators."""

    def __init__(self, max_snapshots: int = 100) -> None:
        self.max_snapshots = max_snapshots
        self._snapshots: List[Dict[str, Any]] = []
        self._lock = threading.Lock()

    def snapshot(self, estimator: HyperLogLogPlusPlus) -> int:
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


class HyperLogLogEngine:
    """Top-level engine managing multiple HLL++ estimators."""

    def __init__(self) -> None:
        self._estimators: Dict[str, HyperLogLogPlusPlus] = {}
        self._default_est: Optional[HyperLogLogPlusPlus] = None
        self._historian = HLLHistorian()
        self._lock = threading.Lock()

    def create(self, name: str = 'default', p: int = 14) -> HyperLogLogPlusPlus:
        est = HyperLogLogPlusPlus(p)
        with self._lock:
            self._estimators[name] = est
            if name == 'default':
                self._default_est = est
        return est

    def get(self, name: str = 'default') -> HyperLogLogPlusPlus:
        with self._lock:
            if name in self._estimators:
                return self._estimators[name]
            if self._default_est is None:
                self._default_est = self.create()
            return self._default_est

    def remove(self, name: str) -> bool:
        with self._lock:
            if name in self._estimators:
                del self._estimators[name]
                if name == 'default':
                    self._default_est = None
                return True
            return False

    def list(self) -> List[str]:
        with self._lock:
            return list(self._estimators.keys())

    def add(self, item: Hashable, name: str = 'default') -> None:
        self.get(name).add(item)

    def add_batch(self, items: List[Hashable], name: str = 'default') -> None:
        est = self.get(name)
        for item in items:
            est.add(item)

    def estimate(self, name: str = 'default') -> float:
        return self.get(name).estimate()

    def merge(self, dst: str, src: str) -> bool:
        with self._lock:
            if dst not in self._estimators or src not in self._estimators:
                return False
            self._estimators[dst].merge(self._estimators[src])
            return True

    def register_count(self, name: str = 'default') -> int:
        return self.get(name).register_count()

    def clear(self, name: str = 'default') -> None:
        self.get(name).clear()

    def clear_all(self) -> None:
        with self._lock:
            for est in self._estimators.values():
                est.clear()

    def snapshot(self, name: str = 'default') -> int:
        return self._historian.snapshot(self.get(name))

    def history(self, n: int = 10) -> List[Dict[str, Any]]:
        return self._historian.history(n)

    def summary(self) -> Dict[str, Any]:
        with self._lock:
            return {
                'estimator_count': len(self._estimators),
                'estimator_names': list(self._estimators.keys()),
                'historian_snapshots': len(self._historian._snapshots),
            }
