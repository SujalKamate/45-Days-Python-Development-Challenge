"""Graceful degradation with dependency fallback and resilience management framework."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple
import datetime
import json
import os
import threading
import time
import uuid


class DependencyCriticality:
    """Criticality classification for dependencies."""

    CRITICAL = 'critical'
    NON_CRITICAL = 'non_critical'

    @staticmethod
    def should_abort(criticality: str) -> bool:
        return criticality == DependencyCriticality.CRITICAL


class DegradationSeverity:
    """Severity levels for degradation events."""

    INFO = 'info'
    WARNING = 'warning'
    ERROR = 'error'
    CRITICAL = 'critical'


class DegradationEvent:
    """A single degradation event with severity, root cause, and context."""

    def __init__(self, module: str, dependency: str,
                 severity: str = DegradationSeverity.WARNING,
                 message: str = '',
                 root_cause: str = '',
                 recovered: bool = False,
                 details: Optional[Dict[str, Any]] = None) -> None:
        self.id = uuid.uuid4().hex[:12]
        self.module = module
        self.dependency = dependency
        self.severity = severity
        self.message = message
        self.root_cause = root_cause
        self.recovered = recovered
        self.details = details or {}
        self.timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'module': self.module,
            'dependency': self.dependency,
            'severity': self.severity,
            'message': self.message,
            'root_cause': self.root_cause,
            'recovered': self.recovered,
            'details': self.details,
            'timestamp': self.timestamp,
        }


class DegradationRegistry:
    """Centralized registry of degraded modules with event history."""

    def __init__(self) -> None:
        self._degraded: Dict[str, Dict[str, Any]] = {}
        self._events: List[DegradationEvent] = []
        self._lock = threading.Lock()

    def mark_degraded(self, module: str, dependency: str,
                      severity: str = DegradationSeverity.WARNING,
                      message: str = '',
                      root_cause: str = '') -> DegradationEvent:
        event = DegradationEvent(module, dependency, severity, message, root_cause)
        with self._lock:
            self._degraded[module] = {
                'dependency': dependency,
                'severity': severity,
                'message': message,
                'since': event.timestamp,
                'recovered': False,
            }
            self._events.append(event)
        return event

    def mark_recovered(self, module: str, message: str = '') -> Optional[DegradationEvent]:
        with self._lock:
            entry = self._degraded.pop(module, None)
            if entry is None:
                return None
            event = DegradationEvent(
                module, entry['dependency'], DegradationSeverity.INFO,
                message or f'{module} recovered', recovered=True,
                details={'previous_severity': entry['severity']},
            )
            self._events.append(event)
        return event

    def is_degraded(self, module: str) -> bool:
        with self._lock:
            return module in self._degraded

    def degraded_modules(self) -> Dict[str, Dict[str, Any]]:
        with self._lock:
            return dict(self._degraded)

    def event_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self._lock:
            return [e.to_dict() for e in self._events[-limit:]]

    def recent_events(self, since_s: float = 60.0) -> List[Dict[str, Any]]:
        cutoff = (datetime.datetime.now(datetime.timezone.utc) -
                  datetime.timedelta(seconds=since_s)).isoformat()
        with self._lock:
            return [e.to_dict() for e in self._events if e.timestamp >= cutoff]

    def summary(self) -> Dict[str, Any]:
        with self._lock:
            total = len(self._events)
            active = len(self._degraded)
            critical = sum(1 for d in self._degraded.values() if d['severity'] == DegradationSeverity.CRITICAL)
            return {
                'active_degradations': active,
                'critical_degradations': critical,
                'total_events': total,
                'degraded_modules': list(self._degraded.keys()),
            }


class FallbackChain:
    """Primary → fallback → failure execution strategy."""

    def __init__(self, primary: Optional[Callable[..., Any]] = None,
                 fallbacks: Optional[List[Callable[..., Any]]] = None,
                 default_value: Any = None,
                 cache: Optional[Dict[str, Any]] = None) -> None:
        self.primary = primary
        self.fallbacks = fallbacks or []
        self.default_value = default_value
        self._cache = cache or {}

    def execute(self, *args: Any, **kwargs: Any) -> Tuple[bool, Any, str]:
        strategies = []
        if self.primary:
            strategies.append(('primary', self.primary))
        for i, fb in enumerate(self.fallbacks):
            strategies.append((f'fallback_{i}', fb))

        for name, fn in strategies:
            try:
                result = fn(*args, **kwargs)
                return True, result, name
            except Exception:
                continue

        if self._cache:
            return True, self._cache, 'cache'
        if self.default_value is not None:
            return True, self.default_value, 'default'

        return False, None, 'failure'


class DependencyInjector:
    """Dependency injection with fallback and criticality awareness."""

    def __init__(self, registry: DegradationRegistry) -> None:
        self._registry = registry
        self._providers: Dict[str, FallbackChain] = {}

    def register(self, name: str, criticality: str,
                 primary: Optional[Callable[..., Any]] = None,
                 fallbacks: Optional[List[Callable[..., Any]]] = None,
                 default_value: Any = None,
                 cache: Optional[Dict[str, Any]] = None) -> None:
        self._providers[name] = {
            'criticality': criticality,
            'chain': FallbackChain(primary, fallbacks, default_value, cache),
        }

    def resolve(self, name: str, module: str = '',
                *args: Any, **kwargs: Any) -> Any:
        provider = self._providers.get(name)
        if provider is None:
            raise ValueError(f'Unknown dependency: {name}')

        criticality = provider['criticality']
        chain = provider['chain']
        success, result, strategy = chain.execute(*args, **kwargs)

        if not success:
            if DependencyCriticality.should_abort(criticality):
                raise RuntimeError(f'Critical dependency {name} unavailable for module {module}')
            self._registry.mark_degraded(
                module, name, DegradationSeverity.WARNING,
                f'{name} unavailable, processing degraded',
                root_cause=f'all {len(chain.fallbacks) + 1} strategies failed',
            )
            return None

        if strategy != 'primary':
            sev = DegradationSeverity.WARNING if criticality == DependencyCriticality.NON_CRITICAL else DegradationSeverity.ERROR
            self._registry.mark_degraded(
                module, name, sev,
                f'{name} using {strategy} (primary failed)',
                root_cause=f'primary failed, fell back to {strategy}',
            )
        else:
            if self._registry.is_degraded(module):
                self._registry.mark_recovered(module, f'{name} recovered to primary')

        return result

    def list_dependencies(self) -> Dict[str, Any]:
        return {
            name: {
                'criticality': p['criticality'],
            }
            for name, p in self._providers.items()
        }


class DegradationMonitoringEndpoint:
    """HTTP endpoint exposing degradation status."""

    def __init__(self, registry: DegradationRegistry,
                 host: str = '0.0.0.0', port: int = 8902) -> None:
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
                if self.path == '/degradation':
                    body = json.dumps({
                        'degraded': reg.degraded_modules(),
                        'summary': reg.summary(),
                        'recent_events': reg.recent_events(300),
                    }).encode('utf-8')
                elif self.path == '/degradation/summary':
                    body = json.dumps(reg.summary()).encode('utf-8')
                elif self.path == '/degradation/events':
                    body = json.dumps(reg.event_history(50)).encode('utf-8')
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


class GracefulDegradationEngine:
    """Top-level resilience management framework."""

    def __init__(self) -> None:
        self._registry = DegradationRegistry()
        self._injector = DependencyInjector(self._registry)
        self._endpoint: Optional[DegradationMonitoringEndpoint] = None
        self._skip_non_essential: bool = False

    @property
    def registry(self) -> DegradationRegistry:
        return self._registry

    @property
    def injector(self) -> DependencyInjector:
        return self._injector

    def register_dependency(self, name: str, criticality: str,
                            primary: Optional[Callable[..., Any]] = None,
                            fallbacks: Optional[List[Callable[..., Any]]] = None,
                            default_value: Any = None,
                            cache: Optional[Dict[str, Any]] = None) -> None:
        self._injector.register(name, criticality, primary, fallbacks, default_value, cache)

    def resolve(self, name: str, module: str = '',
                *args: Any, **kwargs: Any) -> Any:
        return self._injector.resolve(name, module, *args, **kwargs)

    def mark_degraded(self, module: str, dependency: str,
                      severity: str = DegradationSeverity.WARNING,
                      message: str = '', root_cause: str = '') -> DegradationEvent:
        return self._registry.mark_degraded(module, dependency, severity, message, root_cause)

    def mark_recovered(self, module: str, message: str = '') -> Optional[DegradationEvent]:
        return self._registry.mark_recovered(module, message)

    def is_degraded(self, module: str) -> bool:
        return self._registry.is_degraded(module)

    def set_skip_non_essential(self, skip: bool) -> None:
        self._skip_non_essential = skip

    def should_skip(self) -> bool:
        return self._skip_non_essential

    def degraded_summary(self) -> Dict[str, Any]:
        return self._registry.summary()

    def degraded_modules(self) -> Dict[str, Any]:
        return self._registry.degraded_modules()

    def event_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        return self._registry.event_history(limit)

    def start_monitoring_endpoint(self, host: str = '0.0.0.0',
                                  port: int = 8902) -> None:
        self._endpoint = DegradationMonitoringEndpoint(self._registry, host, port)
        self._endpoint.start()

    def stop_monitoring_endpoint(self) -> None:
        if self._endpoint:
            self._endpoint.stop()

    def summary(self) -> Dict[str, Any]:
        deps = self._injector.list_dependencies()
        deg = self._registry.summary()
        return {
            'dependencies': len(deps),
            'critical_count': sum(1 for d in deps.values() if d['criticality'] == DependencyCriticality.CRITICAL),
            'non_critical_count': sum(1 for d in deps.values() if d['criticality'] == DependencyCriticality.NON_CRITICAL),
            'skip_non_essential': self._skip_non_essential,
            'degradation': deg,
        }

    def report_text(self) -> str:
        s = self.summary()
        deg = s['degradation']
        return (
            f'Graceful Degradation Engine\n'
            f'  Dependencies: {s["dependencies"]} ({s["critical_count"]} critical, {s["non_critical_count"]} non-critical)\n'
            f'  Skip non-essential: {s["skip_non_essential"]}\n'
            f'  Active degradations: {deg["active_degradations"]}'
        )

    def export_artifacts(self, dir: str) -> List[str]:
        os.makedirs(dir, exist_ok=True)
        paths = []
        sp = os.path.join(dir, 'degradation.json')
        with open(sp, 'w') as f:
            json.dump({
                'summary': self.summary(),
                'degraded': self.degraded_modules(),
                'events': self.event_history(100),
            }, f, indent=2)
        paths.append(sp)
        return paths
