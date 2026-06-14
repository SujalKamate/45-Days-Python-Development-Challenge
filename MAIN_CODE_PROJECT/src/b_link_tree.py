"""B-Link tree concurrent indexing with sibling links and latch-coupling traversal."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
import math
import threading
import time


class BLinkNode:
    """A single B-Link tree node with keys, values/children, next pointer, and latch."""

    def __init__(self, is_leaf: bool, max_keys: int) -> None:
        self.is_leaf = is_leaf
        self.max_keys = max_keys
        self.keys: List[str] = []
        self.values: List[Any] = [] if is_leaf else []
        self.children: List[BLinkNode] = [] if not is_leaf else []
        self.next: Optional[BLinkNode] = None
        self.lock = threading.Lock()
        self._uid = f'bl:{id(self):x}'

    def is_full(self) -> bool:
        return len(self.keys) >= self.max_keys

    def is_half(self) -> bool:
        return len(self.keys) <= self.max_keys // 2

    def size(self) -> int:
        return len(self.keys)


class BLinkTree:
    """Concurrent B+Tree with sibling links and latch-coupling traversal.

    Supports lock-minimized insert, delete, point_query, and range_query
    using the B-link algorithm (sibling pointers + high-key bounds).
    """

    def __init__(self, max_keys: int = 4) -> None:
        if max_keys < 2:
            raise ValueError('max_keys must be >= 2')
        self.max_keys = max_keys
        self._root = BLinkNode(True, max_keys)
        self._lock = threading.Lock()
        self._uid = f'blt:{id(self):x}'
        self._stats: Dict[str, int] = {'inserts': 0, 'deletes': 0, 'splits': 0, 'queries': 0}

    def point_query(self, key: str) -> Any:
        self._stats['queries'] += 1
        node = self._search_to_leaf(key)
        with node.lock:
            for i, k in enumerate(node.keys):
                if k == key:
                    return node.values[i]
            return None

    def insert(self, key: str, value: Any) -> None:
        self._stats['inserts'] += 1
        self._insert_internal(self._root, key, value)

    def _insert_internal(self, node: BLinkNode, key: str, value: Any) -> None:
        with node.lock:
            if node.is_leaf:
                self._insert_into_leaf(node, key, value)
            else:
                child = self._find_child(node, key)
                self._insert_internal(child, key, value)
                with node.lock:
                    if child.is_full():
                        self._split_child(node, child)

    def _insert_into_leaf(self, node: BLinkNode, key: str, value: Any) -> None:
        i = 0
        while i < len(node.keys) and node.keys[i] < key:
            i += 1
        if i < len(node.keys) and node.keys[i] == key:
            node.values[i] = value
            return
        node.keys.insert(i, key)
        node.values.insert(i, value)
        if node.is_full():
            self._split_leaf(node)

    def _split_leaf(self, node: BLinkNode) -> None:
        mid = len(node.keys) // 2
        new_node = BLinkNode(True, self.max_keys)
        new_node.keys = node.keys[mid:]
        new_node.values = node.values[mid:]
        new_node.next = node.next
        node.keys = node.keys[:mid]
        node.values = node.values[:mid]
        node.next = new_node
        self._stats['splits'] += 1
        parent = self._find_parent(self._root, node)
        if parent is None:
            self._create_new_root(node, new_node.keys[0], new_node)
        else:
            self._insert_into_internal(parent, new_node.keys[0], new_node)

    def _split_child(self, parent: BLinkNode, child: BLinkNode) -> None:
        if child.is_leaf:
            self._split_leaf(child)
        else:
            mid = len(child.keys) // 2
            new_node = BLinkNode(False, self.max_keys)
            new_node.keys = child.keys[mid + 1:]
            new_node.children = child.children[mid + 1:]
            new_node.next = child.next
            mid_key = child.keys[mid]
            child.keys = child.keys[:mid]
            child.children = child.children[:mid + 1]
            child.next = new_node
            self._stats['splits'] += 1
            self._insert_into_internal(parent, mid_key, new_node)

    def _insert_into_internal(self, node: BLinkNode, key: str, child: BLinkNode) -> None:
        i = 0
        while i < len(node.keys) and node.keys[i] < key:
            i += 1
        node.keys.insert(i, key)
        node.children.insert(i + 1, child)
        if node.is_full():
            mid = len(node.keys) // 2
            new_node = BLinkNode(False, self.max_keys)
            new_node.keys = node.keys[mid + 1:]
            new_node.children = node.children[mid + 1:]
            new_node.next = node.next
            mid_key = node.keys[mid]
            node.keys = node.keys[:mid]
            node.children = node.children[:mid + 1]
            node.next = new_node
            self._stats['splits'] += 1
            parent = self._find_parent(self._root, node)
            if parent is None:
                self._create_new_root(node, mid_key, new_node)
            else:
                self._insert_into_internal(parent, mid_key, new_node)

    def _create_new_root(self, left: BLinkNode, key: str, right: BLinkNode) -> None:
        new_root = BLinkNode(False, self.max_keys)
        new_root.keys = [key]
        new_root.children = [left, right]
        self._root = new_root

    def _find_child(self, node: BLinkNode, key: str) -> BLinkNode:
        i = 0
        while i < len(node.keys) and node.keys[i] <= key:
            i += 1
        return node.children[i]

    def delete(self, key: str) -> bool:
        self._stats['deletes'] += 1
        node = self._search_to_leaf(key)
        with node.lock:
            for i, k in enumerate(node.keys):
                if k == key:
                    node.keys.pop(i)
                    node.values.pop(i)
                    return True
            return False

    def range_query(self, start: str, end: str) -> List[Tuple[str, Any]]:
        results: List[Tuple[str, Any]] = []
        node = self._search_to_leaf(start)
        while node:
            with node.lock:
                for i, k in enumerate(node.keys):
                    if start <= k <= end:
                        results.append((k, node.values[i]))
                    if k > end:
                        return results
            node = node.next
        return results

    def _search_to_leaf(self, key: str) -> BLinkNode:
        node = self._root
        while not node.is_leaf:
            with node.lock:
                child = self._find_child(node, key)
                while child is None:
                    node = node.next
                    child = self._find_child(node, key) if node else None
            node = child
        return node

    def _find_parent(self, current: BLinkNode, target: BLinkNode) -> Optional[BLinkNode]:
        if current.is_leaf or current is target:
            return None
        for child in current.children:
            if child is target:
                return current
            if not child.is_leaf:
                result = self._find_parent(child, target)
                if result:
                    return result
        return None

    def metrics(self) -> Dict[str, Any]:
        height = 0
        node = self._root
        while not node.is_leaf:
            height += 1
            if node.children:
                node = node.children[0]
            else:
                break
        total_nodes = self._count_nodes(self._root)
        return {
            'inserts': self._stats['inserts'],
            'deletes': self._stats['deletes'],
            'splits': self._stats['splits'],
            'queries': self._stats['queries'],
            'height': height + 1,
            'total_nodes': total_nodes,
            'root_keys': len(self._root.keys),
        }

    def _count_nodes(self, node: BLinkNode) -> int:
        count = 1
        if not node.is_leaf:
            for child in node.children:
                count += self._count_nodes(child)
        return count

    def to_dict(self) -> Dict[str, Any]:
        return {
            'max_keys': self.max_keys,
            'metrics': self.metrics(),
        }


class BLinkTreeEngine:
    """Top-level engine managing multiple B-Link tree instances."""

    def __init__(self) -> None:
        self._trees: Dict[str, BLinkTree] = {}
        self._default_tree: Optional[BLinkTree] = None
        self._lock = threading.Lock()

    def create(self, name: str = 'default', max_keys: int = 4) -> BLinkTree:
        tree = BLinkTree(max_keys)
        with self._lock:
            self._trees[name] = tree
            if name == 'default':
                self._default_tree = tree
        return tree

    def get(self, name: str = 'default') -> BLinkTree:
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

    def point_query(self, key: str, name: str = 'default') -> Any:
        return self.get(name).point_query(key)

    def insert(self, key: str, value: Any, name: str = 'default') -> None:
        self.get(name).insert(key, value)

    def delete(self, key: str, name: str = 'default') -> bool:
        return self.get(name).delete(key)

    def range_query(self, start: str, end: str,
                    name: str = 'default') -> List[Tuple[str, Any]]:
        return self.get(name).range_query(start, end)

    def metrics(self, name: str = 'default') -> Dict[str, Any]:
        return self.get(name).metrics()

    def summary(self) -> Dict[str, Any]:
        with self._lock:
            return {
                'tree_count': len(self._trees),
                'tree_names': list(self._trees.keys()),
            }
