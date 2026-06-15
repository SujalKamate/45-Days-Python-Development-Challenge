"""Bulkhead resource isolation and capacity protection framework."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional
import datetime
import json
import os
import threading
import time
import uuid


class BulkheadCapacityExceededError(Exception):
    """Raised when a bulkhead group has no available capacity."""
    pass


class BulkheadGroup:
    """Isolated capacity pool for a workload category."""

    def __init__(self, name: str, max_concurrent: int = 10,
                 queue_size: int = 20) -> None:
        self.name = name
        self.max_concurrent = max_concurrent
        self.queue_size = queue_size
        self._semaphore = threading.Semaphore(max_concurrent)
        self._lock = threading.Lock()
        self._active_count = 0
        self._queue_count = 0
        self._total_processed = 0
        self._total_rejected = 0
        self._total_time_s = 0.0
        self._peak_active = 0

    def acquire(self, timeout: float = 0) -> bool:
        if timeout > 0:
            acquired = self._semaphore.acquire(timeout=timeout)
        else:
            with self._lock:
                if self._active_count >= self.max_concurrent:
                    if self._queue_count < self.queue_size:
                        self._queue_count += 1
                    else:
                        self._total_rejected += 1
                        return False
            acquired = self._semaphore.acquire(timeout=1.0)
            if not acquired:
                with self._lock:
                    self._total_rejected += 1
                return False

        with self._lock:
            self._active_count += 1
            self._total_processed += 1
            if self._queue_count > 0:
                self._queue_count -= 1
            if self._active_count > self._peak_active:
                self._peak_active = self._active_count
        return True

    def release(self) -> None:
        with self._lock:
            self._active_count -= 1
        self._semaphore.release()

    @property
    def available(self) -> int:
        return self.max_concurrent - self._active_count

    @property
    def utilization_pct(self) -> float:
        return (self._active_count / self.max_concurrent) * 100.0 if self.max_concurrent > 0 else 0.0

    def metrics(self) -> Dict[str, Any]:
        with self._lock:
            return {
                'name': self.name,
                'max_concurrent': self.max_concurrent,
                'queue_size': self.queue_size,
                'active': self._active_count,
                'available': self.max_concurrent - self._active_count,
                'queue_depth': self._queue_count,
                'utilization_pct': round(self.utilization_pct, 1),
                'peak_active': self._peak_active,
                'total_processed': self._total_processed,
                'total_rejected': self._total_rejected,
                'avg_time_s': round(self._total_time_s / self._total_processed, 3) if self._total_processed else 0.0,
            }


class BulkheadRegistry:
    """Registry of named bulkhead groups."""

    def __init__(self) -> None:
        self._groups: Dict[str, BulkheadGroup] = {}
        self._lock = threading.Lock()
        self._create_defaults()

    def _create_defaults(self) -> None:
        self.create_group('io', 20, 50)
        self.create_group('cpu', 10, 20)
        self.create_group('network', 15, 30)

    def create_group(self, name: str, max_concurrent: int = 10,
                     queue_size: int = 20) -> BulkheadGroup:
        with self._lock:
            group = BulkheadGroup(name, max_concurrent, queue_size)
            self._groups[name] = group
            return group

    def get(self, name: str) -> Optional[BulkheadGroup]:
        with self._lock:
            return self._groups.get(name)

    def get_or_create(self, name: str, max_concurrent: int = 10,
                      queue_size: int = 20) -> BulkheadGroup:
        with self._lock:
            if name not in self._groups:
                self._groups[name] = BulkheadGroup(name, max_concurrent, queue_size)
            return self._groups[name]

    def list_groups(self) -> Dict[str, Dict[str, Any]]:
        with self._lock:
            return {n: g.metrics() for n, g in self._groups.items()}

    def summary(self) -> Dict[str, Any]:
        with self._lock:
            total = len(self._groups)
            total_rejected = sum(g._total_rejected for g in self._groups.values())
            total_processed = sum(g._total_processed for g in self._groups.values())
            active_overall = sum(g._active_count for g in self._groups.values())
            return {
                'total_groups': total,
                'active_overall': active_overall,
                'total_processed': total_processed,
                'total_rejected': total_rejected,
                'groups': self.list_groups(),
            }


class BulkheadExecutor:
    """Execute callables within a bulkhead group capacity."""

    def __init__(self, registry: BulkheadRegistry) -> None:
        self._registry = registry

    def execute(self, group_name: str, fn: Callable[..., Any],
                *args: Any, timeout: float = 0, **kwargs: Any) -> Any:
        group = self._registry.get(group_name)
        if group is None:
            raise ValueError(f'Unknown bulkhead group: {group_name}')

        if not group.acquire(timeout):
            raise BulkheadCapacityExceededError(
                f'Bulkhead {group_name} at capacity '
                f'(active: {group._active_count}/{group.max_concurrent})'
            )

        start = time.perf_counter()
        try:
            return fn(*args, **kwargs)
        finally:
            elapsed = time.perf_counter() - start
            with group._lock:
                group._total_time_s += elapsed
            group.release()

    def execute_io(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        return self.execute('io', fn, *args, **kwargs)

    def execute_cpu(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        return self.execute('cpu', fn, *args, **kwargs)

    def execute_network(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        return self.execute('network', fn, *args, **kwargs)


class BulkheadEngine:
    """Top-level bulkhead resource isolation framework."""

    def __init__(self) -> None:
        self._registry = BulkheadRegistry()
        self._executor = BulkheadExecutor(self._registry)

    @property
    def registry(self) -> BulkheadRegistry:
        return self._registry

    @property
    def executor(self) -> BulkheadExecutor:
        return self._executor

    def create_group(self, name: str, max_concurrent: int = 10, queue_size: int = 20) -> BulkheadGroup:
        return self._registry.create_group(name, max_concurrent, queue_size)

    def execute(self, group_name: str, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        return self._executor.execute(group_name, fn, *args, **kwargs)

    def execute_io(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        return self._executor.execute_io(fn, *args, **kwargs)

    def execute_cpu(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        return self._executor.execute_cpu(fn, *args, **kwargs)

    def execute_network(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        return self._executor.execute_network(fn, *args, **kwargs)

    def group_metrics(self, name: str) -> Optional[Dict[str, Any]]:
        group = self._registry.get(name)
        return group.metrics() if group else None

    def summary(self) -> Dict[str, Any]:
        return self._registry.summary()

    def report_text(self) -> str:
        s = self.summary()
        return (
            f'Bulkhead Engine\n'
            f'  Groups: {s["total_groups"]} (io/cpu/network)\n'
            f'  Active: {s["active_overall"]}, '
            f'Processed: {s["total_processed"]}, '
            f'Rejected: {s["total_rejected"]}'
        )

    def export_artifacts(self, dir: str) -> List[str]:
        os.makedirs(dir, exist_ok=True)
        paths = []
        sp = os.path.join(dir, 'bulkhead.json')
        with open(sp, 'w') as f:
            json.dump(self.summary(), f, indent=2)
        paths.append(sp)
        return paths
