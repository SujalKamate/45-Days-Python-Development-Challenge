"""Optimistic concurrency — versioned state with CAS, lock-free reads, and retry."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple, TypeVar
import threading
import time


T = TypeVar('T')


class VersionedCell:
    """A single value protected by a version counter for optimistic CAS."""

    __slots__ = ('_value', '_version', '_lock')

    def __init__(self, value: Any = None) -> None:
        self._value = value
        self._version = 0
        self._lock = threading.Lock()

    def read(self) -> Tuple[int, Any]:
        return self._version, self._value

    def cas(self, expected_version: int, new_value: Any) -> bool:
        with self._lock:
            if self._version != expected_version:
                return False
            self._version += 1
            self._value = new_value
            return True

    @property
    def version(self) -> int:
        return self._version


class OptimisticStore:
    """Lock-free key-value store using per-key versioned CAS.

    Reads are wait-free. Writes use compare-and-swap with retry.
    """

    def __init__(self) -> None:
        self._cells: Dict[str, VersionedCell] = {}
        self._lock = threading.Lock()

    def _get_cell(self, key: str) -> VersionedCell:
        with self._lock:
            if key not in self._cells:
                self._cells[key] = VersionedCell()
            return self._cells[key]

    def get(self, key: str) -> Optional[Any]:
        _, value = self._get_cell(key).read()
        return value

    def get_versioned(self, key: str) -> Tuple[int, Optional[Any]]:
        return self._get_cell(key).read()

    def set(self, key: str, value: Any, retries: int = 100) -> bool:
        cell = self._get_cell(key)
        for _ in range(retries):
            version, _ = cell.read()
            if cell.cas(version, value):
                return True
            time.sleep(0)
        return False

    def update(self, key: str, fn: Callable[[Optional[Any]], Any],
               retries: int = 100) -> bool:
        cell = self._get_cell(key)
        for _ in range(retries):
            version, current = cell.read()
            new_value = fn(current)
            if cell.cas(version, new_value):
                return True
            time.sleep(0)
        return False

    def delete(self, key: str, retries: int = 100) -> bool:
        cell = self._get_cell(key)
        for _ in range(retries):
            version, _ = cell.read()
            if cell.cas(version, None):
                return True
            time.sleep(0)
        return False

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            keys = list(self._cells.keys())
        result: Dict[str, Any] = {}
        for key in keys:
            val = self.get(key)
            if val is not None:
                result[key] = val
        return result

    def keys(self) -> List[str]:
        with self._lock:
            return list(self._cells.keys())

    def clear(self) -> None:
        with self._lock:
            self._cells.clear()


class OptimisticReadWriteLock:
    """Readers-writer lock using optimistic versioning.

    Readers are never blocked by other readers.
    Writers only block when a write is in progress.
    """

    def __init__(self) -> None:
        self._state = 0
        self._lock = threading.Lock()
        self._write_owner = None

    def read_acquire(self) -> int:
        while True:
            state = self._state
            if state >= 0:
                if self._cas_state(state, state + 1):
                    return state
            time.sleep(0)

    def read_release(self, token: int) -> None:
        self._cas_state(self._state, self._state - 1)

    def write_acquire(self) -> None:
        me = threading.current_thread()
        while True:
            if self._cas_state(0, -1):
                self._write_owner = me
                return
            time.sleep(0)

    def write_release(self) -> None:
        self._write_owner = None
        self._cas_state(-1, 0)

    def _cas_state(self, expected: int, new: int) -> bool:
        with self._lock:
            if self._state != expected:
                return False
            self._state = new
            return True


class RetryExhausted(Exception):
    """Raised when optimistic retry limit is exceeded."""
