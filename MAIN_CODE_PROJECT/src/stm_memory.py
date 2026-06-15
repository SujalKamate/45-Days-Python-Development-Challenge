"""Software transactional memory with optimistic conflict detection and retry semantics."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Set, Tuple
import threading
import time


class STMError(Exception):
    pass


class RetryException(STMError):
    pass


class AbortException(STMError):
    pass


class TVar:
    """Versioned transactional memory variable."""

    def __init__(self, value: Any) -> None:
        self._value = value
        self._version: int = 0
        self._lock = threading.Lock()
        self._uid = f'tv:{id(self):x}'

    def _read(self) -> Tuple[Any, int]:
        with self._lock:
            return self._value, self._version

    def _write(self, value: Any, version: int) -> None:
        with self._lock:
            self._value = value
            self._version = version


class Transaction:
    """In-flight transaction tracking read set, write set, and status."""

    def __init__(self, stm: STM) -> None:
        self.stm = stm
        self.read_set: Dict[TVar, int] = {}
        self.write_set: Dict[TVar, Any] = {}
        self._retry_count: int = 0
        self._committed: bool = False

    def read(self, tvar: TVar) -> Any:
        if tvar in self.write_set:
            return self.write_set[tvar]
        val, ver = tvar._read()
        if tvar not in self.read_set:
            self.read_set[tvar] = ver
        return val

    def write(self, tvar: TVar, value: Any) -> None:
        if tvar not in self.read_set:
            _, ver = tvar._read()
            self.read_set[tvar] = ver
        self.write_set[tvar] = value

    def validate(self) -> bool:
        for tvar, ver in self.read_set.items():
            _, current_ver = tvar._read()
            if current_ver != ver:
                return False
        return True

    def commit(self) -> bool:
        if self._committed:
            return True
        self._committed = True
        with self.stm._global_lock:
            if not self.validate():
                return False
            for tvar, value in self.write_set.items():
                _, ver = tvar._read()
                tvar._write(value, ver + 1)
            self.stm._stats['commits'] += 1
            return True

    def abort(self) -> None:
        self._committed = False
        self.read_set.clear()
        self.write_set.clear()


class STM:
    """Software transactional memory with retry, or_else, and conflict detection."""

    def __init__(self, max_retries: int = 10) -> None:
        self.max_retries = max_retries
        self._global_lock = threading.Lock()
        self._stats: Dict[str, Any] = {
            'commits': 0, 'aborts': 0, 'retries': 0, 'conflicts': 0,
        }
        self._conflict_graph: Dict[str, Set[str]] = {}
        self._uid = f'stm:{id(self):x}'

    def TVar(self, value: Any) -> TVar:
        return TVar(value)

    def transaction(self, block: Callable[[Transaction], Any]) -> Any:
        last_error: Optional[Exception] = None
        for attempt in range(self.max_retries):
            t = Transaction(self)
            try:
                result = block(t)
                if t.commit():
                    return result
                self._stats['conflicts'] += 1
                self._stats['retries'] += 1
                t.abort()
            except RetryException:
                self._stats['retries'] += 1
                t.abort()
                continue
            except AbortException:
                self._stats['aborts'] += 1
                t.abort()
                raise
            except Exception as e:
                self._stats['aborts'] += 1
                t.abort()
                last_error = e
                break
        raise last_error or STMError('Transaction failed after max retries')

    def retry(self, t: Transaction) -> None:
        raise RetryException()

    def or_else(self, first: Callable[[Transaction], Any],
                second: Callable[[Transaction], Any]) -> Callable[[Transaction], Any]:
        def wrapper(t: Transaction) -> Any:
            try:
                return first(t)
            except RetryException:
                return second(t)
        return wrapper

    def read(self, t: Transaction, tvar: TVar) -> Any:
        return t.read(tvar)

    def write(self, t: Transaction, tvar: TVar, value: Any) -> None:
        t.write(tvar, value)

    def conflict_graph_stats(self) -> Dict[str, Any]:
        with self._global_lock:
            edges = sum(len(v) for v in self._conflict_graph.values())
            return {
                'nodes': len(self._conflict_graph),
                'edges': edges,
            }

    def commit_count(self) -> int:
        return self._stats['commits']

    def abort_count(self) -> int:
        return self._stats['aborts']

    def metrics(self) -> Dict[str, Any]:
        return {
            'commits': self._stats['commits'],
            'aborts': self._stats['aborts'],
            'retries': self._stats['retries'],
            'conflicts': self._stats['conflicts'],
            'max_retries': self.max_retries,
            'conflict_graph': self.conflict_graph_stats(),
        }


class STMEngine:
    """Top-level engine managing multiple STM instances."""

    def __init__(self) -> None:
        self._instances: Dict[str, STM] = {}
        self._default_stm: Optional[STM] = None
        self._lock = threading.Lock()

    def create(self, name: str = 'default', max_retries: int = 10) -> STM:
        stm = STM(max_retries)
        with self._lock:
            self._instances[name] = stm
            if name == 'default':
                self._default_stm = stm
        return stm

    def get(self, name: str = 'default') -> STM:
        with self._lock:
            if name in self._instances:
                return self._instances[name]
            if self._default_stm is None:
                self._default_stm = self.create()
            return self._default_stm

    def remove(self, name: str) -> bool:
        with self._lock:
            if name in self._instances:
                del self._instances[name]
                if name == 'default':
                    self._default_stm = None
                return True
            return False

    def list(self) -> List[str]:
        with self._lock:
            return list(self._instances.keys())

    def TVar(self, value: Any, name: str = 'default') -> TVar:
        return self.get(name).TVar(value)

    def transaction(self, block: Callable[[Transaction], Any],
                    name: str = 'default') -> Any:
        return self.get(name).transaction(block)

    def metrics(self, name: str = 'default') -> Dict[str, Any]:
        return self.get(name).metrics()

    def commit_count(self, name: str = 'default') -> int:
        return self.get(name).commit_count()

    def abort_count(self, name: str = 'default') -> int:
        return self.get(name).abort_count()

    def conflict_graph_stats(self, name: str = 'default') -> Dict[str, Any]:
        return self.get(name).conflict_graph_stats()

    def summary(self) -> Dict[str, Any]:
        with self._lock:
            return {
                'stm_count': len(self._instances),
                'stm_names': list(self._instances.keys()),
            }
