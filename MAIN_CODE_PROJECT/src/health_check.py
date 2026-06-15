"""Health check endpoint with dependency probing and service readiness validation."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple
import datetime
import json
import os
import shutil
import socket
import tempfile
import threading
import time
import uuid


class ComponentStatus:
    """Status of a single health check component."""

    HEALTHY = 'healthy'
    UNHEALTHY = 'unhealthy'
    DEGRADED = 'degraded'
    UNKNOWN = 'unknown'

    def __init__(self, name: str, status: str = UNKNOWN,
                 message: str = '', latency_ms: float = 0.0,
                 details: Optional[Dict[str, Any]] = None) -> None:
        self.name = name
        self.status = status
        self.message = message
        self.latency_ms = latency_ms
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'status': self.status,
            'message': self.message,
            'latency_ms': round(self.latency_ms, 2),
            'details': self.details,
        }


class HealthReport:
    """Aggregated health report with overall status."""

    def __init__(self, check_type: str = 'liveness') -> None:
        self.check_type = check_type
        self.components: List[ComponentStatus] = []
        self.timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()

    @property
    def overall_status(self) -> str:
        if not self.components:
            return ComponentStatus.UNKNOWN
        if any(c.status == ComponentStatus.UNHEALTHY for c in self.components):
            return ComponentStatus.UNHEALTHY
        if any(c.status == ComponentStatus.DEGRADED for c in self.components):
            return ComponentStatus.DEGRADED
        return ComponentStatus.HEALTHY

    @property
    def healthy(self) -> bool:
        return self.overall_status == ComponentStatus.HEALTHY

    def add(self, component: ComponentStatus) -> None:
        self.components.append(component)

    def http_status(self) -> int:
        return 200 if self.healthy else 503

    def to_dict(self) -> Dict[str, Any]:
        return {
            'check_type': self.check_type,
            'overall_status': self.overall_status,
            'healthy': self.healthy,
            'timestamp': self.timestamp,
            'components': [c.to_dict() for c in self.components],
        }

    def summary_text(self) -> str:
        total = len(self.components)
        healthy = sum(1 for c in self.components if c.status == ComponentStatus.HEALTHY)
        return f'{self.check_type}: {self.overall_status} ({healthy}/{total} components ok)'


class ModuleLoadChecker:
    """Verify that required application modules are loaded."""

    def __init__(self, required_modules: Optional[List[str]] = None) -> None:
        self._required = required_modules or []

    def add_required(self, module_name: str) -> None:
        if module_name not in self._required:
            self._required.append(module_name)

    def check(self) -> ComponentStatus:
        start = time.perf_counter()
        import sys
        loaded = []
        missing = []
        for mod in self._required:
            if mod in sys.modules:
                loaded.append(mod)
            else:
                missing.append(mod)
        elapsed = (time.perf_counter() - start) * 1000
        if missing:
            return ComponentStatus('module_loader', ComponentStatus.UNHEALTHY,
                                   f'Missing modules: {missing}', elapsed,
                                   {'loaded': loaded, 'missing': missing})
        return ComponentStatus('module_loader', ComponentStatus.HEALTHY,
                               f'All {len(loaded)} modules loaded', elapsed,
                               {'loaded': loaded})


class StorageChecker:
    """Validate state directory accessibility and disk usage."""

    def __init__(self, state_dir: str = '', disk_threshold_pct: float = 90.0) -> None:
        self._state_dir = state_dir or os.getcwd()
        self._disk_threshold = disk_threshold_pct

    def check(self) -> ComponentStatus:
        start = time.perf_counter()
        issues = []
        details: Dict[str, Any] = {}

        try:
            os.makedirs(self._state_dir, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=self._state_dir)
            os.close(fd)
            os.remove(tmp)
            details['tempfile_test'] = 'passed'
        except IOError as e:
            issues.append(f'Storage access: {e}')
            details['tempfile_test'] = f'failed: {e}'

        try:
            usage = shutil.disk_usage(self._state_dir)
            pct = (usage.used / usage.total) * 100
            details['disk_used_pct'] = round(pct, 1)
            details['disk_free_gb'] = round(usage.free / (1024 ** 3), 2)
            if pct > self._disk_threshold:
                issues.append(f'Disk usage {pct:.1f}% exceeds threshold {self._disk_threshold}%')
        except Exception as e:
            issues.append(f'Disk check failed: {e}')

        elapsed = (time.perf_counter() - start) * 1000
        if issues:
            return ComponentStatus('storage', ComponentStatus.UNHEALTHY,
                                   '; '.join(issues), elapsed, details)
        return ComponentStatus('storage', ComponentStatus.HEALTHY,
                               'Storage accessible', elapsed, details)


class ExecutionFreshnessChecker:
    """Track module execution timestamps and detect stale modules."""

    def __init__(self, stale_threshold_s: float = 300.0) -> None:
        self._stale_threshold = stale_threshold_s
        self._exec_times: Dict[str, float] = {}

    def record_execution(self, module_name: str) -> None:
        self._exec_times[module_name] = time.time()

    def check(self) -> ComponentStatus:
        start = time.perf_counter()
        now = time.time()
        stale = []
        fresh = []
        for mod, ts in self._exec_times.items():
            age = now - ts
            if age > self._stale_threshold:
                stale.append({'module': mod, 'age_s': round(age, 1)})
            else:
                fresh.append({'module': mod, 'age_s': round(age, 1)})
        elapsed = (time.perf_counter() - start) * 1000
        details = {'fresh': fresh, 'stale': stale, 'threshold_s': self._stale_threshold}
        if stale:
            return ComponentStatus('execution_freshness', ComponentStatus.DEGRADED,
                                   f'{len(stale)} stale module(s) detected', elapsed, details)
        return ComponentStatus('execution_freshness', ComponentStatus.HEALTHY,
                               'All modules fresh', elapsed, details)


class SampleExecutionChecker:
    """Run a sample processing on dummy data to verify operational capability."""

    def __init__(self,
                 sample_fn: Optional[Callable[[], Any]] = None) -> None:
        self._sample_fn = sample_fn

    def set_sample_fn(self, fn: Callable[[], Any]) -> None:
        self._sample_fn = fn

    def check(self) -> ComponentStatus:
        start = time.perf_counter()
        details: Dict[str, Any] = {}

        if self._sample_fn is None:
            return ComponentStatus('sample_execution', ComponentStatus.UNKNOWN,
                                   'No sample function configured', 0.0, details)

        try:
            result = self._sample_fn()
            elapsed = (time.perf_counter() - start) * 1000
            details['result'] = str(result)[:200]
            return ComponentStatus('sample_execution', ComponentStatus.HEALTHY,
                                   f'Sample execution completed in {elapsed:.1f}ms', elapsed, details)
        except Exception as e:
            elapsed = (time.perf_counter() - start) * 1000
            details['error'] = str(e)
            return ComponentStatus('sample_execution', ComponentStatus.UNHEALTHY,
                                   f'Sample execution failed: {e}', elapsed, details)


class DependencyChecker:
    """Probe external dependencies (network, databases, etc.)."""

    def __init__(self) -> None:
        self._deps: List[Tuple[str, Callable[[], ComponentStatus]]] = []

    def add_dependency(self, name: str,
                       probe_fn: Callable[[], ComponentStatus]) -> None:
        self._deps.append((name, probe_fn))

    def add_network_probe(self, name: str, host: str, port: int,
                          timeout_s: float = 2.0) -> None:
        def _probe() -> ComponentStatus:
            start = time.perf_counter()
            try:
                sock = socket.create_connection((host, port), timeout=timeout_s)
                sock.close()
                elapsed = (time.perf_counter() - start) * 1000
                return ComponentStatus(name, ComponentStatus.HEALTHY,
                                       f'Reachable at {host}:{port}', elapsed)
            except OSError as e:
                elapsed = (time.perf_counter() - start) * 1000
                return ComponentStatus(name, ComponentStatus.UNHEALTHY,
                                       f'Unreachable: {e}', elapsed)

        self._deps.append((name, _probe))

    def check(self) -> List[ComponentStatus]:
        results = []
        for name, probe_fn in self._deps:
            try:
                results.append(probe_fn())
            except Exception as e:
                results.append(ComponentStatus(name, ComponentStatus.UNHEALTHY, str(e)))
        return results


class HealthEndpoint:
    """HTTP server serving /health/live and /health/ready endpoints."""

    def __init__(self, engine: HealthCheckEngine,
                 host: str = '0.0.0.0', port: int = 8901) -> None:
        self._engine = engine
        self._host = host
        self._port = port
        self._server: Optional[Any] = None
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        import http.server
        eng = self._engine

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == '/health/live':
                    report = eng.liveness()
                elif self.path in ('/health/ready', '/health'):
                    report = eng.readiness()
                else:
                    self.send_response(404)
                    self.end_headers()
                    return

                body = json.dumps(report.to_dict()).encode('utf-8')
                self.send_response(report.http_status())
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.send_header('Access-Control-Allow-Origin', '*')
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


class HealthCheckEngine:
    """Top-level health check framework with liveness and readiness probes."""

    def __init__(self) -> None:
        self._module_checker = ModuleLoadChecker()
        self._storage_checker = StorageChecker()
        self._freshness_checker = ExecutionFreshnessChecker()
        self._sample_checker = SampleExecutionChecker()
        self._dependency_checker = DependencyChecker()
        self._custom_liveness: List[Callable[[], ComponentStatus]] = []
        self._custom_readiness: List[Callable[[], ComponentStatus]] = []
        self._endpoint: Optional[HealthEndpoint] = None
        self._startup_time = time.time()

    @property
    def module_checker(self) -> ModuleLoadChecker:
        return self._module_checker

    @property
    def storage_checker(self) -> StorageChecker:
        return self._storage_checker

    @property
    def freshness_checker(self) -> ExecutionFreshnessChecker:
        return self._freshness_checker

    @property
    def sample_checker(self) -> SampleExecutionChecker:
        return self._sample_checker

    @property
    def dependency_checker(self) -> DependencyChecker:
        return self._dependency_checker

    def record_execution(self, module_name: str) -> None:
        self._freshness_checker.record_execution(module_name)

    def add_liveness_probe(self, fn: Callable[[], ComponentStatus]) -> None:
        self._custom_liveness.append(fn)

    def add_readiness_probe(self, fn: Callable[[], ComponentStatus]) -> None:
        self._custom_readiness.append(fn)

    def liveness(self) -> HealthReport:
        report = HealthReport('liveness')
        for probe in self._custom_liveness:
            try:
                report.add(probe())
            except Exception as e:
                report.add(ComponentStatus('custom_liveness', ComponentStatus.UNHEALTHY, str(e)))
        if not report.components:
            report.add(ComponentStatus('process', ComponentStatus.HEALTHY,
                                       f'Running for {time.time() - self._startup_time:.0f}s'))
        return report

    def readiness(self) -> HealthReport:
        report = HealthReport('readiness')

        report.add(self._module_checker.check())
        report.add(self._storage_checker.check())
        report.add(self._freshness_checker.check())
        report.add(self._sample_checker.check())

        for dep_status in self._dependency_checker.check():
            report.add(dep_status)

        for probe in self._custom_readiness:
            try:
                report.add(probe())
            except Exception as e:
                report.add(ComponentStatus('custom_readiness', ComponentStatus.UNHEALTHY, str(e)))

        return report

    def start_endpoint(self, host: str = '0.0.0.0', port: int = 8901) -> HealthEndpoint:
        self._endpoint = HealthEndpoint(self, host, port)
        self._endpoint.start()
        return self._endpoint

    def stop_endpoint(self) -> None:
        if self._endpoint:
            self._endpoint.stop()

    def summary(self) -> Dict[str, Any]:
        live = self.liveness()
        ready = self.readiness()
        return {
            'liveness': live.overall_status,
            'readiness': ready.overall_status,
            'healthy': live.healthy and ready.healthy,
            'uptime_s': round(time.time() - self._startup_time, 1),
            'modules_required': len(self._module_checker._required),
            'dependencies': len(self._dependency_checker._deps),
            'fresh_modules': len(self._freshness_checker._exec_times),
        }

    def report_text(self) -> str:
        s = self.summary()
        return (
            f'Health Check Engine\n'
            f'  Liveness: {s["liveness"]}\n'
            f'  Readiness: {s["readiness"]}\n'
            f'  Overall: {"healthy" if s["healthy"] else "unhealthy"}\n'
            f'  Uptime: {s["uptime_s"]}s'
        )

    def export_artifacts(self, dir: str) -> List[str]:
        os.makedirs(dir, exist_ok=True)
        paths = []
        sp = os.path.join(dir, 'health_check.json')
        with open(sp, 'w') as f:
            json.dump({
                'summary': self.summary(),
                'liveness': self.liveness().to_dict(),
                'readiness': self.readiness().to_dict(),
            }, f, indent=2)
        paths.append(sp)
        return paths

