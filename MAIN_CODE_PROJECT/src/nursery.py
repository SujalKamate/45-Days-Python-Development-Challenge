"""Structured concurrency — hierarchical task lifecycle with cancellation propagation."""

from __future__ import annotations

from typing import Any, Callable, List, Optional, Set, TypeVar
import threading
import time


T = TypeVar('T')


class TaskError(Exception):
    """Raised when a child task fails inside a nursery."""


class CancelScope:
    """A cancellation scope that can be triggered to cancel all child tasks."""

    def __init__(self) -> None:
        self._cancelled = False
        self._lock = threading.Lock()

    def cancel(self) -> None:
        with self._lock:
            self._cancelled = True

    @property
    def cancelled(self) -> bool:
        return self._cancelled


class Task:
    """A single unit of work with parent tracking and cancellation support."""

    def __init__(self, fn: Callable[[], Any], scope: CancelScope,
                 name: str = '') -> None:
        self._fn = fn
        self._scope = scope
        self._name = name or fn.__name__
        self._result: Any = None
        self._error: Optional[Exception] = None
        self._done = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def _run(self) -> None:
        try:
            if not self._scope.cancelled:
                self._result = self._fn()
        except Exception as e:
            self._error = e
        finally:
            self._done.set()

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def wait(self, timeout: Optional[float] = None) -> Any:
        self._done.wait(timeout)
        if self._error:
            raise self._error
        return self._result

    @property
    def done(self) -> bool:
        return self._done.is_set()

    @property
    def name(self) -> str:
        return self._name


class Nursery:
    """A structured concurrency scope — all child tasks complete before it exits.

    If any child raises, all siblings are cancelled and the exception
    propagates. Guarantees cleanup before returning.
    """

    def __init__(self) -> None:
        self._scope = CancelScope()
        self._tasks: List[Task] = []
        self._lock = threading.Lock()
        self._first_error: Optional[Exception] = None

    def start(self, fn: Callable[[], Any], name: str = '') -> Task:
        task = Task(fn, self._scope, name)
        with self._lock:
            self._tasks.append(task)
        task.start()
        return task

    def cancel(self) -> None:
        self._scope.cancel()

    def __enter__(self) -> Nursery:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        try:
            self._wait_all()
        finally:
            pass
        if exc_type is not None:
            return False
        if self._first_error:
            raise TaskError('Child task failed') from self._first_error
        return False

    def _wait_all(self) -> None:
        if not self._tasks:
            return
        alive = list(self._tasks)
        while alive:
            for task in alive[:]:
                if task.done:
                    alive.remove(task)
                    try:
                        task.wait()
                    except Exception as e:
                        if self._first_error is None:
                            self._first_error = e
                        self._scope.cancel()
            if alive:
                time.sleep(0.005)
        if self._first_error:
            self._scope.cancel()


def run_in_nursery(fns: List[Callable[[], Any]]) -> List[Any]:
    """Run callables in a nursery — all complete or all fail."""
    results: List[Any] = []
    with Nursery() as nursery:
        tasks = [nursery.start(fn) for fn in fns]
    for t in tasks:
        try:
            results.append(t.wait())
        except Exception:
            results.append(None)
    return results


class StructuredExecutor:
    """High-level executor with structured concurrency guarantees."""

    def __init__(self) -> None:
        self._nursery: Optional[Nursery] = None
        self._lock = threading.Lock()

    def scope(self) -> Nursery:
        with self._lock:
            if self._nursery is None:
                self._nursery = Nursery()
            return self._nursery

    def run(self, fn: Callable[[], Any], name: str = '') -> Task:
        return self.scope().start(fn, name)

    def gather(self, fns: List[Callable[[], Any]]) -> List[Any]:
        results: List[Any] = []
        errors: List[Optional[Exception]] = []
        with Nursery() as nursery:
            tasks = [nursery.start(fn) for fn in fns]
            for t in tasks:
                try:
                    results.append(t.wait())
                    errors.append(None)
                except Exception as e:
                    results.append(None)
                    errors.append(e)
        if any(errors):
            for e in errors:
                if e:
                    raise TaskError('Gather failed') from e
        return results

    def cancel_all(self) -> None:
        with self._lock:
            if self._nursery:
                self._nursery.cancel()

    def close(self) -> None:
        with self._lock:
            if self._nursery:
                try:
                    self._nursery._wait_all()
                except Exception:
                    pass
                self._nursery = None
