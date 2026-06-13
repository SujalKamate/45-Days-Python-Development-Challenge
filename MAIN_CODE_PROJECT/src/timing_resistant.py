"""Timing-attack resistant error handling and response normalization."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple, Type, Union
import datetime
import random
import threading
import time


_MAX_DELAY_JITTER_MS = 10
_DEFAULT_FIXED_DELAY_MS = 5


def _busy_wait(seconds: float) -> None:
    target = time.perf_counter() + seconds
    while time.perf_counter() < target:
        _ = 0


def _jitter_ms(mean_ms: float) -> float:
    return mean_ms / 1000.0 + random.uniform(0, _MAX_DELAY_JITTER_MS / 1000.0)


class TimingNormalizer:
    """Ensures consistent execution time regardless of code path taken."""

    def __init__(self, fixed_delay_ms: float = _DEFAULT_FIXED_DELAY_MS) -> None:
        self._fixed_s = fixed_delay_ms / 1000.0

    def normalize(self, result: Any, elapsed_s: float) -> Any:
        remaining = self._fixed_s - elapsed_s
        if remaining > 0:
            _busy_wait(remaining)
        return result

    def protect(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        t0 = time.perf_counter()
        try:
            result = fn(*args, **kwargs)
            return self.normalize(result, time.perf_counter() - t0)
        except Exception as e:
            return self.normalize(e, time.perf_counter() - t0)


class TimingProtector:
    """Wraps security-sensitive operations with timing normalization."""

    def __init__(self, policy: Optional[Dict[str, Any]] = None) -> None:
        self._policy = policy or {'default_delay_ms': _DEFAULT_FIXED_DELAY_MS}
        self._lock = threading.Lock()

    def set_delay(self, delay_ms: float) -> None:
        with self._lock:
            self._policy['default_delay_ms'] = delay_ms

    def get_delay(self) -> float:
        with self._lock:
            return self._policy.get('default_delay_ms', _DEFAULT_FIXED_DELAY_MS)

    def protect(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        normalizer = TimingNormalizer(self.get_delay())
        return normalizer.protect(fn, *args, **kwargs)

    def compare_and_delay(self, result: bool, delay_ms: Optional[float] = None) -> bool:
        ms = delay_ms if delay_ms is not None else self.get_delay()
        wait_s = _jitter_ms(ms)
        _busy_wait(wait_s)
        return result


class ConstantTimeResponse:
    """Returns normalized error/success responses with fixed timing."""

    @staticmethod
    def failure(message: str = 'access denied', delay_ms: float = _DEFAULT_FIXED_DELAY_MS) -> Dict[str, Any]:
        _busy_wait(_jitter_ms(delay_ms))
        return {'success': False, 'error': message}

    @staticmethod
    def success(data: Any = None, delay_ms: float = _DEFAULT_FIXED_DELAY_MS) -> Dict[str, Any]:
        _busy_wait(_jitter_ms(delay_ms))
        return {'success': True, 'data': data}

    @staticmethod
    def conditional(success: bool, data: Any = None, error: str = 'access denied', delay_ms: float = _DEFAULT_FIXED_DELAY_MS) -> Dict[str, Any]:
        _busy_wait(_jitter_ms(delay_ms))
        if success:
            return {'success': True, 'data': data}
        return {'success': False, 'error': error}


class TimingSafeHandler:
    """Decorator/context for normalizing timing of security checks."""

    def __init__(self, delay_ms: float = _DEFAULT_FIXED_DELAY_MS) -> None:
        self._delay_s = delay_ms / 1000.0

    def __call__(self, fn: Callable[..., Any]) -> Callable[..., Any]:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            t0 = time.perf_counter()
            try:
                result = fn(*args, **kwargs)
            except Exception as e:
                result = e
            elapsed = time.perf_counter() - t0
            remaining = self._delay_s - elapsed
            if remaining > 0:
                _busy_wait(remaining)
            if isinstance(result, Exception):
                raise result
            return result
        return wrapper

    def execute(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        return self.__call__(fn)(*args, **kwargs)


class TimingAudit:
    """Records timing of security checks for anomaly detection."""

    def __init__(self, max_entries: int = 1000) -> None:
        self._entries: List[Dict[str, Any]] = []
        self._max = max_entries
        self._lock = threading.Lock()

    def record(self, operation: str, elapsed_ms: float, result: str) -> None:
        entry = {
            'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'operation': operation,
            'elapsed_ms': round(elapsed_ms, 3),
            'result': result,
        }
        with self._lock:
            self._entries.append(entry)
            if len(self._entries) > self._max:
                self._entries.pop(0)

    def recent(self, n: int = 20) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._entries[-n:])

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
