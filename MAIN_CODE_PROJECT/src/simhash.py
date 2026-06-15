"""Simhash near-duplicate detection and similarity-preserving document fingerprinting."""

from __future__ import annotations

from typing import Any, Dict, Hashable, List, Optional, Set, Tuple
import hashlib
import json
import math
import struct
import threading
import time


_SIMHASH_BITS = 64


def _sha64(text: str) -> int:
    h = hashlib.sha256(text.encode('utf-8'))
    return struct.unpack('<Q', h.digest()[:8])[0]


def _popcount(x: int) -> int:
    return x.bit_count()


def _tokenize(text: str) -> List[str]:
    cleaned = ''.join(ch.lower() if ch.isalnum() or ch.isspace() else ' ' for ch in text)
    return [t for t in cleaned.split() if t]


class Simhash:
    """64-bit similarity-preserving fingerprint with weighted feature extraction."""

    def __init__(self, value: int = 0) -> None:
        self.value: int = value & ((1 << _SIMHASH_BITS) - 1)

    @staticmethod
    def fingerprint(text: str, weights: Optional[Dict[str, float]] = None) -> Simhash:
        tokens = _tokenize(text)
        if not tokens:
            return Simhash(0)
        v = [0] * _SIMHASH_BITS
        seen: Dict[str, float] = {}
        for token in tokens:
            w = weights.get(token, 1.0) if weights else 1.0
            seen[token] = seen.get(token, 0.0) + w
        for token, w in seen.items():
            h = _sha64(token)
            for i in range(_SIMHASH_BITS):
                if h & (1 << i):
                    v[i] += w
                else:
                    v[i] -= w
        value = 0
        for i in range(_SIMHASH_BITS):
            if v[i] > 0:
                value |= 1 << i
        return Simhash(value)

    @staticmethod
    def from_bytes(data: bytes) -> Simhash:
        return Simhash(struct.unpack('<Q', data[:8])[0])

    def to_bytes(self) -> bytes:
        return struct.pack('<Q', self.value)

    @staticmethod
    def hamming_distance(a: Simhash, b: Simhash) -> int:
        return _popcount(a.value ^ b.value)

    def distance_to(self, other: Simhash) -> int:
        return _popcount(self.value ^ other.value)

    def similarity(self, other: Simhash) -> float:
        d = self.distance_to(other)
        return 1.0 - d / _SIMHASH_BITS

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Simhash):
            return NotImplemented
        return self.value == other.value

    def __hash__(self) -> int:
        return hash(self.value)

    def __repr__(self) -> str:
        return f'Simhash(0x{self.value:016x})'

    def to_dict(self) -> Dict[str, Any]:
        return {'value': self.value}

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> Simhash:
        return Simhash(data.get('value', 0))


class SimhashIndex:
    """Block-based index for efficient near-duplicate candidate retrieval.

    Splits the 64-bit fingerprint into *blocks* and stores each block
    as a key in a hash table.  Candidates share at least one block
    with the query fingerprint.
    """

    def __init__(self, blocks: int = 4) -> None:
        if blocks < 1 or blocks > 8:
            raise ValueError('blocks must be between 1 and 8')
        self.blocks = blocks
        self._block_width = _SIMHASH_BITS // blocks
        self._index: Dict[int, List[str]] = {}
        self._fingerprints: Dict[str, Simhash] = {}
        self._lock = threading.Lock()
        self._uid = f'sh:{id(self):x}'

    def _block_keys(self, value: int) -> List[int]:
        keys = []
        for b in range(self.blocks):
            shift = b * self._block_width
            block_val = (value >> shift) & ((1 << self._block_width) - 1)
            key = (b << 32) | block_val
            keys.append(key)
        return keys

    def insert(self, key: str, fp: Simhash) -> None:
        with self._lock:
            self._fingerprints[key] = fp
            for bk in self._block_keys(fp.value):
                self._index.setdefault(bk, []).append(key)

    def remove(self, key: str) -> bool:
        with self._lock:
            if key not in self._fingerprints:
                return False
            fp = self._fingerprints.pop(key)
            for bk in self._block_keys(fp.value):
                if bk in self._index:
                    self._index[bk] = [k for k in self._index[bk] if k != key]
                    if not self._index[bk]:
                        del self._index[bk]
            return True

    def candidates(self, fp: Simhash) -> List[str]:
        seen: Set[str] = set()
        with self._lock:
            for bk in self._block_keys(fp.value):
                for k in self._index.get(bk, []):
                    if k not in seen:
                        seen.add(k)
        return list(seen)

    def find_duplicates(self, threshold: float = 0.85) -> List[Tuple[str, str, float]]:
        max_dist = int(_SIMHASH_BITS * (1.0 - threshold))
        pairs: Dict[Tuple[str, str], float] = {}
        with self._lock:
            keys = list(self._fingerprints.keys())
            for i in range(len(keys)):
                fp_i = self._fingerprints[keys[i]]
                candidate_keys = set()
                for bk in self._block_keys(fp_i.value):
                    for k in self._index.get(bk, []):
                        if k != keys[i]:
                            candidate_keys.add(k)
                for j_key in candidate_keys:
                    pair = (keys[i], j_key) if keys[i] < j_key else (j_key, keys[i])
                    if pair not in pairs:
                        fp_j = self._fingerprints[pair[1] if pair[0] == keys[i] else pair[0]]
                        actual = fp_i.distance_to(self._fingerprints[pair[1] if pair[0] == keys[i] else pair[0]])
                        if actual <= max_dist:
                            sim = 1.0 - actual / _SIMHASH_BITS
                            pairs[pair] = sim
        return [(a, b, sim) for (a, b), sim in sorted(pairs.items(), key=lambda x: -x[1])]

    def query(self, fp: Simhash, threshold: float = 0.85) -> List[Tuple[str, float]]:
        max_dist = int(_SIMHASH_BITS * (1.0 - threshold))
        results: Dict[str, float] = {}
        for ck in self.candidates(fp):
            other = self._fingerprints.get(ck)
            if other:
                d = fp.distance_to(other)
                if d <= max_dist:
                    results[ck] = 1.0 - d / _SIMHASH_BITS
        return sorted(results.items(), key=lambda x: -x[1])

    def size(self) -> int:
        return len(self._fingerprints)

    def clear(self) -> None:
        with self._lock:
            self._index.clear()
            self._fingerprints.clear()

    def to_dict(self) -> Dict[str, Any]:
        with self._lock:
            return {
                'blocks': self.blocks,
                'fingerprints': {k: v.value for k, v in self._fingerprints.items()},
            }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> SimhashIndex:
        idx = SimhashIndex(data['blocks'])
        for k, v in data.get('fingerprints', {}).items():
            idx._fingerprints[k] = Simhash(v)
            for bk in idx._block_keys(v):
                idx._index.setdefault(bk, []).append(k)
        return idx


class SimhashEngine:
    """Top-level engine managing simhash operations and indexes."""

    def __init__(self) -> None:
        self._indexes: Dict[str, SimhashIndex] = {}
        self._default_index: Optional[SimhashIndex] = None
        self._lock = threading.Lock()

    def create_index(self, name: str = 'default', blocks: int = 4) -> SimhashIndex:
        idx = SimhashIndex(blocks)
        with self._lock:
            self._indexes[name] = idx
            if name == 'default':
                self._default_index = idx
        return idx

    def get_index(self, name: str = 'default') -> SimhashIndex:
        with self._lock:
            if name in self._indexes:
                return self._indexes[name]
            if self._default_index is None:
                self._default_index = self.create_index()
            return self._default_index

    def remove_index(self, name: str) -> bool:
        with self._lock:
            if name in self._indexes:
                del self._indexes[name]
                if name == 'default':
                    self._default_index = None
                return True
            return False

    def list_indexes(self) -> List[str]:
        with self._lock:
            return list(self._indexes.keys())

    def fingerprint(self, text: str,
                    weights: Optional[Dict[str, float]] = None) -> Simhash:
        return Simhash.fingerprint(text, weights)

    def hamming_distance(self, a: Simhash, b: Simhash) -> int:
        return Simhash.hamming_distance(a, b)

    def similarity(self, a: Simhash, b: Simhash) -> float:
        return a.similarity(b)

    def insert(self, key: str, text: str,
               index_name: str = 'default',
               weights: Optional[Dict[str, float]] = None) -> Simhash:
        fp = self.fingerprint(text, weights)
        self.get_index(index_name).insert(key, fp)
        return fp

    def candidates(self, text: str, index_name: str = 'default',
                   weights: Optional[Dict[str, float]] = None) -> List[str]:
        fp = self.fingerprint(text, weights)
        return self.get_index(index_name).candidates(fp)

    def query(self, text: str, threshold: float = 0.85,
              index_name: str = 'default',
              weights: Optional[Dict[str, float]] = None) -> List[Tuple[str, float]]:
        fp = self.fingerprint(text, weights)
        return self.get_index(index_name).query(fp, threshold)

    def find_duplicates(self, index_name: str = 'default',
                        threshold: float = 0.85) -> List[Tuple[str, str, float]]:
        return self.get_index(index_name).find_duplicates(threshold)

    def summary(self) -> Dict[str, Any]:
        with self._lock:
            return {
                'index_count': len(self._indexes),
                'index_names': list(self._indexes.keys()),
            }
