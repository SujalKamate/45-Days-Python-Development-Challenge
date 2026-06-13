"""Horizontally-sharded state store with consistent hashing for balanced key distribution."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Set, Tuple
import hashlib
import threading


def _hash_key(key: str) -> int:
    return int(hashlib.sha256(key.encode('utf-8')).hexdigest()[:16], 16)


class Shard:
    """A single storage shard — an isolated key-value partition."""

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

    def items(self) -> List[Tuple[str, Any]]:
        with self._lock:
            return list(self._data.items())

    def keys(self) -> Set[str]:
        with self._lock:
            return set(self._data.keys())

    def drain(self) -> Dict[str, Any]:
        with self._lock:
            data = dict(self._data)
            self._data.clear()
            return data

    def load(self, data: Dict[str, Any]) -> None:
        with self._lock:
            self._data.update(data)

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._data)


class ConsistentHashRing:
    """Consistent hashing ring for balanced key-to-shard routing with minimal redistribution on reshard."""

    def __init__(self, virtual_nodes: int = 64) -> None:
        self._virtual_nodes = virtual_nodes
        self._ring: Dict[int, int] = {}  # position -> shard_id
        self._sorted_positions: List[int] = []
        self._lock = threading.Lock()

    def _make_virtual_positions(self, shard_id: int) -> List[int]:
        positions = []
        for i in range(self._virtual_nodes):
            pos = _hash_key(f'shard:{shard_id}:vnode:{i}')
            positions.append(pos)
        return positions

    def add_shard(self, shard_id: int) -> None:
        with self._lock:
            for pos in self._make_virtual_positions(shard_id):
                self._ring[pos] = shard_id
            self._sorted_positions = sorted(self._ring.keys())

    def remove_shard(self, shard_id: int) -> None:
        with self._lock:
            keys_to_remove = [pos for pos, sid in self._ring.items() if sid == shard_id]
            for pos in keys_to_remove:
                del self._ring[pos]
            self._sorted_positions = sorted(self._ring.keys())

    def get_shard(self, key: str) -> Optional[int]:
        with self._lock:
            if not self._sorted_positions:
                return None
            pos = _hash_key(key)
            import bisect
            idx = bisect.bisect_right(self._sorted_positions, pos)
            if idx == len(self._sorted_positions):
                idx = 0
            return self._ring[self._sorted_positions[idx]]

    @property
    def shard_count(self) -> int:
        with self._lock:
            return len(set(self._ring.values()))


class ShardedStore:
    """Key-value store that distributes data across shards via consistent hashing.

    Supports dynamic add/remove of shards with minimal key redistribution.
    """

    def __init__(self, initial_shards: int = 4, virtual_nodes: int = 64) -> None:
        self._shards: Dict[int, Shard] = {}
        self._ring = ConsistentHashRing(virtual_nodes)
        self._lock = threading.Lock()
        self._next_shard_id = 0
        for _ in range(initial_shards):
            self._add_shard()

    def _add_shard(self) -> int:
        sid = self._next_shard_id
        self._next_shard_id += 1
        self._shards[sid] = Shard(sid)
        self._ring.add_shard(sid)
        return sid

    def _shard_for_key(self, key: str) -> Optional[Shard]:
        sid = self._ring.get_shard(key)
        if sid is not None:
            return self._shards.get(sid)
        return None

    def get(self, key: str) -> Optional[Any]:
        shard = self._shard_for_key(key)
        if shard is None:
            return None
        return shard.get(key)

    def set(self, key: str, value: Any) -> None:
        shard = self._shard_for_key(key)
        if shard is not None:
            shard.set(key, value)

    def delete(self, key: str) -> bool:
        shard = self._shard_for_key(key)
        if shard is None:
            return False
        return shard.delete(key)

    def keys(self) -> Set[str]:
        result: Set[str] = set()
        for shard in self._shards.values():
            result.update(shard.keys())
        return result

    def items(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        for shard in self._shards.values():
            for k, v in shard.items():
                result[k] = v
        return result

    def add_shard(self) -> int:
        with self._lock:
            return self._add_shard()

    def remove_shard(self) -> int:
        with self._lock:
            if len(self._shards) <= 1:
                return 0
            sid = max(self._shards.keys())
            old_shard = self._shards.pop(sid, None)
            self._ring.remove_shard(sid)
            if old_shard:
                for key, value in old_shard.drain().items():
                    self.set(key, value)
            return sid

    @property
    def shard_count(self) -> int:
        return len(self._shards)

    @property
    def size(self) -> int:
        return sum(s.size for s in self._shards.values())

    def shard_sizes(self) -> Dict[int, int]:
        return {s.id: s.size for s in self._shards.values()}
