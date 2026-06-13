"""Consistent-hashing state sharding for scalable distributed storage with virtual nodes."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple
import bisect
import hashlib
import threading


def _sha256_int(key: str) -> int:
    return int(hashlib.sha256(key.encode('utf-8')).hexdigest()[:16], 16)


class VirtualNode:
    __slots__ = ('shard_id', 'weight')

    def __init__(self, shard_id: int, weight: int = 1) -> None:
        self.shard_id = shard_id
        self.weight = weight


class ConsistentHashRing:
    """Consistent hash ring with virtual nodes for balanced key distribution.

    Each physical shard maps to ``virtual_nodes`` positions on the ring.
    Higher *weight* values increase virtual node count proportionally.
    """

    def __init__(self, virtual_nodes: int = 128) -> None:
        self._vnode_count = virtual_nodes
        self._ring: Dict[int, VirtualNode] = {}
        self._positions: List[int] = []
        self._shard_weights: Dict[int, int] = {}
        self._lock = threading.Lock()

    def _vnodes_for(self, shard_id: int, weight: int) -> List[int]:
        count = max(1, self._vnode_count * weight)
        return [_sha256_int(f'{shard_id}:vnode:{i}') for i in range(count)]

    def add_shard(self, shard_id: int, weight: int = 1) -> None:
        with self._lock:
            self._shard_weights[shard_id] = weight
            for pos in self._vnodes_for(shard_id, weight):
                self._ring[pos] = VirtualNode(shard_id, weight)
            self._positions = sorted(self._ring.keys())

    def remove_shard(self, shard_id: int) -> None:
        with self._lock:
            self._shard_weights.pop(shard_id, None)
            for pos in list(self._ring.keys()):
                if self._ring[pos].shard_id == shard_id:
                    del self._ring[pos]
            self._positions = sorted(self._ring.keys())

    def update_weight(self, shard_id: int, weight: int) -> None:
        self.remove_shard(shard_id)
        self.add_shard(shard_id, weight)

    def get_shard(self, key: str) -> Optional[int]:
        with self._lock:
            if not self._positions:
                return None
            pos = _sha256_int(key)
            idx = bisect.bisect_right(self._positions, pos)
            if idx == len(self._positions):
                idx = 0
            return self._ring[self._positions[idx]].shard_id

    @property
    def shards(self) -> Set[int]:
        return set(self._shard_weights.keys())

    @property
    def shard_count(self) -> int:
        return len(self._shard_weights)


class ShardBucket:
    """A single shard bucket holding key-value data."""

    def __init__(self, shard_id: int) -> None:
        self.id = shard_id
        self._data: Dict[str, Any] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            return self._data.get(key)

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._data[key] = value

    def delete(self, key: str) -> bool:
        with self._lock:
            return self._data.pop(key, None) is not None

    def all_items(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._data)

    def drain(self) -> Dict[str, Any]:
        with self._lock:
            data = dict(self._data)
            self._data.clear()
            return data

    def load(self, items: Dict[str, Any]) -> None:
        with self._lock:
            self._data.update(items)

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._data)


class ConsistentHashStore:
    """Horizontally scalable key-value store using consistent hashing.

    Supports weighted shards, virtual nodes, and dynamic resharding.
    """

    def __init__(self, initial_shards: int = 4, virtual_nodes: int = 128) -> None:
        self._buckets: Dict[int, ShardBucket] = {}
        self._ring = ConsistentHashRing(virtual_nodes)
        self._lock = threading.Lock()
        self._next_id = 0
        for _ in range(initial_shards):
            self.add_shard()

    def add_shard(self, weight: int = 1) -> int:
        with self._lock:
            sid = self._next_id
            self._next_id += 1
            self._buckets[sid] = ShardBucket(sid)
            self._ring.add_shard(sid, weight)
            return sid

    def remove_shard(self) -> int:
        with self._lock:
            if len(self._buckets) <= 1:
                return -1
            sid = max(self._buckets.keys())
            bucket = self._buckets.pop(sid, None)
            self._ring.remove_shard(sid)
            if bucket:
                for key, value in bucket.drain().items():
                    target = self._ring.get_shard(key)
                    if target is not None and target in self._buckets:
                        self._buckets[target].set(key, value)
            return sid

    def _bucket_for(self, key: str) -> Optional[ShardBucket]:
        sid = self._ring.get_shard(key)
        if sid is not None:
            return self._buckets.get(sid)
        return None

    def get(self, key: str) -> Optional[Any]:
        bucket = self._bucket_for(key)
        return bucket.get(key) if bucket else None

    def set(self, key: str, value: Any) -> None:
        bucket = self._bucket_for(key)
        if bucket:
            bucket.set(key, value)

    def delete(self, key: str) -> bool:
        bucket = self._bucket_for(key)
        return bucket.delete(key) if bucket else False

    def all_keys(self) -> Set[str]:
        result: Set[str] = set()
        for b in self._buckets.values():
            result.update(b.all_items().keys())
        return result

    def all_items(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        for b in self._buckets.values():
            result.update(b.all_items())
        return result

    def shard_sizes(self) -> Dict[int, int]:
        return {s.id: s.size for s in self._buckets.values()}

    def rebalance(self) -> int:
        moved = 0
        for bucket in list(self._buckets.values()):
            for key, value in bucket.all_items().items():
                target_sid = self._ring.get_shard(key)
                if target_sid is not None and target_sid != bucket.id:
                    target = self._buckets.get(target_sid)
                    if target:
                        target.set(key, value)
                        bucket.delete(key)
                        moved += 1
        return moved

    @property
    def shard_count(self) -> int:
        return len(self._buckets)

    @property
    def total_keys(self) -> int:
        return sum(b.size for b in self._buckets.values())
