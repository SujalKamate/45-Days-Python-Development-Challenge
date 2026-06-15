"""Patricia trie (radix tree) for prefix search, longest-prefix matching, and autocomplete."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
import threading
import time


class RadixNode:
    """A single Patricia trie node storing a path fragment and optional value."""

    def __init__(self, path: str = '', value: Any = None) -> None:
        self.path = path
        self.value = value
        self.has_value: bool = value is not None
        self.children: Dict[str, RadixNode] = {}
        self._uid = f'rx:{id(self):x}'


class RadixTree:
    """Space-optimized Patricia trie with path compression, longest-prefix matching, and prefix scan."""

    def __init__(self) -> None:
        self._root = RadixNode()
        self._lock = threading.Lock()
        self._size: int = 0
        self._uid = f'rt:{id(self):x}'

    def insert(self, key: str, value: Any) -> None:
        if not key:
            return
        with self._lock:
            self._insert_internal(self._root, key, value)
            self._size += 1

    def _insert_internal(self, node: RadixNode, key: str, value: Any) -> None:
        if not key:
            node.value = value
            node.has_value = True
            return
        first = key[0]
        if first in node.children:
            child = node.children[first]
            common = self._common_prefix(key, child.path)
            if common == len(child.path):
                self._insert_internal(child, key[common:], value)
            else:
                split_node = RadixNode(child.path[common:], child.value)
                split_node.has_value = child.has_value
                split_node.children = child.children
                child.path = child.path[:common]
                child.value = None
                child.has_value = False
                child.children = {split_node.path[0]: split_node}
                remainder = key[common:]
                if remainder:
                    child.children[remainder[0]] = RadixNode(remainder, value)
                    child.children[remainder[0]].has_value = True
                else:
                    child.value = value
                    child.has_value = True
        else:
            node.children[first] = RadixNode(key, value)
            node.children[first].has_value = True

    def lookup(self, key: str) -> Any:
        if not key:
            return None
        with self._lock:
            node = self._find_node(self._root, key)
            return node.value if node and node.has_value else None

    def _find_node(self, node: RadixNode, key: str) -> Optional[RadixNode]:
        if not key:
            return node if node.has_value else None
        first = key[0]
        child = node.children.get(first)
        if not child:
            return None
        if key.startswith(child.path):
            return self._find_node(child, key[len(child.path):])
        return None

    def longest_prefix(self, key: str) -> Optional[Tuple[str, Any]]:
        if not key:
            return None
        with self._lock:
            return self._longest_prefix_internal(self._root, key, '', None)

    def _longest_prefix_internal(self, node: RadixNode, key: str,
                                  prefix: str, best: Optional[Tuple[str, Any]]) -> Optional[Tuple[str, Any]]:
        if node.has_value:
            best = (prefix, node.value)
        if not key:
            return best
        first = key[0]
        child = node.children.get(first)
        if not child:
            return best
        if key.startswith(child.path):
            return self._longest_prefix_internal(
                child, key[len(child.path):], prefix + child.path, best)
        cp = self._common_prefix(key, child.path)
        if cp > 0:
            return best if node.has_value else best
        return best

    def prefix_scan(self, prefix: str) -> List[Tuple[str, Any]]:
        results: List[Tuple[str, Any]] = []
        if not prefix:
            return results
        with self._lock:
            node = self._root
            remaining = prefix
            while remaining:
                first = remaining[0]
                child = node.children.get(first)
                if not child:
                    return results
                if remaining.startswith(child.path):
                    remaining = remaining[len(child.path):]
                    node = child
                else:
                    cp = self._common_prefix(remaining, child.path)
                    if cp == len(remaining):
                        remaining = ''
                        node = child
                    else:
                        return results
            self._collect(node, prefix, results)
        return results

    def _collect(self, node: RadixNode, prefix: str, results: List[Tuple[str, Any]]) -> None:
        if node.has_value:
            results.append((prefix, node.value))
        for first in sorted(node.children.keys()):
            child = node.children[first]
            self._collect(child, prefix + child.path, results)

    def delete(self, key: str) -> bool:
        if not key:
            return False
        with self._lock:
            result = self._delete_internal(self._root, key)
            if result is not False:
                self._size -= 1
                return True
            return False

    def _delete_internal(self, node: RadixNode, key: str) -> Any:
        if not key:
            if node.has_value:
                node.value = None
                node.has_value = False
                if len(node.children) == 1 and not node.path:
                    pass
                return True
            return False
        first = key[0]
        child = node.children.get(first)
        if not child:
            return False
        if key.startswith(child.path):
            result = self._delete_internal(child, key[len(child.path):])
            if result and not child.has_value and len(child.children) == 1:
                only_child = next(iter(child.children.values()))
                child.path += only_child.path
                child.value = only_child.value
                child.has_value = only_child.has_value
                child.children = only_child.children
            if result and not child.has_value and not child.children:
                del node.children[first]
            return result
        return False

    def _common_prefix(self, a: str, b: str) -> int:
        i = 0
        while i < len(a) and i < len(b) and a[i] == b[i]:
            i += 1
        return i

    def size(self) -> int:
        return self._size

    def clear(self) -> None:
        with self._lock:
            self._root = RadixNode()
            self._size = 0

    def metrics(self) -> Dict[str, Any]:
        total_nodes = [0]
        total_path_len = [0]
        self._count_nodes(self._root, total_nodes, total_path_len)
        return {
            'entries': self._size,
            'total_nodes': total_nodes[0],
            'avg_path_len': round(total_path_len[0] / total_nodes[0], 2) if total_nodes[0] else 0,
        }

    def _count_nodes(self, node: RadixNode, count: List[int], path_len: List[int]) -> None:
        count[0] += 1
        path_len[0] += len(node.path)
        for child in node.children.values():
            self._count_nodes(child, count, path_len)

    def to_dict(self) -> Dict[str, Any]:
        return {'metrics': self.metrics()}


class RadixTreeEngine:
    """Top-level engine managing multiple radix trees."""

    def __init__(self) -> None:
        self._trees: Dict[str, RadixTree] = {}
        self._default_tree: Optional[RadixTree] = None
        self._lock = threading.Lock()

    def create(self, name: str = 'default') -> RadixTree:
        tree = RadixTree()
        with self._lock:
            self._trees[name] = tree
            if name == 'default':
                self._default_tree = tree
        return tree

    def get(self, name: str = 'default') -> RadixTree:
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

    def insert(self, key: str, value: Any, name: str = 'default') -> None:
        self.get(name).insert(key, value)

    def lookup(self, key: str, name: str = 'default') -> Any:
        return self.get(name).lookup(key)

    def longest_prefix(self, key: str, name: str = 'default') -> Optional[Tuple[str, Any]]:
        return self.get(name).longest_prefix(key)

    def prefix_scan(self, prefix: str, name: str = 'default') -> List[Tuple[str, Any]]:
        return self.get(name).prefix_scan(prefix)

    def delete(self, key: str, name: str = 'default') -> bool:
        return self.get(name).delete(key)

    def metrics(self, name: str = 'default') -> Dict[str, Any]:
        return self.get(name).metrics()

    def summary(self) -> Dict[str, Any]:
        with self._lock:
            return {
                'tree_count': len(self._trees),
                'tree_names': list(self._trees.keys()),
            }
