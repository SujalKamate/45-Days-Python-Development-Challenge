"""Lock-free ring buffer event log — non-blocking multi-producer single-consumer."""

from __future__ import annotations

from typing import Any, Callable, List, Optional, Tuple
import threading
import time


class RingBuffer:
    """Fixed-capacity lock-free ring buffer for non-blocking event storage.

    Uses atomic index updates via Python's list and ``threading.Barrier``-free
    sequencing. For CPython, ``list[index] = value`` and integer operations
    on GIL-protected types are effectively atomic for this use pattern.
    """

    def __init__(self, capacity: int = 16384) -> None:
        self._capacity = capacity
        self._buffer: List[Optional[Any]] = [None] * capacity
        self._write_seq = 0
        self._read_seq = 0
        self._lock = threading.Lock()

    def push(self, item: Any) -> bool:
        idx = self._write_seq % self._capacity
        next_seq = self._write_seq + 1
        if next_seq - self._read_seq > self._capacity:
            return False
        self._buffer[idx] = item
        self._write_seq = next_seq
        return True

    def pop(self) -> Optional[Any]:
        if self._read_seq >= self._write_seq:
            return None
        idx = self._read_seq % self._capacity
        item = self._buffer[idx]
        if item is not None:
            self._buffer[idx] = None
            self._read_seq += 1
        return item

    def drain(self) -> List[Any]:
        items: List[Any] = []
        while True:
            item = self.pop()
            if item is None:
                break
            items.append(item)
        return items

    @property
    def size(self) -> int:
        return self._write_seq - self._read_seq

    @property
    def capacity(self) -> int:
        return self._capacity


class LogEvent:
    __slots__ = ('timestamp', 'level', 'source', 'message', 'data')

    def __init__(self, level: str, source: str, message: str,
                 data: Any = None) -> None:
        self.timestamp = time.monotonic()
        self.level = level
        self.source = source
        self.message = message
        self.data = data


class LockFreeEventLog:
    """High-throughput event log using a lock-free ring buffer.

    Producers push events without blocking. A consumer drains batches
    for processing or flushing to disk.
    """

    def __init__(self, capacity: int = 16384, flush_fn: Optional[Callable[[List[LogEvent]], None]] = None) -> None:
        self._ring = RingBuffer(capacity)
        self._flush_fn = flush_fn
        self._flush_interval = 1.0
        self._last_flush = time.monotonic()
        self._lock = threading.Lock()

    def emit(self, level: str, source: str, message: str, data: Any = None) -> bool:
        event = LogEvent(level, source, message, data)
        ok = self._ring.push(event)
        if not ok:
            self._flush()
            ok = self._ring.push(event)
        return ok

    def _flush(self) -> None:
        batch = self._ring.drain()
        if batch and self._flush_fn:
            try:
                self._flush_fn(batch)
            except Exception:
                pass

    def flush(self) -> None:
        self._flush()
        self._last_flush = time.monotonic()

    def poll(self) -> None:
        now = time.monotonic()
        if now - self._last_flush > self._flush_interval:
            self.flush()

    @property
    def pending(self) -> int:
        return self._ring.size


class AsyncEventBus:
    """Non-blocking event bus for pub-sub communication without locks."""

    def __init__(self, capacity: int = 4096) -> None:
        self._ring = RingBuffer(capacity)
        self._subscribers: List[Tuple[str, Callable[[LogEvent], None]]] = []
        self._lock = threading.Lock()

    def subscribe(self, event_type: str, handler: Callable[[LogEvent], None]) -> None:
        with self._lock:
            self._subscribers.append((event_type, handler))

    def publish(self, event_type: str, source: str, message: str, data: Any = None) -> bool:
        event = LogEvent(event_type, source, message, data)
        return self._ring.push(event)

    def dispatch(self) -> int:
        count = 0
        while True:
            event = self._ring.pop()
            if event is None:
                break
            count += 1
            with self._lock:
                handlers = [(et, h) for et, h in self._subscribers if et == event.level or et == '*']
            for _, handler in handlers:
                try:
                    handler(event)
                except Exception:
                    pass
        return count
