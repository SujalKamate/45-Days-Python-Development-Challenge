"""Deadline propagation and context-aware execution control framework."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional
import datetime
import json
import os
import threading
import time
import uuid


class DeadlineExceededError(Exception):
    """Raised when a deadline is exceeded before or during execution."""
    pass


class CancelledError(Exception):
    """Raised when execution is cancelled."""
    pass


class ExecutionContext:
    """Request-scoped execution context with deadline, cancellation, and metadata."""

    def __init__(self, deadline_s: float = 0,
                 parent: Optional[ExecutionContext] = None,
                 metadata: Optional[Dict[str, Any]] = None) -> None:
        self.context_id = uuid.uuid4().hex[:12]
        self.created_at = time.time()
        self._deadline_s = deadline_s
        self._cancelled = False
        self._cancel_reason = ''
        self._parent = parent
        self._metadata: Dict[str, Any] = metadata or {}
        self._child_contexts: List[ExecutionContext] = []

    @property
    def deadline(self) -> float:
        if self._deadline_s > 0:
            return self.created_at + self._deadline_s
        if self._parent and self._parent.deadline > 0:
            return self._parent.deadline
        return 0.0

    @property
    def remaining_s(self) -> float:
        d = self.deadline
        if d == 0:
            return float('inf')
        remaining = d - time.time()
        return max(0.0, remaining)

    @property
    def expired(self) -> bool:
        d = self.deadline
        if d == 0:
            return False
        return time.time() >= d

    @property
    def cancelled(self) -> bool:
        if self._cancelled:
            return True
        if self._parent and self._parent.cancelled:
            return True
        return False

    @property
    def cancel_reason(self) -> str:
        if self._cancelled:
            return self._cancel_reason
        if self._parent and self._parent.cancelled:
            return self._parent.cancel_reason
        return ''

    def cancel(self, reason: str = 'cancelled') -> None:
        self._cancelled = True
        self._cancel_reason = reason
        for child in self._child_contexts:
            child.cancel(reason)

    def add_metadata(self, key: str, value: Any) -> None:
        self._metadata[key] = value

    def get_metadata(self, key: str, default: Any = None) -> Any:
        return self._metadata.get(key, default)

    def all_metadata(self) -> Dict[str, Any]:
        meta = dict(self._metadata)
        if self._parent:
            parent_meta = self._parent.all_metadata()
            parent_meta.update(meta)
            return parent_meta
        return meta

    def create_child(self, deadline_s: float = 0,
                     metadata: Optional[Dict[str, Any]] = None) -> ExecutionContext:
        child = ExecutionContext(deadline_s, self, metadata)
        self._child_contexts.append(child)
        return child

    def check(self) -> None:
        if self.cancelled:
            raise CancelledError(f'Execution cancelled: {self.cancel_reason}')
        if self.expired:
            raise DeadlineExceededError(f'Deadline exceeded (remaining: {self.remaining_s:.1f}s)')

    def to_dict(self) -> Dict[str, Any]:
        return {
            'context_id': self.context_id,
            'deadline_s': self._deadline_s,
            'deadline_abs': datetime.datetime.fromtimestamp(self.deadline, datetime.timezone.utc).isoformat() if self.deadline else '',
            'remaining_s': round(self.remaining_s, 2) if self.deadline else None,
            'expired': self.expired,
            'cancelled': self.cancelled,
            'cancel_reason': self.cancel_reason,
            'metadata': self._metadata,
            'child_count': len(self._child_contexts),
        }

    @staticmethod
    def with_deadline(deadline_s: float,
                      metadata: Optional[Dict[str, Any]] = None) -> ExecutionContext:
        return ExecutionContext(deadline_s, metadata=metadata)

    @staticmethod
    def with_cancel(metadata: Optional[Dict[str, Any]] = None) -> ExecutionContext:
        return ExecutionContext(0, metadata=metadata)


class ContextStorage:
    """Thread-local storage for the current execution context."""

    _local = threading.local()

    @classmethod
    def get(cls) -> Optional[ExecutionContext]:
        return getattr(cls._local, 'context', None)

    @classmethod
    def set(cls, ctx: ExecutionContext) -> None:
        cls._local.context = ctx

    @classmethod
    def clear(cls) -> None:
        if hasattr(cls._local, 'context'):
            del cls._local.context


class DeadlineValidator:
    """Validate deadlines before executing expensive tasks."""

    @staticmethod
    def check_deadline(context: Optional[ExecutionContext] = None,
                       min_remaining_s: float = 0.1) -> None:
        ctx = context or ContextStorage.get()
        if ctx is None:
            return
        if ctx.remaining_s < min_remaining_s:
            raise DeadlineExceededError(
                f'Insufficient time remaining: {ctx.remaining_s:.3f}s < {min_remaining_s}s'
            )

    @staticmethod
    def has_time(context: Optional[ExecutionContext] = None,
                 required_s: float = 1.0) -> bool:
        ctx = context or ContextStorage.get()
        if ctx is None:
            return True
        return ctx.remaining_s >= required_s


class ContextAwareExecutor:
    """Execute callables with deadline and cancellation checks."""

    def __init__(self) -> None:
        self._timeout_events: List[Dict[str, Any]] = []
        self._cancel_events: List[Dict[str, Any]] = []

    def execute(self, fn: Callable[..., Any], *args: Any,
                context: Optional[ExecutionContext] = None,
                check_interval_s: float = 0.1,
                **kwargs: Any) -> Any:
        ctx = context or ContextStorage.get()

        if ctx:
            ctx.check()

        has_deadline = ctx and ctx.deadline > 0

        if has_deadline:
            result_holder: List[Any] = [None]
            exc_holder: List[Optional[Exception]] = [None]
            finished = threading.Event()

            def _target() -> None:
                try:
                    result_holder[0] = fn(*args, **kwargs)
                except Exception as e:
                    exc_holder[0] = e
                finally:
                    finished.set()

            thread = threading.Thread(target=_target, daemon=True)
            thread.start()

            while not finished.is_set():
                if ctx.cancelled:
                    self._cancel_events.append({
                        'context_id': ctx.context_id,
                        'reason': ctx.cancel_reason,
                        'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    })
                    raise CancelledError(f'Cancelled during execution: {ctx.cancel_reason}')
                if ctx.expired:
                    self._timeout_events.append({
                        'context_id': ctx.context_id,
                        'remaining_s': round(ctx.remaining_s, 3),
                        'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    })
                    raise DeadlineExceededError(f'Deadline exceeded during execution')
                finished.wait(timeout=check_interval_s)

            if exc_holder[0]:
                raise exc_holder[0]
            return result_holder[0]
        else:
            return fn(*args, **kwargs)

    def timeout_events(self, limit: int = 100) -> List[Dict[str, Any]]:
        return self._timeout_events[-limit:]

    def cancel_events(self, limit: int = 100) -> List[Dict[str, Any]]:
        return self._cancel_events[-limit:]

    def clear_events(self) -> None:
        self._timeout_events.clear()
        self._cancel_events.clear()


class DeadlineContextEngine:
    """Top-level deadline propagation and context-aware execution engine."""

    def __init__(self) -> None:
        self._executor = ContextAwareExecutor()
        self._metric_lock = threading.Lock()
        self._total_contexts = 0
        self._total_timeouts = 0
        self._total_cancellations = 0

    @property
    def executor(self) -> ContextAwareExecutor:
        return self._executor

    def create_context(self, deadline_s: float = 0,
                       metadata: Optional[Dict[str, Any]] = None) -> ExecutionContext:
        ctx = ExecutionContext(deadline_s, metadata=metadata)
        with self._metric_lock:
            self._total_contexts += 1
        ContextStorage.set(ctx)
        return ctx

    def create_child_context(self, deadline_s: float = 0,
                             metadata: Optional[Dict[str, Any]] = None) -> Optional[ExecutionContext]:
        parent = ContextStorage.get()
        if parent is None:
            return self.create_context(deadline_s, metadata)
        child = parent.create_child(deadline_s, metadata)
        ContextStorage.set(child)
        with self._metric_lock:
            self._total_contexts += 1
        return child

    def current_context(self) -> Optional[ExecutionContext]:
        return ContextStorage.get()

    def clear_context(self) -> None:
        ContextStorage.clear()

    def execute(self, fn: Callable[..., Any], *args: Any,
                deadline_s: float = 0,
                context: Optional[ExecutionContext] = None,
                **kwargs: Any) -> Any:
        ctx = context or self.current_context()
        if ctx is None and deadline_s > 0:
            ctx = self.create_context(deadline_s)

        if ctx is None:
            return fn(*args, **kwargs)

        try:
            return self._executor.execute(fn, *args, context=ctx, **kwargs)
        except DeadlineExceededError:
            with self._metric_lock:
                self._total_timeouts += 1
            raise
        except CancelledError:
            with self._metric_lock:
                self._total_cancellations += 1
            raise

    def check_deadline(self, min_remaining_s: float = 0.1) -> None:
        DeadlineValidator.check_deadline(min_remaining_s)

    def has_time(self, required_s: float = 1.0) -> bool:
        return DeadlineValidator.has_time(required_s=required_s)

    def summary(self) -> Dict[str, Any]:
        with self._metric_lock:
            return {
                'total_contexts': self._total_contexts,
                'total_timeouts': self._total_timeouts,
                'total_cancellations': self._total_cancellations,
                'current_context': ContextStorage.get().to_dict() if ContextStorage.get() else None,
            }

    def report_text(self) -> str:
        s = self.summary()
        return (
            f'Deadline Context Engine\n'
            f'  Contexts created: {s["total_contexts"]}\n'
            f'  Timeouts: {s["total_timeouts"]}\n'
            f'  Cancellations: {s["total_cancellations"]}\n'
            f'  Active context: {"yes" if s["current_context"] else "no"}'
        )

    def export_artifacts(self, dir: str) -> List[str]:
        os.makedirs(dir, exist_ok=True)
        paths = []
        sp = os.path.join(dir, 'deadline_context.json')
        with open(sp, 'w') as f:
            json.dump(self.summary(), f, indent=2)
        paths.append(sp)
        return paths
