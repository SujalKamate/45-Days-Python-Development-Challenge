"""Circuit breaker with half-open recovery and failure isolation framework."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple
import datetime
import json
import os
import subprocess
import threading
import time
import uuid
from urllib.request import Request, urlopen
from urllib.error import URLError


class CircuitState:
    """Circuit breaker states."""

    CLOSED = 'closed'
    OPEN = 'open'
    HALF_OPEN = 'half_open'


class StateTransition:
    """Record of a circuit breaker state transition."""

    def __init__(self, resource: str, from_state: str, to_state: str,
                 reason: str = '') -> None:
        self.resource = resource
        self.from_state = from_state
        self.to_state = to_state
        self.reason = reason
        self.timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            'resource': self.resource,
            'from': self.from_state,
            'to': self.to_state,
            'reason': self.reason,
            'timestamp': self.timestamp,
        }


class SlidingWindowCounter:
    """Count failures within a sliding time window."""

    def __init__(self, window_s: float = 60.0) -> None:
        self._window_s = window_s
        self._events: list[float] = []
        self._lock = threading.Lock()

    def record_failure(self) -> None:
        now = time.time()
        with self._lock:
            self._events.append(now)
            self._trim(now)

    def _trim(self, now: float) -> None:
        cutoff = now - self._window_s
        self._events = [t for t in self._events if t >= cutoff]

    def count(self) -> int:
        now = time.time()
        with self._lock:
            self._trim(now)
            return len(self._events)

    def reset(self) -> None:
        with self._lock:
            self._events.clear()


class CircuitBreaker:
    """Circuit breaker for a single resource."""

    def __init__(self, resource: str,
                 failure_threshold: int = 5,
                 cooldown_s: float = 30.0,
                 window_s: float = 60.0,
                 recovery_probe: Optional[Callable[[], bool]] = None) -> None:
        self.resource = resource
        self.failure_threshold = failure_threshold
        self.cooldown_s = cooldown_s
        self._window_s = window_s
        self._recovery_probe = recovery_probe
        self._state = CircuitState.CLOSED
        self._counter = SlidingWindowCounter(window_s)
        self._last_failure_time: float = 0.0
        self._last_state_change: float = time.time()
        self._lock = threading.Lock()
        self._transitions: List[StateTransition] = []
        self._success_count: int = 0
        self._failure_count: int = 0

    @property
    def state(self) -> str:
        with self._lock:
            if self._state == CircuitState.OPEN:
                if time.time() - self._last_state_change >= self.cooldown_s:
                    self._transition_to(CircuitState.HALF_OPEN,
                                        'cooldown elapsed')
            return self._state

    def call(self, fn: Callable[..., Any], *args: Any,
             **kwargs: Any) -> Any:
        current_state = self.state

        if current_state == CircuitState.OPEN:
            self._failure_count += 1
            raise CircuitBreakerOpenError(
                f'Circuit breaker OPEN for {self.resource}'
            )

        if current_state == CircuitState.HALF_OPEN:
            if self._recovery_probe:
                try:
                    probe_ok = self._recovery_probe()
                except Exception:
                    probe_ok = False
                if not probe_ok:
                    self._transition_to(CircuitState.OPEN,
                                        'recovery probe failed')
                    self._failure_count += 1
                    raise CircuitBreakerOpenError(
                        f'Recovery probe failed for {self.resource}'
                    )

        try:
            result = fn(*args, **kwargs)
            with self._lock:
                if self._state == CircuitState.HALF_OPEN:
                    self._transition_to(CircuitState.CLOSED, 'recovery succeeded')
                self._success_count += 1
                self._counter.reset()
            return result
        except Exception as e:
            with self._lock:
                self._counter.record_failure()
                self._last_failure_time = time.time()
                self._failure_count += 1
                count = self._counter.count()
                if count >= self.failure_threshold and self._state != CircuitState.OPEN:
                    self._transition_to(CircuitState.OPEN,
                                        f'failure threshold reached ({count}/{self.failure_threshold})')
            raise

    def _transition_to(self, new_state: str, reason: str = '') -> None:
        old_state = self._state
        if old_state == new_state:
            return
        self._state = new_state
        self._last_state_change = time.time()
        self._transitions.append(
            StateTransition(self.resource, old_state, new_state, reason)
        )

    def set_recovery_probe(self, probe: Callable[[], bool]) -> None:
        self._recovery_probe = probe

    def reset(self) -> None:
        with self._lock:
            self._state = CircuitState.CLOSED
            self._counter.reset()
            self._last_state_change = time.time()
            self._transitions.append(
                StateTransition(self.resource, self._state, CircuitState.CLOSED, 'manual reset')
            )

    def metrics(self) -> Dict[str, Any]:
        with self._lock:
            return {
                'resource': self.resource,
                'state': self._state,
                'failure_threshold': self.failure_threshold,
                'cooldown_s': self.cooldown_s,
                'window_s': self._window_s,
                'failures_in_window': self._counter.count(),
                'total_successes': self._success_count,
                'total_failures': self._failure_count,
                'last_failure_time': datetime.datetime.fromtimestamp(
                    self._last_failure_time, datetime.timezone.utc
                ).isoformat() if self._last_failure_time else '',
                'last_state_change': datetime.datetime.fromtimestamp(
                    self._last_state_change, datetime.timezone.utc
                ).isoformat(),
                'transition_count': len(self._transitions),
            }

    def transition_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            return [t.to_dict() for t in self._transitions[-limit:]]


class CircuitBreakerOpenError(Exception):
    """Raised when a circuit breaker is OPEN and rejects a call."""
    pass


class CircuitBreakerRegistry:
    """Registry of all circuit breakers."""

    def __init__(self) -> None:
        self._breakers: Dict[str, CircuitBreaker] = {}
        self._lock = threading.Lock()

    def get_or_create(self, resource: str,
                      failure_threshold: int = 5,
                      cooldown_s: float = 30.0,
                      window_s: float = 60.0,
                      recovery_probe: Optional[Callable[[], bool]] = None) -> CircuitBreaker:
        with self._lock:
            if resource not in self._breakers:
                self._breakers[resource] = CircuitBreaker(
                    resource, failure_threshold, cooldown_s, window_s, recovery_probe
                )
            return self._breakers[resource]

    def get(self, resource: str) -> Optional[CircuitBreaker]:
        with self._lock:
            return self._breakers.get(resource)

    def list(self) -> Dict[str, Any]:
        with self._lock:
            return {name: cb.metrics() for name, cb in self._breakers.items()}

    def reset_all(self) -> None:
        with self._lock:
            for cb in self._breakers.values():
                cb.reset()

    def summary(self) -> Dict[str, Any]:
        with self._lock:
            total = len(self._breakers)
            open_count = sum(1 for cb in self._breakers.values() if cb.state == CircuitState.OPEN)
            half_open = sum(1 for cb in self._breakers.values() if cb.state == CircuitState.HALF_OPEN)
            closed = sum(1 for cb in self._breakers.values() if cb.state == CircuitState.CLOSED)
            return {
                'total': total,
                'closed': closed,
                'open': open_count,
                'half_open': half_open,
            }


class ProtectedCaller:
    """Protected wrappers for HTTP, file, subprocess, and generic operations."""

    def __init__(self, registry: CircuitBreakerRegistry) -> None:
        self._registry = registry

    def http_get(self, url: str, resource: str = '',
                 timeout: float = 10.0, **kwargs: Any) -> bytes:
        breaker = self._registry.get_or_create(resource or url)
        return breaker.call(self._do_http_get, url, timeout)

    @staticmethod
    def _do_http_get(url: str, timeout: float) -> bytes:
        req = Request(url, method='GET')
        with urlopen(req, timeout=timeout) as resp:
            return resp.read()

    def file_read(self, path: str, resource: str = '') -> str:
        breaker = self._registry.get_or_create(resource or f'file:{path}')
        return breaker.call(self._do_file_read, path)

    @staticmethod
    def _do_file_read(path: str) -> str:
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()

    def file_write(self, path: str, content: str, resource: str = '') -> None:
        breaker = self._registry.get_or_create(resource or f'file:{path}')
        return breaker.call(self._do_file_write, path, content)

    @staticmethod
    def _do_file_write(path: str, content: str) -> None:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)

    def subprocess_run(self, cmd: List[str], resource: str = '',
                       timeout: float = 30.0, **kwargs: Any) -> subprocess.CompletedProcess:
        breaker = self._registry.get_or_create(resource or f'subprocess:{cmd[0]}')
        return breaker.call(self._do_subprocess, cmd, timeout, **kwargs)

    @staticmethod
    def _do_subprocess(cmd: List[str], timeout: float,
                       **kwargs: Any) -> subprocess.CompletedProcess:
        return subprocess.run(cmd, capture_output=True, timeout=timeout, **kwargs)

    def call(self, fn: Callable[..., Any], resource: str,
             *args: Any, **kwargs: Any) -> Any:
        breaker = self._registry.get_or_create(resource)
        return breaker.call(fn, *args, **kwargs)


class CircuitBreakerEndpoint:
    """HTTP endpoint exposing circuit breaker status."""

    def __init__(self, registry: CircuitBreakerRegistry,
                 host: str = '0.0.0.0', port: int = 8903) -> None:
        self._registry = registry
        self._host = host
        self._port = port
        self._server: Optional[Any] = None
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        import http.server
        reg = self._registry

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == '/circuit-breaker':
                    body = json.dumps({
                        'summary': reg.summary(),
                        'breakers': reg.list(),
                    }).encode('utf-8')
                elif self.path == '/circuit-breaker/summary':
                    body = json.dumps(reg.summary()).encode('utf-8')
                else:
                    self.send_response(404)
                    self.end_headers()
                    return
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, fmt, *args):
                pass

        self._server = http.server.HTTPServer((self._host, self._port), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()


class CircuitBreakerEngine:
    """Top-level circuit breaker framework."""

    def __init__(self) -> None:
        self._registry = CircuitBreakerRegistry()
        self._caller = ProtectedCaller(self._registry)
        self._endpoint: Optional[CircuitBreakerEndpoint] = None

    @property
    def registry(self) -> CircuitBreakerRegistry:
        return self._registry

    @property
    def caller(self) -> ProtectedCaller:
        return self._caller

    def get_breaker(self, resource: str,
                    failure_threshold: int = 5,
                    cooldown_s: float = 30.0,
                    window_s: float = 60.0,
                    recovery_probe: Optional[Callable[[], bool]] = None) -> CircuitBreaker:
        return self._registry.get_or_create(resource, failure_threshold, cooldown_s, window_s, recovery_probe)

    def protect(self, fn: Callable[..., Any], resource: str,
                *args: Any, **kwargs: Any) -> Any:
        return self._caller.call(fn, resource, *args, **kwargs)

    def http_get(self, url: str, resource: str = '', timeout: float = 10.0) -> bytes:
        return self._caller.http_get(url, resource, timeout)

    def file_read(self, path: str, resource: str = '') -> str:
        return self._caller.file_read(path, resource)

    def file_write(self, path: str, content: str, resource: str = '') -> None:
        return self._caller.file_write(path, content, resource)

    def subprocess_run(self, cmd: List[str], resource: str = '',
                       timeout: float = 30.0) -> Any:
        return self._caller.subprocess_run(cmd, resource, timeout)

    def reset_all(self) -> None:
        self._registry.reset_all()

    def start_endpoint(self, host: str = '0.0.0.0', port: int = 8903) -> None:
        self._endpoint = CircuitBreakerEndpoint(self._registry, host, port)
        self._endpoint.start()

    def stop_endpoint(self) -> None:
        if self._endpoint:
            self._endpoint.stop()

    def summary(self) -> Dict[str, Any]:
        return {
            'breakers': self._registry.summary(),
            'details': self._registry.list(),
        }

    def report_text(self) -> str:
        s = self._registry.summary()
        return (
            f'Circuit Breaker Engine\n'
            f'  Total breakers: {s["total"]}\n'
            f'  Closed: {s["closed"]}, Open: {s["open"]}, Half-Open: {s["half_open"]}'
        )

    def export_artifacts(self, dir: str) -> List[str]:
        os.makedirs(dir, exist_ok=True)
        paths = []
        sp = os.path.join(dir, 'circuit_breaker.json')
        with open(sp, 'w') as f:
            json.dump(self.summary(), f, indent=2)
        paths.append(sp)
        return paths
