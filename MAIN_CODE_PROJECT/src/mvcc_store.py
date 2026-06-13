"""Multi-Version Concurrency Control (MVCC) for snapshot-isolated state access."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
import threading
import time


class Version:
    __slots__ = ('value', 'txn_id', 'timestamp')

    def __init__(self, value: Any, txn_id: int) -> None:
        self.value = value
        self.txn_id = txn_id
        self.timestamp = time.monotonic()


class MVCCRecord:
    """A record with multiple versions, one per write transaction."""

    def __init__(self, initial_value: Any = None, txn_id: int = 0) -> None:
        self._versions: List[Version] = [Version(initial_value, txn_id)]
        self._lock = threading.Lock()

    def read(self, snapshot_txn: int) -> Any:
        with self._lock:
            for v in reversed(self._versions):
                if v.txn_id <= snapshot_txn:
                    return v.value
        return None

    def write(self, value: Any, txn_id: int) -> None:
        with self._lock:
            self._versions.append(Version(value, txn_id))

    def gc(self, oldest_active_txn: int, max_versions: int = 5) -> None:
        with self._lock:
            keep: List[Version] = []
            seen_txns: set[int] = set()
            for v in reversed(self._versions):
                if len(keep) < max_versions or v.txn_id > oldest_active_txn:
                    if v.txn_id not in seen_txns or v.txn_id > oldest_active_txn:
                        keep.append(v)
                        seen_txns.add(v.txn_id)
            self._versions = list(reversed(keep))

    @property
    def version_count(self) -> int:
        return len(self._versions)


class MVCCStore:
    """Thread-safe key-value store with MVCC snapshot isolation."""

    def __init__(self) -> None:
        self._data: Dict[str, MVCCRecord] = {}
        self._lock = threading.Lock()
        self._txn_counter = 0
        self._active_txns: Dict[int, float] = {}

    def begin_txn(self) -> int:
        with self._lock:
            self._txn_counter += 1
            txn_id = self._txn_counter
            self._active_txns[txn_id] = time.monotonic()
            return txn_id

    def commit_txn(self, txn_id: int) -> None:
        with self._lock:
            self._active_txns.pop(txn_id, None)

    def rollback_txn(self, txn_id: int) -> None:
        with self._lock:
            self._active_txns.pop(txn_id, None)
            for record in self._data.values():
                with record._lock:
                    record._versions = [v for v in record._versions if v.txn_id != txn_id]

    def get(self, key: str, snapshot_txn: int) -> Any:
        with self._lock:
            record = self._data.get(key)
        if record is None:
            return None
        return record.read(snapshot_txn)

    def set(self, key: str, value: Any, txn_id: int) -> None:
        with self._lock:
            if key not in self._data:
                self._data[key] = MVCCRecord()
            record = self._data[key]
        record.write(value, txn_id)

    def snapshot(self, txn_id: int) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        with self._lock:
            keys = list(self._data.keys())
        for key in keys:
            val = self.get(key, txn_id)
            if val is not None:
                result[key] = val
        return result

    def gc(self, max_versions: int = 5) -> None:
        with self._lock:
            oldest = min(self._active_txns.keys()) if self._active_txns else 0
            keys = list(self._data.keys())
        for key in keys:
            with self._lock:
                record = self._data.get(key)
            if record:
                record.gc(oldest, max_versions)
                if record.version_count == 0:
                    with self._lock:
                        self._data.pop(key, None)

    def close(self) -> None:
        self._data.clear()
        self._active_txns.clear()
