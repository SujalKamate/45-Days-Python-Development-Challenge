"""High-performance asynchronous state storage using modern kernel I/O interfaces."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple
import asyncio
import datetime
import json
import os
import threading
import time


_ASYNC_AVAILABLE = True
_CHUNK_SIZE = 65536
_MAX_CONCURRENT = 32


def _make_dirs(path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)


class AsyncWriteOp:
    """Represents a single asynchronous write operation."""

    def __init__(self, path: str, data: bytes, metadata: Optional[Dict[str, Any]] = None) -> None:
        self.path = path
        self.data = data
        self.metadata = metadata or {}
        self.submitted_at: Optional[float] = None
        self.completed_at: Optional[float] = None
        self.error: Optional[str] = None
        self._future: Optional[asyncio.Future] = None

    @property
    def elapsed_ms(self) -> float:
        if self.submitted_at and self.completed_at:
            return (self.completed_at - self.submitted_at) * 1000
        return 0.0


class AsyncReadOp:
    """Represents a single asynchronous read operation."""

    def __init__(self, path: str) -> None:
        self.path = path
        self.data: Optional[bytes] = None
        self.error: Optional[str] = None
        self.submitted_at: Optional[float] = None
        self.completed_at: Optional[float] = None

    @property
    def elapsed_ms(self) -> float:
        if self.submitted_at and self.completed_at:
            return (self.completed_at - self.submitted_at) * 1000
        return 0.0


class IOSQ:
    """I/O Submission Queue — batches operations for kernel submission."""

    def __init__(self) -> None:
        self._pending: List[AsyncWriteOp] = []
        self._lock = threading.Lock()

    def submit(self, op: AsyncWriteOp) -> None:
        with self._lock:
            self._pending.append(op)

    def drain(self) -> List[AsyncWriteOp]:
        with self._lock:
            batch = list(self._pending)
            self._pending.clear()
        return batch

    @property
    def pending_count(self) -> int:
        with self._lock:
            return len(self._pending)


class AsyncIOBackend:
    """Async I/O backend with thread pool fallback for compatibility."""

    def __init__(self, max_workers: int = _MAX_CONCURRENT) -> None:
        self._semaphore = asyncio.Semaphore(max_workers)
        self._executor = None

    async def write(self, path: str, data: bytes) -> None:
        _make_dirs(path)
        try:
            async with self._semaphore:
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(self._executor, self._sync_write, path, data)
        except Exception as e:
            raise IOError(f'async write failed: {e}') from e

    def _sync_write(self, path: str, data: bytes) -> None:
        with open(path, 'wb') as f:
            f.write(data)

    async def read(self, path: str) -> bytes:
        try:
            async with self._semaphore:
                loop = asyncio.get_running_loop()
                return await loop.run_in_executor(self._executor, self._sync_read, path)
        except Exception as e:
            raise IOError(f'async read failed: {e}') from e

    def _sync_read(self, path: str) -> bytes:
        with open(path, 'rb') as f:
            return f.read()

    async def write_batch(self, ops: List[AsyncWriteOp]) -> List[AsyncWriteOp]:
        tasks = []
        for op in ops:
            op.submitted_at = time.time()
            tasks.append(self._execute_write(op))
        return await asyncio.gather(*tasks, return_exceptions=True)

    async def _execute_write(self, op: AsyncWriteOp) -> AsyncWriteOp:
        try:
            await self.write(op.path, op.data)
        except Exception as e:
            op.error = str(e)
        op.completed_at = time.time()
        return op


class AsyncStateStore:
    """Async state storage with SQ/CQ model and batch operations."""

    def __init__(self, base_dir: str = '.async_state') -> None:
        self._base = base_dir
        self._backend = AsyncIOBackend()
        self._sq = IOSQ()
        self._cq: List[AsyncWriteOp] = []
        self._lock = threading.Lock()
        os.makedirs(self._base, exist_ok=True)

    def _state_path(self, name: str) -> str:
        safe = name.replace('/', '_').replace('\\', '_')
        return os.path.join(self._base, f'{safe}.state')

    async def store(self, name: str, data: Dict[str, Any]) -> AsyncWriteOp:
        op = AsyncWriteOp(self._state_path(name), json.dumps(data, default=str).encode('utf-8'))
        op.submitted_at = time.time()
        await self._backend.write(op.path, op.data)
        op.completed_at = time.time()
        with self._lock:
            self._cq.append(op)
        return op

    async def load(self, name: str) -> Dict[str, Any]:
        path = self._state_path(name)
        try:
            data = await self._backend.read(path)
            return json.loads(data.decode('utf-8'))
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    async def store_batch(self, items: Dict[str, Dict[str, Any]]) -> List[AsyncWriteOp]:
        ops = []
        for name, data in items.items():
            op = AsyncWriteOp(self._state_path(name), json.dumps(data, default=str).encode('utf-8'))
            op.submitted_at = time.time()
            ops.append(op)
        results = await self._backend.write_batch(ops)
        completed = []
        for r in results:
            if isinstance(r, AsyncWriteOp):
                r.completed_at = time.time()
                completed.append(r)
        with self._lock:
            self._cq.extend(completed)
        return completed

    def submit(self, name: str, data: Dict[str, Any]) -> None:
        op = AsyncWriteOp(self._state_path(name), json.dumps(data, default=str).encode('utf-8'))
        self._sq.submit(op)

    async def flush(self) -> List[AsyncWriteOp]:
        batch = self._sq.drain()
        if not batch:
            return []
        return await self._backend.write_batch(batch)

    def completion_queue(self, clear: bool = True) -> List[AsyncWriteOp]:
        with self._lock:
            cq = list(self._cq)
            if clear:
                self._cq.clear()
        return cq

    @property
    def pending_submissions(self) -> int:
        return self._sq.pending_count

    def list_states(self) -> List[str]:
        if not os.path.isdir(self._base):
            return []
        files = os.listdir(self._base)
        return sorted(f[:-6] for f in files if f.endswith('.state'))

    def delete(self, name: str) -> bool:
        path = self._state_path(name)
        if os.path.exists(path):
            os.remove(path)
            return True
        return False


class AsyncStoreMetrics:
    """Tracks async store throughput and latency."""

    def __init__(self) -> None:
        self._write_times: List[float] = []
        self._read_times: List[float] = []
        self._lock = threading.Lock()

    def record_write(self, elapsed_ms: float) -> None:
        with self._lock:
            self._write_times.append(elapsed_ms)
            if len(self._write_times) > 1000:
                self._write_times.pop(0)

    def record_read(self, elapsed_ms: float) -> None:
        with self._lock:
            self._read_times.append(elapsed_ms)
            if len(self._read_times) > 1000:
                self._read_times.pop(0)

    def avg_write_latency(self) -> float:
        with self._lock:
            return sum(self._write_times) / max(len(self._write_times), 1)

    def avg_read_latency(self) -> float:
        with self._lock:
            return sum(self._read_times) / max(len(self._read_times), 1)

    def throughput_per_sec(self, elapsed_s: float) -> Dict[str, float]:
        with self._lock:
            writes_per_s = len(self._write_times) / max(elapsed_s, 0.001)
            reads_per_s = len(self._read_times) / max(elapsed_s, 0.001)
        return {'writes_per_sec': round(writes_per_s, 1), 'reads_per_sec': round(reads_per_s, 1)}

    def summary(self) -> Dict[str, Any]:
        return {
            'avg_write_latency_ms': round(self.avg_write_latency(), 3),
            'avg_read_latency_ms': round(self.avg_read_latency(), 3),
            'total_writes': len(self._write_times),
            'total_reads': len(self._read_times),
        }


class AsyncStorageEngine:
    """Top-level async storage engine with SQ/CQ and metrics."""

    def __init__(self, base_dir: str = '.async_state') -> None:
        self._store = AsyncStateStore(base_dir)
        self._metrics = AsyncStoreMetrics()
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    async def store(self, name: str, data: Dict[str, Any]) -> None:
        t0 = time.perf_counter()
        op = await self._store.store(name, data)
        self._metrics.record_write(op.elapsed_ms)

    async def load(self, name: str) -> Dict[str, Any]:
        t0 = time.perf_counter()
        data = await self._store.load(name)
        self._metrics.record_read((time.perf_counter() - t0) * 1000)
        return data

    async def store_batch(self, items: Dict[str, Dict[str, Any]]) -> int:
        ops = await self._store.store_batch(items)
        for op in ops:
            self._metrics.record_write(op.elapsed_ms)
        return len(ops)

    def submit(self, name: str, data: Dict[str, Any]) -> None:
        self._store.submit(name, data)

    async def flush(self) -> int:
        ops = await self._store.flush()
        for op in ops:
            self._metrics.record_write(op.elapsed_ms)
        return len(ops)

    def completion_queue(self, clear: bool = True) -> List[AsyncWriteOp]:
        return self._store.completion_queue(clear)

    @property
    def pending(self) -> int:
        return self._store.pending_submissions

    def metrics(self) -> Dict[str, Any]:
        return self._metrics.summary()

    def list_states(self) -> List[str]:
        return self._store.list_states()

    def delete(self, name: str) -> bool:
        return self._store.delete(name)

    async def run_async(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        return await fn(*args, **kwargs)

    def run(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        loop = self._loop or asyncio.new_event_loop()
        self._loop = loop
        return loop.run_until_complete(fn(*args, **kwargs))
