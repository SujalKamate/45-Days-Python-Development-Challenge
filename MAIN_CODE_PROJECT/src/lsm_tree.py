"""LSM-tree storage engine with tiered compaction, SSTable management, and Bloom-filter lookups."""

from __future__ import annotations

from typing import Any, Dict, Hashable, List, Optional, Tuple, Callable
import hashlib
import heapq
import json
import math
import os
import random
import struct
import threading
import time
from pathlib import Path


_TOMBSTONE = object()
_DELETED = object()


def _bloom_hash(item: str, seed: int, m: int) -> int:
    h = hashlib.sha256(f'{seed}:{item}'.encode('utf-8'))
    return struct.unpack('<I', h.digest()[:4])[0] % m


class BloomFilter:
    def __init__(self, capacity: int = 1000, fpr: float = 0.01) -> None:
        self.m = max(1, int(-capacity * math.log(fpr) / (math.log(2) ** 2)))
        self.k = max(1, int(round((self.m / max(capacity, 1)) * math.log(2))))
        self._bits = bytearray((self.m + 7) >> 3)
        self._seeds = [random.randint(0, 1 << 31) for _ in range(self.k)]

    def add(self, item: str) -> None:
        for s in self._seeds:
            idx = _bloom_hash(item, s, self.m)
            self._bits[idx >> 3] |= 1 << (idx & 7)

    def contains(self, item: str) -> bool:
        for s in self._seeds:
            idx = _bloom_hash(item, s, self.m)
            if not (self._bits[idx >> 3] & 1 << (idx & 7)):
                return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        return {'m': self.m, 'k': self.k, 'seeds': list(self._seeds), 'bits': list(self._bits)}

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> BloomFilter:
        bf = BloomFilter(1000, 0.01)
        bf.m = data['m']
        bf.k = data['k']
        bf._seeds = list(data['seeds'])
        bf._bits = bytearray(data['bits'])
        return bf


class WALEntry:
    def __init__(self, seq: int, op: str, key: str, value: Any = None) -> None:
        self.seq = seq
        self.op = op
        self.key = key
        self.value = value

    def to_dict(self) -> Dict[str, Any]:
        return {'seq': self.seq, 'op': self.op, 'key': self.key, 'value': self.value}


class WAL:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._entries: List[WALEntry] = []

    def append(self, entry: WALEntry) -> None:
        with self._lock:
            self._entries.append(entry)
            with open(self.path, 'a') as f:
                f.write(json.dumps(entry.to_dict()) + '\n')

    def replay(self) -> List[WALEntry]:
        if not self.path.exists():
            return []
        with self._lock:
            with open(self.path, 'r') as f:
                return [WALEntry(**json.loads(line)) for line in f if line.strip()]

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
            if self.path.exists():
                self.path.unlink()

    def size(self) -> int:
        return len(self._entries)


class SSTable:
    """Immutable sorted key-value table with embedded Bloom filter."""

    def __init__(self, level: int, data: Dict[str, Any],
                 bloom: Optional[BloomFilter] = None) -> None:
        self.level = level
        self._data = dict(sorted(data.items()))
        self._keys = list(self._data.keys())
        self._bloom = bloom or BloomFilter(max(len(data), 1), 0.01)
        if bloom is None:
            for k in self._data:
                self._bloom.add(k)
        self._uid = f'sst:{id(self):x}'

    def get(self, key: str) -> Any:
        if not self._bloom.contains(key):
            return None
        return self._data.get(key)

    def range_scan(self, start: str, end: str) -> List[Tuple[str, Any]]:
        result = []
        for k in self._keys:
            if start <= k <= end:
                result.append((k, self._data[k]))
            if k > end:
                break
        return result

    def keys(self) -> List[str]:
        return list(self._keys)

    def size(self) -> int:
        return len(self._data)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'level': self.level,
            'data': dict(self._data),
            'bloom': self._bloom.to_dict(),
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> SSTable:
        bf = BloomFilter.from_dict(data['bloom'])
        return SSTable(data['level'], data['data'], bf)


class LSMLevel:
    """A single level in the LSM tree containing zero or more SSTables."""

    def __init__(self, level: int, target_size: int) -> None:
        self.level = level
        self.target_size = target_size
        self._tables: List[SSTable] = []
        self._lock = threading.Lock()

    def add(self, table: SSTable) -> None:
        with self._lock:
            self._tables.append(table)

    def clear(self) -> None:
        with self._lock:
            self._tables.clear()

    def tables(self) -> List[SSTable]:
        with self._lock:
            return list(self._tables)

    def size(self) -> int:
        with self._lock:
            return sum(t.size() for t in self._tables)

    def is_overflow(self) -> bool:
        return self.size() > self.target_size


class LSMTree:
    """Log-structured merge-tree with memtable, WAL, leveled compaction, and Bloom-filter lookups."""

    def __init__(self, base_dir: str | Path = 'lsm_data',
                 memtable_size: int = 10000, level_factor: int = 10) -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.memtable_size = memtable_size
        self.level_factor = level_factor
        self._memtable: Dict[str, Any] = {}
        self._memtable_lock = threading.Lock()
        self._wal = WAL(self.base_dir / 'wal.log')
        self._levels: List[LSMLevel] = []
        self._levels.append(LSMLevel(0, memtable_size * 2))
        self._seq: int = 0
        self._lock = threading.Lock()
        self._compaction_lock = threading.Lock()
        self._stop_compaction = False
        self._stats: Dict[str, Any] = {
            'writes': 0, 'reads': 0, 'flushes': 0,
            'compactions': 0, 'read_amp': 0, 'write_amp': 0,
        }
        self._compaction_thread: Optional[threading.Thread] = None
        self._uid = f'lsm:{id(self):x}'
        self._replay_wal()

    def _replay_wal(self) -> None:
        for entry in self._wal.replay():
            if entry.op == 'put':
                self._memtable[entry.key] = entry.value
            elif entry.op == 'delete':
                self._memtable[entry.key] = _TOMBSTONE

    def put(self, key: str, value: Any) -> None:
        with self._memtable_lock:
            self._seq += 1
            self._wal.append(WALEntry(self._seq, 'put', key, value))
            self._memtable[key] = value
            self._stats['writes'] += 1
            if len(self._memtable) >= self.memtable_size:
                self._flush()

    def get(self, key: str) -> Any:
        self._stats['reads'] += 1
        with self._memtable_lock:
            if key in self._memtable:
                v = self._memtable[key]
                return None if v is _TOMBSTONE else v
        read_amp = 1
        for level in self._levels:
            for table in level.tables():
                read_amp += 1
                v = table.get(key)
                if v is not None:
                    self._stats['read_amp'] = (self._stats['read_amp'] + read_amp) / 2
                    return None if v is _TOMBSTONE else v
        self._stats['read_amp'] = (self._stats['read_amp'] + read_amp) / 2
        return None

    def delete(self, key: str) -> None:
        with self._memtable_lock:
            self._seq += 1
            self._wal.append(WALEntry(self._seq, 'delete', key))
            self._memtable[key] = _TOMBSTONE
            self._stats['writes'] += 1
            if len(self._memtable) >= self.memtable_size:
                self._flush()

    def range_scan(self, start: str, end: str) -> List[Tuple[str, Any]]:
        merged: Dict[str, Any] = {}
        with self._memtable_lock:
            for k, v in self._memtable.items():
                if start <= k <= end and v is not _TOMBSTONE:
                    merged[k] = v
        for level in self._levels:
            for table in level.tables():
                for k, v in table.range_scan(start, end):
                    if k not in merged and v is not _TOMBSTONE:
                        merged[k] = v
        return sorted(merged.items())

    def _flush(self) -> None:
        if not self._memtable:
            return
        data = dict(self._memtable)
        self._memtable.clear()
        self._wal.clear()
        table = SSTable(0, data)
        self._levels[0].add(table)
        self._stats['flushes'] += 1
        self._maybe_compact()

    def _maybe_compact(self) -> None:
        if self._compaction_lock.acquire(blocking=False):
            try:
                self._compact_level(0)
                for i in range(1, len(self._levels)):
                    if self._levels[i].is_overflow():
                        self._compact_level(i)
            finally:
                self._compaction_lock.release()

    def _compact_level(self, level: int) -> None:
        tables = self._levels[level].tables()
        if not tables:
            return
        merged: Dict[str, Any] = {}
        for t in reversed(tables):
            for k in t.keys():
                v = t.get(k)
                if v is not None and v is not _TOMBSTONE and k not in merged:
                    merged[k] = v
        self._levels[level].clear()
        if level + 1 >= len(self._levels):
            target = self.level_factor ** (level + 1) * self.memtable_size
            self._levels.append(LSMLevel(level + 1, target))
        target_level = self._levels[level + 1]
        new_table = SSTable(level + 1, merged)
        target_level.add(new_table)
        self._stats['compactions'] += 1
        self._stats['write_amp'] = (self._stats['write_amp'] + len(merged)) / 2

    def bloom_filter_path(self, key: str) -> Optional[str]:
        for level in self._levels:
            for i, table in enumerate(level.tables()):
                if table._bloom.contains(key):
                    return f'L{level.level}:sst_{i}'
        return None

    def metrics(self) -> Dict[str, Any]:
        total_tables = sum(len(l.tables()) for l in self._levels)
        total_size = sum(l.size() for l in self._levels)
        return {
            'writes': self._stats['writes'],
            'reads': self._stats['reads'],
            'flushes': self._stats['flushes'],
            'compactions': self._stats['compactions'],
            'read_amplification': round(self._stats['read_amp'], 2),
            'write_amplification': round(self._stats['write_amp'], 2),
            'memtable_size': len(self._memtable),
            'levels': len(self._levels),
            'total_tables': total_tables,
            'total_entries': total_size,
        }

    def close(self) -> None:
        with self._memtable_lock:
            if self._memtable:
                self._flush()


class LSMTreeEngine:
    """Top-level engine managing multiple LSM-tree instances."""

    def __init__(self) -> None:
        self._trees: Dict[str, LSMTree] = {}
        self._default_tree: Optional[LSMTree] = None
        self._lock = threading.Lock()

    def create(self, name: str = 'default', base_dir: str = 'lsm_data',
               memtable_size: int = 10000, level_factor: int = 10) -> LSMTree:
        path = str(Path(base_dir) / name)
        tree = LSMTree(path, memtable_size, level_factor)
        with self._lock:
            self._trees[name] = tree
            if name == 'default':
                self._default_tree = tree
        return tree

    def get(self, name: str = 'default') -> LSMTree:
        with self._lock:
            if name in self._trees:
                return self._trees[name]
            if self._default_tree is None:
                self._default_tree = self.create()
            return self._default_tree

    def remove(self, name: str) -> bool:
        with self._lock:
            if name in self._trees:
                self._trees[name].close()
                del self._trees[name]
                if name == 'default':
                    self._default_tree = None
                return True
            return False

    def list(self) -> List[str]:
        with self._lock:
            return list(self._trees.keys())

    def put(self, key: str, value: Any, name: str = 'default') -> None:
        self.get(name).put(key, value)

    def get_value(self, key: str, name: str = 'default') -> Any:
        return self.get(name).get(key)

    def delete(self, key: str, name: str = 'default') -> None:
        self.get(name).delete(key)

    def range_scan(self, start: str, end: str,
                   name: str = 'default') -> List[Tuple[str, Any]]:
        return self.get(name).range_scan(start, end)

    def bloom_filter_path(self, key: str, name: str = 'default') -> Optional[str]:
        return self.get(name).bloom_filter_path(key)

    def metrics(self, name: str = 'default') -> Dict[str, Any]:
        return self.get(name).metrics()

    def close(self, name: str = 'default') -> None:
        self.get(name).close()

    def summary(self) -> Dict[str, Any]:
        with self._lock:
            return {
                'tree_count': len(self._trees),
                'tree_names': list(self._trees.keys()),
            }
