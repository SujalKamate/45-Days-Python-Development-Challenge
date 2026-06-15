"""MinHash signature generation and locality-sensitive similarity search."""

from __future__ import annotations

from typing import Any, Dict, Hashable, List, Optional, Set, Tuple
import hashlib
import heapq
import json
import math
import random
import struct
import threading
import time


_MAX_HASH = (1 << 32) - 1


def _minhash_hash(item: Hashable, seed: int) -> int:
    h = hashlib.sha256(f'{seed}:{item}'.encode('utf-8'))
    return struct.unpack('<I', h.digest()[:4])[0]


class MinHashSignature:
    """Fixed-length minwise hash signature for a set."""

    def __init__(self, sig: List[int]) -> None:
        self.sig = list(sig)

    def __len__(self) -> int:
        return len(self.sig)

    def similarity(self, other: MinHashSignature) -> float:
        if len(self.sig) != len(other.sig):
            raise ValueError('Signature lengths must match')
        if not self.sig:
            return 0.0
        matches = sum(1 for a, b in zip(self.sig, other.sig) if a == b)
        return matches / len(self.sig)

    def to_dict(self) -> List[int]:
        return list(self.sig)

    @staticmethod
    def from_dict(data: List[int]) -> MinHashSignature:
        return MinHashSignature(data)


class MinHash:
    """MinHash generator producing k-length signatures for arbitrary sets."""

    def __init__(self, k: int = 128) -> None:
        if k < 1:
            raise ValueError('k must be >= 1')
        self.k = k
        self._seeds: List[int] = [random.randint(0, _MAX_HASH) for _ in range(k)]
        self._uid = f'mh:{id(self):x}'

    def signature(self, items: Set[Hashable]) -> MinHashSignature:
        sig = [_MAX_HASH] * self.k
        for item in items:
            if not isinstance(item, Hashable):
                continue
            for i in range(self.k):
                h = _minhash_hash(item, self._seeds[i])
                if h < sig[i]:
                    sig[i] = h
        return MinHashSignature(sig)

    @staticmethod
    def similarity(sig1: MinHashSignature, sig2: MinHashSignature) -> float:
        return sig1.similarity(sig2)

    @staticmethod
    def jaccard(set_a: Set[Hashable], set_b: Set[Hashable]) -> float:
        if not set_a and not set_b:
            return 1.0
        union = len(set_a | set_b)
        if union == 0:
            return 1.0
        return len(set_a & set_b) / union


class LSHBand:
    """A single LSH band that buckets signatures by a band slice."""

    def __init__(self, band_index: int) -> None:
        self.band_index = band_index
        self._buckets: Dict[int, List[str]] = {}
        self._lock = threading.Lock()

    def insert(self, key: str, band_hash: int) -> None:
        with self._lock:
            self._buckets.setdefault(band_hash, []).append(key)

    def lookup(self, band_hash: int) -> List[str]:
        with self._lock:
            return list(self._buckets.get(band_hash, []))

    def clear(self) -> None:
        with self._lock:
            self._buckets.clear()


class LSHIndex:
    """Locality-sensitive hash index with bands for candidate retrieval."""

    def __init__(self, signature_len: int, bands: int, rows: int) -> None:
        if bands * rows != signature_len:
            raise ValueError('bands * rows must equal signature length')
        self.signature_len = signature_len
        self.bands = bands
        self.rows = rows
        self._bands_list: List[LSHBand] = [LSHBand(b) for b in range(bands)]
        self._signatures: Dict[str, MinHashSignature] = {}
        self._lock = threading.Lock()

    def insert(self, key: str, sig: MinHashSignature) -> None:
        if len(sig) != self.signature_len:
            raise ValueError('Signature length mismatch')
        with self._lock:
            self._signatures[key] = sig
            for b in range(self.bands):
                start = b * self.rows
                end = start + self.rows
                band_slice = tuple(sig.sig[start:end])
                band_hash = hash(band_slice)
                self._bands_list[b].insert(key, band_hash)

    def candidate_pairs(self, threshold: float = 0.5) -> List[Tuple[str, str, float]]:
        candidates: Dict[Tuple[str, str], float] = {}
        with self._lock:
            for band in self._bands_list:
                with band._lock:
                    for candidates_list in band._buckets.values():
                        for i in range(len(candidates_list)):
                            for j in range(i + 1, len(candidates_list)):
                                a, b = candidates_list[i], candidates_list[j]
                                if a < b:
                                    pair = (a, b)
                                else:
                                    pair = (b, a)
                                if pair not in candidates:
                                    sig_a = self._signatures.get(a)
                                    sig_b = self._signatures.get(b)
                                    if sig_a and sig_b:
                                        sim = sig_a.similarity(sig_b)
                                        if sim >= threshold:
                                            candidates[pair] = sim
        return [(a, b, sim) for (a, b), sim in sorted(candidates.items(), key=lambda x: -x[1])]

    def query(self, sig: MinHashSignature, threshold: float = 0.5) -> List[Tuple[str, float]]:
        if len(sig) != self.signature_len:
            raise ValueError('Signature length mismatch')
        candidates: Dict[str, float] = {}
        with self._lock:
            for b in range(self.bands):
                start = b * self.rows
                end = start + self.rows
                band_slice = tuple(sig.sig[start:end])
                band_hash = hash(band_slice)
                for key in self._bands_list[b].lookup(band_hash):
                    if key not in candidates and key in self._signatures:
                        sim = sig.similarity(self._signatures[key])
                        if sim >= threshold:
                            candidates[key] = sim
        return sorted(candidates.items(), key=lambda x: -x[1])

    def remove(self, key: str) -> bool:
        with self._lock:
            if key in self._signatures:
                del self._signatures[key]
                return True
            return False

    def clear(self) -> None:
        with self._lock:
            self._signatures.clear()
            for band in self._bands_list:
                band.clear()

    def size(self) -> int:
        return len(self._signatures)

    def to_dict(self) -> Dict[str, Any]:
        with self._lock:
            return {
                'signature_len': self.signature_len,
                'bands': self.bands,
                'rows': self.rows,
                'signatures': {k: v.to_dict() for k, v in self._signatures.items()},
            }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> LSHIndex:
        idx = LSHIndex(data['signature_len'], data['bands'], data['rows'])
        for k, sd in data.get('signatures', {}).items():
            idx._signatures[k] = MinHashSignature.from_dict(sd)
        return idx


class MinHashLSHEngine:
    """Top-level engine managing MinHash generators and LSH indexes."""

    def __init__(self) -> None:
        self._generators: Dict[str, MinHash] = {}
        self._indexes: Dict[str, LSHIndex] = {}
        self._default_gen: Optional[MinHash] = None
        self._lock = threading.Lock()

    def create_generator(self, name: str = 'default', k: int = 128) -> MinHash:
        mh = MinHash(k)
        with self._lock:
            self._generators[name] = mh
            if name == 'default':
                self._default_gen = mh
        return mh

    def get_generator(self, name: str = 'default') -> MinHash:
        with self._lock:
            if name in self._generators:
                return self._generators[name]
            if self._default_gen is None:
                self._default_gen = self.create_generator()
            return self._default_gen

    def remove_generator(self, name: str) -> bool:
        with self._lock:
            if name in self._generators:
                del self._generators[name]
                if name == 'default':
                    self._default_gen = None
                return True
            return False

    def signature(self, items: Set[Hashable], gen_name: str = 'default') -> MinHashSignature:
        return self.get_generator(gen_name).signature(items)

    def similarity(self, sig1: MinHashSignature, sig2: MinHashSignature) -> float:
        return MinHash.similarity(sig1, sig2)

    def jaccard(self, set_a: Set[Hashable], set_b: Set[Hashable]) -> float:
        return MinHash.jaccard(set_a, set_b)

    def create_index(self, name: str, signature_len: int,
                     bands: int, rows: int) -> LSHIndex:
        idx = LSHIndex(signature_len, bands, rows)
        with self._lock:
            self._indexes[name] = idx
        return idx

    def get_index(self, name: str) -> Optional[LSHIndex]:
        with self._lock:
            return self._indexes.get(name)

    def remove_index(self, name: str) -> bool:
        with self._lock:
            if name in self._indexes:
                del self._indexes[name]
                return True
            return False

    def index_insert(self, index_name: str, key: str, sig: MinHashSignature) -> None:
        idx = self.get_index(index_name)
        if idx:
            idx.insert(key, sig)

    def candidate_pairs(self, index_name: str,
                        threshold: float = 0.5) -> List[Tuple[str, str, float]]:
        idx = self.get_index(index_name)
        if idx:
            return idx.candidate_pairs(threshold)
        return []

    def query(self, index_name: str, sig: MinHashSignature,
              threshold: float = 0.5) -> List[Tuple[str, float]]:
        idx = self.get_index(index_name)
        if idx:
            return idx.query(sig, threshold)
        return []

    def list_generators(self) -> List[str]:
        with self._lock:
            return list(self._generators.keys())

    def list_indexes(self) -> List[str]:
        with self._lock:
            return list(self._indexes.keys())

    def summary(self) -> Dict[str, Any]:
        with self._lock:
            return {
                'generator_count': len(self._generators),
                'generator_names': list(self._generators.keys()),
                'index_count': len(self._indexes),
                'index_names': list(self._indexes.keys()),
            }
