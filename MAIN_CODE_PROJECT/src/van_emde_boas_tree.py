"""Van Emde Boas tree for bounded-universe integer indexing with O(log log U) operations."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
import math
import threading
import time


def _sqrt(u: int) -> int:
    return int(math.isqrt(u))


def _high(x: int, s: int) -> int:
    return x // s


def _low(x: int, s: int) -> int:
    return x % s


def _index(high: int, low: int, s: int) -> int:
    return high * s + low


class VEBNode:
    """Recursive van Emde Boas tree node."""

    def __init__(self, u: int) -> None:
        self.u = u
        self.min: Optional[int] = None
        self.max: Optional[int] = None
        self.summary: Optional[VEBNode] = None
        self.clusters: Dict[int, VEBNode] = {}
        if u > 2:
            s = _sqrt(u)
            self.summary = VEBNode(s)


class VEBTree:
    """Van Emde Boas tree for bounded-universe integer indexing."""

    def __init__(self, universe_size: int = 65536) -> None:
        if universe_size < 2:
            raise ValueError('Universe size must be >= 2')
        self._universe = universe_size
        self._root = VEBNode(universe_size)
        self._lock = threading.Lock()
        self._size: int = 0
        self._uid = f'veb:{id(self):x}'

    def _min(self, node: Optional[VEBNode]) -> Optional[int]:
        return node.min if node else None

    def _max(self, node: Optional[VEBNode]) -> Optional[int]:
        return node.max if node else None

    def min(self) -> Optional[int]:
        with self._lock:
            return self._root.min

    def max(self) -> Optional[int]:
        with self._lock:
            return self._root.max

    def insert(self, key: int) -> None:
        if key < 0 or key >= self._universe:
            raise ValueError(f'Key {key} out of bounds [0, {self._universe})')
        with self._lock:
            self._insert(self._root, key)
            self._size += 1

    def _insert(self, node: VEBNode, key: int) -> None:
        if node.min is None:
            node.min = key
            node.max = key
            return
        if key < node.min:
            key, node.min = node.min, key
        if node.u > 2:
            s = _sqrt(node.u)
            hi = _high(key, s)
            lo = _low(key, s)
            if hi not in node.clusters:
                node.clusters[hi] = VEBNode(s)
            if node.clusters[hi].min is None:
                self._insert(node.summary, hi)
            self._insert(node.clusters[hi], lo)
        if key > node.max:
            node.max = key

    def delete(self, key: int) -> bool:
        if key < 0 or key >= self._universe:
            return False
        with self._lock:
            if self._root.min is None:
                return False
            result = self._delete(self._root, key)
            if result:
                self._size -= 1
            return result

    def _delete(self, node: VEBNode, key: int) -> bool:
        if node.min is None:
            return False
        if key < node.min or key > node.max:
            return False
        if node.min == node.max:
            node.min = None
            node.max = None
            return True
        if node.u == 2:
            if key == 0:
                node.min = 1
            else:
                node.min = 0
            node.max = node.min
            return True
        s = _sqrt(node.u)
        if key == node.min:
            summary_min = self._min(node.summary)
            if summary_min is None:
                node.min = node.max
                return True
            first_cluster = node.clusters.get(summary_min)
            if first_cluster:
                key = _index(summary_min, first_cluster.min, s)
                node.min = key
        hi = _high(key, s)
        lo = _low(key, s)
        if hi in node.clusters:
            self._delete(node.clusters[hi], lo)
            if node.clusters[hi].min is None:
                self._delete(node.summary, hi)
                del node.clusters[hi]
        if key == node.max:
            summary_max = self._max(node.summary)
            if summary_max is None:
                node.max = node.min
            else:
                last_cluster = node.clusters.get(summary_max)
                if last_cluster:
                    node.max = _index(summary_max, last_cluster.max, s)
                else:
                    node.max = node.min
        return True

    def successor(self, key: int) -> Optional[int]:
        if key < 0 or key >= self._universe:
            return None
        with self._lock:
            return self._successor(self._root, key)

    def _successor(self, node: VEBNode, key: int) -> Optional[int]:
        if node.min is None:
            return None
        if key < node.min:
            return node.min
        if node.u == 2:
            if key == 0 and node.max == 1:
                return 1
            return None
        s = _sqrt(node.u)
        hi = _high(key, s)
        lo = _low(key, s)
        max_low = None
        if hi in node.clusters:
            cluster_node = node.clusters[hi]
            if lo < (cluster_node.max if cluster_node.max is not None else -1):
                succ = self._successor(cluster_node, lo)
                if succ is not None:
                    return _index(hi, succ, s)
                max_low = cluster_node.max
        next_hi = hi + 1
        succ_hi = self._successor(node.summary, next_hi - 1) if next_hi > 0 else node.summary.min
        if succ_hi is not None:
            if hi in node.clusters and node.clusters[hi].max is not None:
                return _index(succ_hi, 0, s)
            while succ_hi is not None and succ_hi not in node.clusters:
                succ_hi = self._successor(node.summary, succ_hi)
            if succ_hi is not None and succ_hi in node.clusters:
                return _index(succ_hi, node.clusters[succ_hi].min, s)
        return None

    def predecessor(self, key: int) -> Optional[int]:
        if key < 0 or key >= self._universe:
            return None
        with self._lock:
            return self._predecessor(self._root, key)

    def _predecessor(self, node: VEBNode, key: int) -> Optional[int]:
        if node.min is None:
            return None
        if key <= node.min:
            return None
        if node.u == 2:
            if key == 1 and node.min == 0:
                return 0
            return None
        s = _sqrt(node.u)
        hi = _high(key - 1, s)
        lo = _low(key - 1, s)
        if hi in node.clusters:
            cluster_min = node.clusters[hi].min
            if cluster_min is not None and lo >= cluster_min:
                pred = self._predecessor(node.clusters[hi], lo)
                if pred is not None:
                    return _index(hi, pred, s)
        pred_hi = self._predecessor(node.summary, hi)
        if pred_hi is not None:
            if pred_hi in node.clusters:
                return _index(pred_hi, node.clusters[pred_hi].max, s)
        if hi in node.clusters and node.clusters[hi].min is not None:
            return _index(hi, node.clusters[hi].min, s)
        return node.min if node.min is not None else None

    def contains(self, key: int) -> bool:
        if key < 0 or key >= self._universe:
            return False
        with self._lock:
            if self._root.min is None:
                return False
            return self._contains(self._root, key)

    def _contains(self, node: VEBNode, key: int) -> bool:
        if node.min is None:
            return False
        if key == node.min or key == node.max:
            return True
        if node.u == 2:
            return False
        s = _sqrt(node.u)
        hi = _high(key, s)
        lo = _low(key, s)
        if hi in node.clusters:
            return self._contains(node.clusters[hi], lo)
        return False

    def size(self) -> int:
        return self._size

    def clear(self) -> None:
        with self._lock:
            self._root = VEBNode(self._universe)
            self._size = 0

    def metrics(self) -> Dict[str, Any]:
        node_count = [0]
        self._count_nodes(self._root, node_count)
        return {
            'universe_size': self._universe,
            'entries': self._size,
            'total_nodes': node_count[0],
            'min_key': self._root.min,
            'max_key': self._root.max,
        }

    def _count_nodes(self, node: VEBNode, count: List[int]) -> None:
        count[0] += 1
        for cluster in node.clusters.values():
            self._count_nodes(cluster, count)

    def to_dict(self) -> Dict[str, Any]:
        return {'metrics': self.metrics()}


class VEBTreeEngine:
    """Top-level engine managing multiple van Emde Boas trees."""

    def __init__(self) -> None:
        self._trees: Dict[str, VEBTree] = {}
        self._default_tree: Optional[VEBTree] = None
        self._lock = threading.Lock()

    def create(self, name: str = 'default', universe_size: int = 65536) -> VEBTree:
        tree = VEBTree(universe_size)
        with self._lock:
            self._trees[name] = tree
            if name == 'default':
                self._default_tree = tree
        return tree

    def get(self, name: str = 'default') -> VEBTree:
        with self._lock:
            if name in self._trees:
                return self._trees[name]
            if self._default_tree is None:
                self._default_tree = self.create()
            return self._default_tree

    def remove(self, name: str) -> bool:
        with self._lock:
            if name in self._trees:
                del self._trees[name]
                if name == 'default':
                    self._default_tree = None
                return True
            return False

    def list(self) -> List[str]:
        with self._lock:
            return list(self._trees.keys())

    def insert(self, key: int, name: str = 'default') -> None:
        self.get(name).insert(key)

    def delete(self, key: int, name: str = 'default') -> bool:
        return self.get(name).delete(key)

    def successor(self, key: int, name: str = 'default') -> Optional[int]:
        return self.get(name).successor(key)

    def predecessor(self, key: int, name: str = 'default') -> Optional[int]:
        return self.get(name).predecessor(key)

    def min_key(self, name: str = 'default') -> Optional[int]:
        return self.get(name).min()

    def max_key(self, name: str = 'default') -> Optional[int]:
        return self.get(name).max()

    def contains(self, key: int, name: str = 'default') -> bool:
        return self.get(name).contains(key)

    def metrics(self, name: str = 'default') -> Dict[str, Any]:
        return self.get(name).metrics()

    def summary(self) -> Dict[str, Any]:
        with self._lock:
            return {
                'tree_count': len(self._trees),
                'tree_names': list(self._trees.keys()),
            }
