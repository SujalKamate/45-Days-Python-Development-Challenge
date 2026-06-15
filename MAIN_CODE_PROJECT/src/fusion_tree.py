"""Fusion tree integer search with sketch-compressed keys and bit-parallel operations."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
import math
import random
import threading
import time


_WORD_SIZE = 64


def _bit_pos(x: int, pos: int) -> int:
    return (x >> pos) & 1


def _distinguishing_bits(keys: List[int]) -> List[int]:
    if len(keys) <= 1:
        return []
    bits = []
    for i in range(_WORD_SIZE - 1, -1, -1):
        seen = set()
        for k in keys:
            seen.add(_bit_pos(k, i))
        if len(seen) > 1:
            bits.append(i)
            if len(bits) >= len(keys):
                break
    return bits[:len(keys)]


def _sketch(key: int, bits: List[int]) -> int:
    s = 0
    for i, b in enumerate(bits):
        if _bit_pos(key, b):
            s |= 1 << i
    return s


def _pack(sketches: List[int], bits_per_key: int) -> int:
    packed = 0
    for i, s in enumerate(sketches):
        packed |= (s & ((1 << bits_per_key) - 1)) << (i * bits_per_key)
    return packed


class FusionNode:
    """Internal or leaf node with sketch-compressed keys."""

    def __init__(self, is_leaf: bool = False) -> None:
        self.is_leaf = is_leaf
        self.keys: List[int] = []
        self.children: List[FusionNode] = []
        self.sketch_bits: List[int] = []
        self.sketch_word: int = 0
        self.bits_per_key: int = 0

    def rebuild_sketch(self) -> None:
        if not self.keys:
            self.sketch_bits = []
            self.sketch_word = 0
            return
        self.sketch_bits = _distinguishing_bits(self.keys)
        if not self.sketch_bits:
            return
        self.bits_per_key = max(1, (len(self.sketch_bits) + _WORD_SIZE - 1) // _WORD_SIZE)
        sketches = [_sketch(k, self.sketch_bits) for k in self.keys]
        pw = max(1, (len(self.sketch_bits) + _WORD_SIZE - 1) // _WORD_SIZE)
        self.sketch_word = _pack(sketches, pw)

    def sketch_search(self, key: int) -> int:
        if not self.sketch_bits or not self.keys:
            return 0
        sk = _sketch(key, self.sketch_bits)
        pw = self.bits_per_key
        result = 0
        for i, k in enumerate(self.keys):
            if sk <= _sketch(k, self.sketch_bits):
                result = i
                break
        else:
            result = len(self.keys)
        return result

    def is_full(self) -> bool:
        return len(self.keys) >= 7


class FusionTree:
    """Fusion tree with sketch-based search and B-tree style nodes."""

    def __init__(self, max_keys: int = 7) -> None:
        self.max_keys = max_keys
        self._root = FusionNode(is_leaf=True)
        self._lock = threading.Lock()
        self._size: int = 0
        self._uid = f'ft:{id(self):x}'

    def insert(self, key: int) -> None:
        with self._lock:
            self._insert(self._root, key)
            self._size += 1

    def _insert(self, node: FusionNode, key: int) -> None:
        if node.is_leaf:
            idx = 0
            while idx < len(node.keys) and node.keys[idx] < key:
                idx += 1
            if idx < len(node.keys) and node.keys[idx] == key:
                return
            node.keys.insert(idx, key)
            node.rebuild_sketch()
            if node.is_full():
                self._split(node)
        else:
            idx = node.sketch_search(key)
            if idx > len(node.children) - 1:
                idx = len(node.children) - 1
            self._insert(node.children[idx], key)
            if node.children[idx].is_full():
                self._split_child(node, idx)

    def _split(self, node: FusionNode) -> None:
        if len(node.keys) <= 1:
            return
        mid = len(node.keys) // 2
        mid_key = node.keys[mid]
        left = FusionNode(is_leaf=node.is_leaf)
        right = FusionNode(is_leaf=node.is_leaf)
        left.keys = node.keys[:mid]
        right.keys = node.keys[mid + 1:]
        if not node.is_leaf and len(node.children) > mid:
            left.children = node.children[:mid + 1]
            right.children = node.children[mid + 1:]
        left.rebuild_sketch()
        right.rebuild_sketch()
        new_root = FusionNode()
        new_root.keys = [mid_key]
        new_root.children = [left, right]
        new_root.rebuild_sketch()
        self._root = new_root

    def _split_child(self, parent: FusionNode, idx: int) -> None:
        child = parent.children[idx]
        if len(child.keys) <= 1:
            return
        mid = len(child.keys) // 2
        mid_key = child.keys[mid]
        right = FusionNode(is_leaf=child.is_leaf)
        right.keys = child.keys[mid + 1:]
        child.keys = child.keys[:mid]
        if not child.is_leaf and len(child.children) > mid:
            right.children = child.children[mid + 1:]
            child.children = child.children[:mid + 1]
        child.rebuild_sketch()
        right.rebuild_sketch()
        parent.keys.insert(idx, mid_key)
        parent.children.insert(idx + 1, right)
        parent.rebuild_sketch()

    def contains(self, key: int) -> bool:
        with self._lock:
            node = self._root
            while node:
                if node.is_leaf:
                    return key in node.keys
                idx = node.sketch_search(key)
                if idx < len(node.children):
                    node = node.children[idx]
                else:
                    return False
            return False

    def predecessor(self, key: int) -> Optional[int]:
        with self._lock:
            return self._predecessor(self._root, key)

    def _predecessor(self, node: FusionNode, key: int) -> Optional[int]:
        if node.is_leaf:
            best = None
            for k in node.keys:
                if k < key:
                    best = k
                else:
                    break
            return best
        idx = node.sketch_search(key)
        if idx > 0:
            pred = self._predecessor(node.children[idx - 1], key)
            if pred is not None:
                return pred
        elif idx == len(node.children):
            pred = self._predecessor(node.children[-1], key)
            if pred is not None:
                return pred
        if idx < len(node.keys) and node.keys[idx] < key:
            return node.keys[idx]
        for i in range(idx - 1, -1, -1):
            pred = self._predecessor(node.children[i], key)
            if pred is not None:
                return pred
        return None

    def successor(self, key: int) -> Optional[int]:
        with self._lock:
            return self._successor(self._root, key)

    def _successor(self, node: FusionNode, key: int) -> Optional[int]:
        if node.is_leaf:
            for k in node.keys:
                if k > key:
                    return k
            return None
        idx = node.sketch_search(key)
        if idx < len(node.children):
            succ = self._successor(node.children[idx], key)
            if succ is not None:
                return succ
        for i in range(idx, len(node.keys)):
            if node.keys[i] > key:
                return node.keys[i]
        for i in range(idx + 1, len(node.children)):
            succ = self._successor(node.children[i], key)
            if succ is not None:
                return succ
        return None

    def delete(self, key: int) -> bool:
        with self._lock:
            result = self._delete(self._root, key)
            if result:
                self._size -= 1
            return result

    def _delete(self, node: FusionNode, key: int) -> bool:
        if node.is_leaf:
            if key in node.keys:
                node.keys.remove(key)
                node.rebuild_sketch()
                return True
            return False
        idx = node.sketch_search(key)
        if idx < len(node.children):
            return self._delete(node.children[idx], key)
        return False

    def min_key(self) -> Optional[int]:
        node = self._root
        while node and not node.is_leaf:
            node = node.children[0]
        if node and node.keys:
            return node.keys[0]
        return None

    def max_key(self) -> Optional[int]:
        node = self._root
        while node and not node.is_leaf:
            node = node.children[-1]
        if node and node.keys:
            return node.keys[-1]
        return None

    def size(self) -> int:
        return self._size

    def clear(self) -> None:
        with self._lock:
            self._root = FusionNode(is_leaf=True)
            self._size = 0

    def metrics(self) -> Dict[str, Any]:
        node_count = [0]
        total_keys = [0]
        self._count(self._root, node_count, total_keys)
        return {
            'entries': self._size,
            'nodes': node_count[0],
            'total_keys_stored': total_keys[0],
            'min_key': self.min_key(),
            'max_key': self.max_key(),
            'tree_depth': self._depth(),
        }

    def _count(self, node: FusionNode, nc: List[int], kc: List[int]) -> None:
        nc[0] += 1
        kc[0] += len(node.keys)
        if not node.is_leaf:
            for child in node.children:
                self._count(child, nc, kc)

    def _depth(self) -> int:
        d = 0
        node = self._root
        while node and not node.is_leaf:
            d += 1
            node = node.children[0] if node.children else None
        return d + 1


class FusionTreeEngine:
    """Top-level engine managing multiple fusion trees."""

    def __init__(self) -> None:
        self._trees: Dict[str, FusionTree] = {}
        self._default_tree: Optional[FusionTree] = None
        self._lock = threading.Lock()

    def create(self, name: str = 'default', max_keys: int = 7) -> FusionTree:
        tree = FusionTree(max_keys)
        with self._lock:
            self._trees[name] = tree
            if name == 'default':
                self._default_tree = tree
        return tree

    def get(self, name: str = 'default') -> FusionTree:
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

    def predecessor(self, key: int, name: str = 'default') -> Optional[int]:
        return self.get(name).predecessor(key)

    def successor(self, key: int, name: str = 'default') -> Optional[int]:
        return self.get(name).successor(key)

    def contains(self, key: int, name: str = 'default') -> bool:
        return self.get(name).contains(key)

    def min_key(self, name: str = 'default') -> Optional[int]:
        return self.get(name).min_key()

    def max_key(self, name: str = 'default') -> Optional[int]:
        return self.get(name).max_key()

    def metrics(self, name: str = 'default') -> Dict[str, Any]:
        return self.get(name).metrics()

    def summary(self) -> Dict[str, Any]:
        with self._lock:
            return {
                'tree_count': len(self._trees),
                'tree_names': list(self._trees.keys()),
            }
