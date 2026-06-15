"""Retry with exponential backoff and jitter framework for transient failure handling."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Type
import datetime
import functools
import json
import os
import random
import threading
import time
import uuid


class RetryableError(Exception):
    """Base exception for retryable transient failures."""
    pass


class NonRetryableError(Exception):
    """Exception that should not be retried."""
    pass


class RetryPolicy:
    """Configuration for retry behavior."""

    def __init__(self, max_attempts: int = 3,
                 base_delay_s: float = 1.0,
                 max_delay_s: float = 60.0,
                 multiplier: float = 2.0,
                 jitter: bool = True,
                 retryable_exceptions: Optional[Set[Type[Exception]]] = None,
                 non_retryable_exceptions: Optional[Set[Type[Exception]]] = None,
                 on_retry: Optional[Callable[[int, float, Exception], None]] = None) -> None:
        self.max_attempts = max_attempts
        self.base_delay_s = base_delay_s
        self.max_delay_s = max_delay_s
        self.multiplier = multiplier
        self.jitter = jitter
        self.retryable_exceptions = retryable_exceptions or {Exception}
        self.non_retryable_exceptions = non_retryable_exceptions or set()
        self.on_retry = on_retry

    def to_dict(self) -> Dict[str, Any]:
        return {
            'max_attempts': self.max_attempts,
            'base_delay_s': self.base_delay_s,
            'max_delay_s': self.max_delay_s,
            'multiplier': self.multiplier,
            'jitter': self.jitter,
            'retryable_exceptions': [e.__name__ for e in self.retryable_exceptions],
            'non_retryable_exceptions': [e.__name__ for e in self.non_retryable_exceptions],
        }


class ExponentialBackoff:
    """Calculate delay with exponential backoff and full-jitter."""

    def __init__(self, policy: RetryPolicy) -> None:
        self._policy = policy

    def delay(self, attempt: int) -> float:
        exp_delay = self._policy.base_delay_s * (self._policy.multiplier ** (attempt - 1))
        capped = min(exp_delay, self._policy.max_delay_s)
        if self._policy.jitter:
            return random.uniform(0, capped)
        return capped


class RetryAttempt:
    """Record of a single retry attempt."""

    def __init__(self, attempt: int, delay_s: float,
                 exception: Optional[Exception] = None) -> None:
        self.attempt = attempt
        self.delay_s = delay_s
        self.exception = exception
        self.timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            'attempt': self.attempt,
            'delay_s': round(self.delay_s, 3),
            'exception': repr(self.exception) if self.exception else None,
            'timestamp': self.timestamp,
        }


class RetryResult:
    """Result of a retry execution."""

    def __init__(self, success: bool, result: Any = None,
                 exception: Optional[Exception] = None,
                 total_attempts: int = 0,
                 total_time_s: float = 0.0,
                 attempts: Optional[List[RetryAttempt]] = None) -> None:
        self.id = uuid.uuid4().hex[:12]
        self.success = success
        self.result = result
        self.exception = exception
        self.total_attempts = total_attempts
        self.total_time_s = total_time_s
        self.attempts = attempts or []

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'success': self.success,
            'result': repr(self.result)[:200] if self.success else None,
            'exception': repr(self.exception) if self.exception else None,
            'total_attempts': self.total_attempts,
            'total_time_s': round(self.total_time_s, 3),
            'attempts': [a.to_dict() for a in self.attempts],
        }


class RetryExecutor:
    """Synchronous retry execution with exponential backoff and jitter."""

    def __init__(self, policy: RetryPolicy) -> None:
        self._policy = policy
        self._backoff = ExponentialBackoff(policy)
        self._history: List[RetryResult] = []

    def execute(self, fn: Callable[..., Any], *args: Any,
                **kwargs: Any) -> RetryResult:
        attempts: List[RetryAttempt] = []
        start = time.perf_counter()

        for attempt in range(1, self._policy.max_attempts + 1):
            try:
                result = fn(*args, **kwargs)
                elapsed = time.perf_counter() - start
                retry_result = RetryResult(True, result, total_attempts=attempt,
                                           total_time_s=elapsed, attempts=attempts)
                self._history.append(retry_result)
                return retry_result
            except tuple(self._policy.non_retryable_exceptions) as e:
                elapsed = time.perf_counter() - start
                retry_result = RetryResult(False, exception=e, total_attempts=attempt,
                                           total_time_s=elapsed, attempts=attempts)
                self._history.append(retry_result)
                return retry_result
            except tuple(self._policy.retryable_exceptions) as e:
                delay = self._backoff.delay(attempt) if attempt < self._policy.max_attempts else 0
                attempts.append(RetryAttempt(attempt, delay, e))
                if self._policy.on_retry:
                    try:
                        self._policy.on_retry(attempt, delay, e)
                    except Exception:
                        pass
                if attempt < self._policy.max_attempts:
                    time.sleep(delay)

        elapsed = time.perf_counter() - start
        last_exc = attempts[-1].exception if attempts else None
        retry_result = RetryResult(False, exception=last_exc,
                                   total_attempts=self._policy.max_attempts,
                                   total_time_s=elapsed, attempts=attempts)
        self._history.append(retry_result)
        return retry_result

    def history(self, limit: int = 100) -> List[Dict[str, Any]]:
        return [r.to_dict() for r in self._history[-limit:]]

    def clear_history(self) -> None:
        self._history.clear()


class AsyncRetryExecutor:
    """Asynchronous retry execution (simulated with threads)."""

    def __init__(self, policy: RetryPolicy) -> None:
        self._policy = policy
        self._backoff = ExponentialBackoff(policy)
        self._history: List[RetryResult] = []

    def execute_async(self, fn: Callable[..., Any], *args: Any,
                      **kwargs: Any) -> RetryResult:
        result_holder: List[RetryResult] = []

        def _run() -> None:
            executor = RetryExecutor(self._policy)
            result_holder.append(executor.execute(fn, *args, **kwargs))

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
        thread.join()

        if result_holder:
            self._history.append(result_holder[0])
            return result_holder[0]
        return RetryResult(False, exception=RuntimeError('async execution failed'))

    def history(self, limit: int = 100) -> List[Dict[str, Any]]:
        return [r.to_dict() for r in self._history[-limit:]]


class RetryContextManager:
    """Context manager for retrying a block of code."""

    def __init__(self, policy: RetryPolicy) -> None:
        self._executor = RetryExecutor(policy)
        self._result: Optional[RetryResult] = None

    def __enter__(self) -> 'RetryContextManager':
        return self

    def __exit__(self, exc_type: Optional[Type[Exception]],
                 exc_val: Optional[Exception],
                 exc_tb: Any) -> bool:
        return False

    @property
    def result(self) -> Optional[RetryResult]:
        return self._result

    def call(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        self._result = self._executor.execute(fn, *args, **kwargs)
        if self._result.success:
            return self._result.result
        raise self._result.exception or RetryableError('retry exhausted')


def retry(policy: Optional[RetryPolicy] = None) -> Callable[..., Any]:
    """Decorator that wraps a function with retry logic."""
    if policy is None:
        policy = RetryPolicy()

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        executor = RetryExecutor(policy)

        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            result = executor.execute(fn, *args, **kwargs)
            if result.success:
                return result.result
            raise result.exception or RetryableError('retry exhausted')

        wrapper._retry_executor = executor
        return wrapper

    return decorator


class RetryMetrics:
    """Aggregated retry metrics."""

    def __init__(self) -> None:
        self._history: List[RetryResult] = []
        self._lock = threading.Lock()

    def record(self, result: RetryResult) -> None:
        with self._lock:
            self._history.append(result)

    def summary(self) -> Dict[str, Any]:
        with self._lock:
            total = len(self._history)
            successes = sum(1 for r in self._history if r.success)
            failures = total - successes
            total_attempts = sum(r.total_attempts for r in self._history)
            total_time = sum(r.total_time_s for r in self._history)
            avg_time = total_time / total if total else 0.0
            return {
                'total_calls': total,
                'successes': successes,
                'failures': failures,
                'total_attempts': total_attempts,
                'avg_attempts_per_call': round(total_attempts / total, 2) if total else 0.0,
                'total_time_s': round(total_time, 3),
                'avg_time_s': round(avg_time, 3),
            }


class RetryEngine:
    """Top-level retry framework."""

    def __init__(self) -> None:
        self._metrics = RetryMetrics()
        self._default_policy = RetryPolicy()

    @property
    def metrics(self) -> RetryMetrics:
        return self._metrics

    def set_default_policy(self, policy: RetryPolicy) -> None:
        self._default_policy = policy

    def execute(self, fn: Callable[..., Any], *args: Any,
                policy: Optional[RetryPolicy] = None,
                **kwargs: Any) -> Any:
        p = policy or self._default_policy
        executor = RetryExecutor(p)
        result = executor.execute(fn, *args, **kwargs)
        self._metrics.record(result)
        if result.success:
            return result.result
        raise result.exception or RetryableError('retry exhausted')

    def execute_async(self, fn: Callable[..., Any], *args: Any,
                      policy: Optional[RetryPolicy] = None,
                      **kwargs: Any) -> Any:
        p = policy or self._default_policy
        executor = AsyncRetryExecutor(p)
        result = executor.execute_async(fn, *args, **kwargs)
        self._metrics.record(result)
        if result.success:
            return result.result
        raise result.exception or RetryableError('retry exhausted')

    def retry_context(self, policy: Optional[RetryPolicy] = None) -> RetryContextManager:
        return RetryContextManager(policy or self._default_policy)

    def history(self, limit: int = 100) -> List[Dict[str, Any]]:
        return [r.to_dict() for r in self._metrics._history[-limit:]]

    def summary(self) -> Dict[str, Any]:
        return {
            'default_policy': self._default_policy.to_dict(),
            'metrics': self._metrics.summary(),
        }

    def report_text(self) -> str:
        s = self.summary()
        m = s['metrics']
        return (
            f'Retry Engine\n'
            f'  Calls: {m["total_calls"]} ({m["successes"]} ok, {m["failures"]} failed)\n'
            f'  Avg attempts/call: {m["avg_attempts_per_call"]}\n'
            f'  Avg time: {m["avg_time_s"]}s'
        )

    def export_artifacts(self, dir: str) -> List[str]:
        os.makedirs(dir, exist_ok=True)
        paths = []
        sp = os.path.join(dir, 'retry_framework.json')
        with open(sp, 'w') as f:
            json.dump(self.summary(), f, indent=2)
        paths.append(sp)
        hp = os.path.join(dir, 'retry_history.json')
        with open(hp, 'w') as f:
            json.dump(self.history(500), f, indent=2)
        paths.append(hp)
        return paths
