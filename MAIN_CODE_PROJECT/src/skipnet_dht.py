"""SkipNet DHT simulation with multi-level routing rings and locality-aware lookups."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
import hashlib
import json
import math
import random
import struct
import threading
import time


_MAX_LEVELS = 16


def _hash_id(name: str) -> int:
    h = hashlib.sha256(name.encode('utf-8'))
    return struct.unpack('<Q', h.digest()[:8])[0]


class SkipNode:
    """A single SkipNet participant with routing tables and local key-value store."""

    def __init__(self, node_id: str, numeric_id: int, max_levels: int = _MAX_LEVELS) -> None:
        self.node_id = node_id
        self.numeric_id = numeric_id
        self.max_levels = max_levels
        self.left: List[Optional[SkipNode]] = [None] * max_levels
        self.right: List[Optional[SkipNode]] = [None] * max_levels
        self.level: int = 0
        self._data: Dict[str, Any] = {}
        self._lock = threading.Lock()
        self._uid = f'sn:{id(self):x}'

    def store(self, key: str, value: Any) -> None:
        with self._lock:
            self._data[key] = value

    def retrieve(self, key: str) -> Any:
        with self._lock:
            return self._data.get(key)

    def delete_key(self, key: str) -> bool:
        with self._lock:
            if key in self._data:
                del self._data[key]
                return True
            return False

    def data_size(self) -> int:
        return len(self._data)


class SkipNet:
    """Distributed hash table simulation with SkipNet multi-level routing rings."""

    def __init__(self, max_levels: int = _MAX_LEVELS) -> None:
        self.max_levels = max_levels
        self._nodes: Dict[str, SkipNode] = {}
        self._all_ids: List[int] = []
        self._lock = threading.Lock()
        self._stats: Dict[str, Any] = {
            'joins': 0, 'leaves': 0, 'stores': 0, 'lookups': 0,
            'total_hops': 0, 'route_count': 0,
        }
        self._uid = f'snet:{id(self):x}'

    def join(self, node_id: str) -> bool:
        with self._lock:
            if node_id in self._nodes:
                return False
            nid = _hash_id(node_id)
            node = SkipNode(node_id, nid, self.max_levels)
            self._nodes[node_id] = node
            self._all_ids.append(nid)
            self._all_ids.sort()
            self._recalculate_levels()
            self._stats['joins'] += 1
            return True

    def leave(self, node_id: str) -> bool:
        with self._lock:
            if node_id not in self._nodes:
                return False
            node = self._nodes[node_id]
            for key in list(node._data.keys()):
                successor = self._find_successor(node, _hash_id(key))
                if successor and successor.node_id != node_id:
                    successor.store(key, node._data[key])
            del self._nodes[node_id]
            self._all_ids = sorted(n.numeric_id for n in self._nodes.values())
            self._recalculate_levels()
            self._stats['leaves'] += 1
            return True

    def _recalculate_levels(self) -> None:
        sorted_nodes = sorted(self._nodes.values(), key=lambda n: n.numeric_id)
        if not sorted_nodes:
            return
        m = len(sorted_nodes)
        for node in sorted_nodes:
            for lv in range(self.max_levels):
                node.left[lv] = None
                node.right[lv] = None
        for lv in range(self.max_levels):
            step = 1 << lv
            if step >= m:
                break
            for i, node in enumerate(sorted_nodes):
                left_idx = (i - step) % m
                right_idx = (i + step) % m
                node.left[lv] = sorted_nodes[left_idx]
                node.right[lv] = sorted_nodes[right_idx]
                node.level = lv

    def store(self, key: str, value: Any, node_id: Optional[str] = None) -> bool:
        with self._lock:
            self._stats['stores'] += 1
            if node_id and node_id in self._nodes:
                self._nodes[node_id].store(key, value)
                return True
            target = self._find_responsible(key)
            if target:
                target.store(key, value)
                return True
            return False

    def lookup(self, key: str) -> Any:
        with self._lock:
            self._stats['lookups'] += 1
            target = self._find_responsible(key)
            if target:
                return target.retrieve(key)
            return None

    def route_hops(self, key: str) -> Dict[str, Any]:
        with self._lock:
            if not self._nodes:
                return {'found': False, 'hops': 0, 'path': []}
            kid = _hash_id(key)
            current = random.choice(list(self._nodes.values()))
            path = [current.node_id]
            hops = 0
            self._stats['route_count'] += 1
            while True:
                if current.retrieve(key) is not None:
                    break
                closest = self._find_closest_node(current, kid)
                if closest is None or closest.numeric_id == current.numeric_id:
                    break
                current = closest
                path.append(current.node_id)
                hops += 1
                if hops > self.max_levels * 3:
                    break
            found = current.retrieve(key) is not None
            self._stats['total_hops'] += hops
            return {'found': found, 'hops': hops, 'path': path, 'target': current.node_id}

    def _find_responsible(self, key: str) -> Optional[SkipNode]:
        if not self._nodes:
            return None
        kid = _hash_id(key)
        sorted_nodes = sorted(self._nodes.values(), key=lambda n: n.numeric_id)
        best = sorted_nodes[0]
        for node in sorted_nodes:
            if abs(node.numeric_id - kid) < abs(best.numeric_id - kid):
                best = node
        return best

    def _find_successor(self, node: SkipNode, target_id: int) -> Optional[SkipNode]:
        sorted_nodes = sorted(self._nodes.values(), key=lambda n: n.numeric_id)
        for n in sorted_nodes:
            if n.numeric_id > target_id:
                return n
        return sorted_nodes[0] if sorted_nodes else None

    def _find_closest_node(self, node: SkipNode, target_id: int) -> Optional[SkipNode]:
        best: Optional[SkipNode] = None
        best_dist = abs(node.numeric_id - target_id)
        for lv in range(node.level, -1, -1):
            for direction in ['right', 'left']:
                neighbor = getattr(node, direction)[lv]
                if neighbor:
                    dist = abs(neighbor.numeric_id - target_id)
                    if dist < best_dist:
                        best_dist = dist
                        best = neighbor
        return best

    def metrics(self) -> Dict[str, Any]:
        with self._lock:
            avg_hops = (self._stats['total_hops'] / self._stats['route_count']
                        if self._stats['route_count'] else 0)
            return {
                'nodes': len(self._nodes),
                'joins': self._stats['joins'],
                'leaves': self._stats['leaves'],
                'stores': self._stats['stores'],
                'lookups': self._stats['lookups'],
                'avg_hops': round(avg_hops, 2),
                'route_count': self._stats['route_count'],
                'max_levels': self.max_levels,
            }

    def node_list(self) -> List[str]:
        with self._lock:
            return list(self._nodes.keys())


class SkipNetEngine:
    """Top-level engine managing multiple SkipNet instances."""

    def __init__(self) -> None:
        self._nets: Dict[str, SkipNet] = {}
        self._default_net: Optional[SkipNet] = None
        self._lock = threading.Lock()

    def create(self, name: str = 'default', max_levels: int = _MAX_LEVELS) -> SkipNet:
        net = SkipNet(max_levels)
        with self._lock:
            self._nets[name] = net
            if name == 'default':
                self._default_net = net
        return net

    def get(self, name: str = 'default') -> SkipNet:
        with self._lock:
            if name in self._nets:
                return self._nets[name]
            if self._default_net is None:
                self._default_net = self.create()
            return self._default_net

    def remove(self, name: str) -> bool:
        with self._lock:
            if name in self._nets:
                del self._nets[name]
                if name == 'default':
                    self._default_net = None
                return True
            return False

    def list(self) -> List[str]:
        with self._lock:
            return list(self._nets.keys())

    def join(self, node_id: str, net_name: str = 'default') -> bool:
        return self.get(net_name).join(node_id)

    def leave(self, node_id: str, net_name: str = 'default') -> bool:
        return self.get(net_name).leave(node_id)

    def store(self, key: str, value: Any, node_id: Optional[str] = None,
              net_name: str = 'default') -> bool:
        return self.get(net_name).store(key, value, node_id)

    def lookup(self, key: str, net_name: str = 'default') -> Any:
        return self.get(net_name).lookup(key)

    def route_hops(self, key: str, net_name: str = 'default') -> Dict[str, Any]:
        return self.get(net_name).route_hops(key)

    def metrics(self, net_name: str = 'default') -> Dict[str, Any]:
        return self.get(net_name).metrics()

    def summary(self) -> Dict[str, Any]:
        with self._lock:
            return {
                'net_count': len(self._nets),
                'net_names': list(self._nets.keys()),
            }
