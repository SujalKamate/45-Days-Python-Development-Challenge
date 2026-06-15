"""Bloom filter cascade for hierarchical membership verification and query routing."""

from __future__ import annotations

from typing import Any, Dict, Hashable, List, Optional, Set, Tuple
import hashlib
import json
import math
import struct
import threading
import time


def _optimal_m(n: int, p: float) -> int:
    return max(1, int(math.ceil(-n * math.log(p) / (math.log(2) ** 2))))


def _optimal_k(m: int, n: int) -> int:
    return max(1, int(round((m / n) * math.log(2))))


def _hashes(item: Hashable, m: int, k: int) -> List[int]:
    h = hashlib.sha256(str(item).encode('utf-8')).digest()
    h1 = struct.unpack('<Q', h[:8])[0]
    h2 = struct.unpack('<Q', h[8:16])[0]
    return [(h1 + i * h2) % m for i in range(k)]


class BloomFilterLayer:
    """Single bloom filter layer with configurable size and false-positive rate."""

    def __init__(self, n: int = 10000, p: float = 0.01,
                 m: Optional[int] = None, k: Optional[int] = None) -> None:
        if m is None:
            m = _optimal_m(n, p)
        if k is None:
            k = _optimal_k(m, n)
        self.m: int = m
        self.k: int = k
        self.n: int = n
        self.p: float = p
        self._bits: bytearray = bytearray((m + 7) >> 3)
        self._count: int = 0
        self._lock = threading.Lock()
        self._uid = f'bf:{id(self):x}'

    def insert(self, item: Hashable) -> None:
        with self._lock:
            for h in _hashes(item, self.m, self.k):
                byte_idx = h >> 3
                bit_idx = h & 7
                self._bits[byte_idx] |= 1 << bit_idx
            self._count += 1

    def contains(self, item: Hashable) -> bool:
        for h in _hashes(item, self.m, self.k):
            byte_idx = h >> 3
            bit_idx = h & 7
            if not (self._bits[byte_idx] & (1 << bit_idx)):
                return False
        return True

    def clear(self) -> None:
        with self._lock:
            self._bits = bytearray((self.m + 7) >> 3)
            self._count = 0

    def occupancy(self) -> float:
        set_bits = sum(bin(b).count('1') for b in self._bits)
        return set_bits / (self.m or 1)

    def fpr(self) -> float:
        return (1.0 - math.exp(-self.k * self._count / (self.m or 1))) ** self.k

    def copy(self) -> BloomFilterLayer:
        bf = BloomFilterLayer(self.n, self.p, self.m, self.k)
        bf._bits = bytearray(self._bits)
        bf._count = self._count
        return bf

    def union(self, other: BloomFilterLayer) -> BloomFilterLayer:
        if self.m != other.m or self.k != other.k:
            raise ValueError('Layer dimensions must match for union')
        bf = BloomFilterLayer(n=self.n, p=self.p, m=self.m, k=self.k)
        for i in range(len(self._bits)):
            bf._bits[i] = self._bits[i] | other._bits[i]
        return bf

    def intersection(self, other: BloomFilterLayer) -> BloomFilterLayer:
        if self.m != other.m or self.k != other.k:
            raise ValueError('Layer dimensions must match for intersection')
        bf = BloomFilterLayer(n=self.n, p=self.p, m=self.m, k=self.k)
        for i in range(len(self._bits)):
            bf._bits[i] = self._bits[i] & other._bits[i]
        return bf

    def to_dict(self) -> Dict[str, Any]:
        return {
            'm': self.m, 'k': self.k, 'n': self.n, 'p': self.p,
            'bits': list(self._bits), 'count': self._count,
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> BloomFilterLayer:
        bf = BloomFilterLayer(n=data['n'], p=data['p'], m=data['m'], k=data['k'])
        bf._bits = bytearray(data['bits'])
        bf._count = data.get('count', 0)
        return bf


class BloomCascade:
    """Hierarchical bloom filter cascade with parent-child layer relationships."""

    def __init__(self, name: str = 'default') -> None:
        self.name = name
        self._layers: Dict[str, BloomFilterLayer] = {}
        self._children: Dict[str, List[str]] = {}
        self._parents: Dict[str, str] = {}
        self._lock = threading.Lock()
        self._uid = f'bc:{id(self):x}'

    def add_layer(self, name: str, n: int = 10000, p: float = 0.01,
                  m: Optional[int] = None, k: Optional[int] = None,
                  parent: Optional[str] = None) -> BloomFilterLayer:
        with self._lock:
            if name in self._layers:
                raise ValueError(f'Layer {name!r} already exists')
            bf = BloomFilterLayer(n, p, m, k)
            self._layers[name] = bf
            if parent:
                if parent not in self._layers:
                    raise ValueError(f'Parent layer {parent!r} not found')
                self._children.setdefault(parent, []).append(name)
                self._parents[name] = parent
            return bf

    def get_layer(self, name: str) -> BloomFilterLayer:
        with self._lock:
            if name not in self._layers:
                raise ValueError(f'Layer {name!r} not found')
            return self._layers[name]

    def remove_layer(self, name: str) -> bool:
        with self._lock:
            if name not in self._layers:
                return False
            del self._layers[name]
            self._children.pop(name, None)
            parent = self._parents.pop(name, None)
            if parent and name in self._children.get(parent, []):
                self._children[parent].remove(name)
            for child in list(self._children.get(name, [])):
                self._parents.pop(child, None)
            return True

    def insert(self, layer: str, item: Hashable) -> None:
        self.get_layer(layer).insert(item)

    def contains(self, layer: str, item: Hashable) -> bool:
        return self.get_layer(layer).contains(item)

    def hierarchical_contains(self, item: Hashable) -> Dict[str, Any]:
        results: Dict[str, Any] = {}
        found = False
        deepest = None
        with self._lock:
            for name in self._layers:
                present = self._layers[name].contains(item)
                results[name] = present
                if present:
                    found = True
                    if deepest is None or len(name) > len(str(deepest)):
                        deepest = name
        return {
            'item': str(item),
            'found': found,
            'deepest_layer': deepest,
            'results': results,
        }

    def cascade_contains(self, item: Hashable, start: str) -> Dict[str, Any]:
        results: Dict[str, bool] = {}
        queue = [start]
        while queue:
            cur = queue.pop(0)
            if cur in self._layers:
                results[cur] = self._layers[cur].contains(item)
                for child in self._children.get(cur, []):
                    queue.append(child)
        return {
            'item': str(item),
            'start_layer': start,
            'results': results,
        }

    def union(self, other: BloomCascade) -> BloomCascade:
        cascade = BloomCascade(f'{self.name}_u_{other.name}')
        with self._lock, other._lock:
            all_names = set(self._layers) | set(other._layers)
            for name in all_names:
                if name in self._layers and name in other._layers:
                    cascade._layers[name] = self._layers[name].union(other._layers[name])
                elif name in self._layers:
                    cascade._layers[name] = self._layers[name].copy()
                else:
                    cascade._layers[name] = other._layers[name].copy()
            cascade._parents = dict(self._parents or other._parents)
            cascade._children = dict(self._children or other._children)
        return cascade

    def intersection(self, other: BloomCascade) -> BloomCascade:
        cascade = BloomCascade(f'{self.name}_i_{other.name}')
        with self._lock, other._lock:
            common = set(self._layers) & set(other._layers)
            for name in common:
                cascade._layers[name] = self._layers[name].intersection(other._layers[name])
            cascade._parents = dict(self._parents)
            cascade._children = dict(self._children)
        return cascade

    def occupancy_report(self) -> Dict[str, Dict[str, float]]:
        report: Dict[str, Dict[str, float]] = {}
        with self._lock:
            for name, bf in self._layers.items():
                report[name] = {
                    'occupancy': bf.occupancy(),
                    'fpr_estimate': bf.fpr(),
                    'inserted': bf._count,
                }
        return report

    def layers(self) -> List[str]:
        with self._lock:
            return list(self._layers.keys())

    def clear_layer(self, name: str) -> None:
        self.get_layer(name).clear()

    def clear_all(self) -> None:
        with self._lock:
            for bf in self._layers.values():
                bf.clear()

    def to_dict(self) -> Dict[str, Any]:
        with self._lock:
            return {
                'name': self.name,
                'layers': {k: v.to_dict() for k, v in self._layers.items()},
                'children': dict(self._children),
                'parents': dict(self._parents),
            }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> BloomCascade:
        cascade = BloomCascade(data['name'])
        for name, ld in data['layers'].items():
            cascade._layers[name] = BloomFilterLayer.from_dict(ld)
        cascade._children = dict(data.get('children', {}))
        cascade._parents = dict(data.get('parents', {}))
        return cascade


class BloomCascadeEngine:
    """Top-level engine managing multiple bloom filter cascades."""

    def __init__(self) -> None:
        self._cascades: Dict[str, BloomCascade] = {}
        self._default_cascade: Optional[BloomCascade] = None
        self._history: List[Dict[str, Any]] = []
        self._lock = threading.Lock()
        self._max_history = 100

    def create_cascade(self, name: str = 'default') -> BloomCascade:
        cascade = BloomCascade(name)
        with self._lock:
            self._cascades[name] = cascade
            if name == 'default':
                self._default_cascade = cascade
        return cascade

    def get_cascade(self, name: str = 'default') -> BloomCascade:
        with self._lock:
            if name in self._cascades:
                return self._cascades[name]
            if self._default_cascade is None:
                self._default_cascade = self.create_cascade()
            return self._default_cascade

    def remove_cascade(self, name: str) -> bool:
        with self._lock:
            if name in self._cascades:
                del self._cascades[name]
                if name == 'default':
                    self._default_cascade = None
                return True
            return False

    def list_cascades(self) -> List[str]:
        with self._lock:
            return list(self._cascades.keys())

    def add_layer(self, layer: str, n: int = 10000, p: float = 0.01,
                  m: Optional[int] = None, k: Optional[int] = None,
                  parent: Optional[str] = None,
                  cascade_name: str = 'default') -> BloomFilterLayer:
        return self.get_cascade(cascade_name).add_layer(layer, n, p, m, k, parent)

    def insert(self, layer: str, item: Hashable, cascade_name: str = 'default') -> None:
        self.get_cascade(cascade_name).insert(layer, item)

    def contains(self, layer: str, item: Hashable, cascade_name: str = 'default') -> bool:
        return self.get_cascade(cascade_name).contains(layer, item)

    def hierarchical_contains(self, item: Hashable,
                              cascade_name: str = 'default') -> Dict[str, Any]:
        return self.get_cascade(cascade_name).hierarchical_contains(item)

    def cascade_contains(self, item: Hashable, start: str,
                         cascade_name: str = 'default') -> Dict[str, Any]:
        return self.get_cascade(cascade_name).cascade_contains(item, start)

    def union(self, dst: str, src: str) -> bool:
        with self._lock:
            if dst not in self._cascades or src not in self._cascades:
                return False
            self._cascades[dst] = self._cascades[dst].union(self._cascades[src])
            return True

    def intersection(self, dst: str, src: str) -> bool:
        with self._lock:
            if dst not in self._cascades or src not in self._cascades:
                return False
            self._cascades[dst] = self._cascades[dst].intersection(self._cascades[src])
            return True

    def occupancy_report(self, cascade_name: str = 'default') -> Dict[str, Dict[str, float]]:
        return self.get_cascade(cascade_name).occupancy_report()

    def clear_layer(self, layer: str, cascade_name: str = 'default') -> None:
        self.get_cascade(cascade_name).clear_layer(layer)

    def clear_all(self, cascade_name: str = 'default') -> None:
        self.get_cascade(cascade_name).clear_all()

    def summary(self) -> Dict[str, Any]:
        with self._lock:
            return {
                'cascade_count': len(self._cascades),
                'cascade_names': list(self._cascades.keys()),
            }
