"""Canary module deployment and progressive traffic management framework."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple
import datetime
import json
import os
import random
import threading
import time
import uuid


class CanaryVersion:
    """Stable and canary version pair for a module."""

    def __init__(self, module: str, stable_fn: Callable[..., Any],
                 canary_fn: Callable[..., Any],
                 stable_label: str = 'stable',
                 canary_label: str = 'canary') -> None:
        self.module = module
        self.stable_fn = stable_fn
        self.canary_fn = canary_fn
        self.stable_label = stable_label
        self.canary_label = canary_label


class ComparisonResult:
    """Result of comparing stable vs canary outputs."""

    def __init__(self, module: str, passed: bool,
                 stable_output: Any = None,
                 canary_output: Any = None,
                 deviation: float = 0.0,
                 details: str = '') -> None:
        self.module = module
        self.passed = passed
        self.stable_output = stable_output
        self.canary_output = canary_output
        self.deviation = deviation
        self.details = details
        self.timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            'module': self.module,
            'passed': self.passed,
            'stable': repr(self.stable_output)[:200],
            'canary': repr(self.canary_output)[:200],
            'deviation': round(self.deviation, 4),
            'details': self.details,
            'timestamp': self.timestamp,
        }


class TrafficRouter:
    """Route traffic between stable and canary versions based on percentage."""

    def __init__(self, canary_pct: float = 10.0) -> None:
        self._canary_pct = canary_pct

    @property
    def canary_pct(self) -> float:
        return self._canary_pct

    @canary_pct.setter
    def canary_pct(self, value: float) -> None:
        self._canary_pct = max(0.0, min(100.0, value))

    def route(self) -> bool:
        return random.uniform(0, 100) < self._canary_pct

    def to_dict(self) -> Dict[str, Any]:
        return {'canary_pct': self._canary_pct, 'stable_pct': 100.0 - self._canary_pct}


class BehavioralComparator:
    """Compare canary outputs against stable outputs for deviation detection."""

    def __init__(self, max_deviation: float = 0.05):
        self._max_deviation = max_deviation

    def compare(self, stable: Any, canary: Any) -> ComparisonResult:
        if isinstance(stable, (int, float)) and isinstance(canary, (int, float)):
            if stable == 0:
                deviation = abs(canary) if canary != 0 else 0.0
            else:
                deviation = abs((canary - stable) / stable)
            passed = deviation <= self._max_deviation
            details = f'deviation={deviation:.4f}' if not passed else ''
            return ComparisonResult('', passed, stable, canary, deviation, details)

        if isinstance(stable, dict) and isinstance(canary, dict):
            mismatched = set(stable.keys()) ^ set(canary.keys())
            if mismatched:
                return ComparisonResult('', False, stable, canary, 1.0, f'key mismatch: {mismatched}')
            deviations = []
            for k in stable:
                if stable[k] != canary[k]:
                    deviations.append(k)
            if deviations:
                return ComparisonResult('', False, stable, canary, len(deviations), f'different keys: {deviations}')
            return ComparisonResult('', True, stable, canary, 0.0, '')

        if stable == canary:
            return ComparisonResult('', True, stable, canary, 0.0, '')

        return ComparisonResult('', False, stable, canary, 1.0, 'values differ')


class CanaryDeployment:
    """A single canary deployment lifecycle."""

    def __init__(self, module: str, version_tag: str,
                 initial_pct: float = 10.0) -> None:
        self.module = module
        self.version_tag = version_tag
        self.deployment_id = uuid.uuid4().hex[:12]
        self.created_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        self.router = TrafficRouter(initial_pct)
        self.comparator = BehavioralComparator()
        self.comparisons: List[ComparisonResult] = []
        self.total_requests = 0
        self.canary_requests = 0
        self.failures = 0
        self._active = True
        self._rollback_reason = ''

    @property
    def active(self) -> bool:
        return self._active

    @property
    def rollback_reason(self) -> str:
        return self._rollback_reason

    def rollback(self, reason: str = 'manual') -> None:
        self._active = False
        self._rollback_reason = reason
        self.router.canary_pct = 0.0

    def promote(self) -> None:
        self._active = False
        self.router.canary_pct = 100.0

    def record_comparison(self, result: ComparisonResult) -> None:
        self.comparisons.append(result)
        self.total_requests += 1
        if not result.passed:
            self.failures += 1

    def success_rate(self) -> float:
        if self.total_requests == 0:
            return 1.0
        return 1.0 - (self.failures / self.total_requests)

    def summary(self, module: str = '') -> Dict[str, Any]:
        r = self.comparison_rate()
        return {
            'deployment_id': self.deployment_id,
            'module': module or self.module,
            'version': self.version_tag,
            'active': self._active,
            'canary_pct': self.router.canary_pct,
            'total_requests': self.total_requests,
            'canary_requests': self.canary_requests,
            'comparison_failures': self.failures,
            'success_rate': round(self.success_rate(), 4),
            'comparison_match_rate': round(r, 4),
            'rollback_reason': self._rollback_reason if not self._active else '',
            'created_at': self.created_at,
        }

    def comparison_rate(self) -> float:
        if not self.comparisons:
            return 1.0
        passed = sum(1 for c in self.comparisons if c.passed)
        return passed / len(self.comparisons)


class ProgressiveExpander:
    """Progressively increase canary traffic after successful evaluations."""

    def __init__(self, steps: Optional[List[float]] = None,
                 min_comparisons: int = 10,
                 min_success_rate: float = 0.95,
                 evaluation_interval_s: float = 60.0) -> None:
        self._steps = steps or [10.0, 25.0, 50.0, 75.0, 100.0]
        self._min_comparisons = min_comparisons
        self._min_success_rate = min_success_rate
        self._evaluation_interval = evaluation_interval_s

    def evaluate(self, deployment: CanaryDeployment) -> Tuple[bool, str]:
        if deployment.total_requests < self._min_comparisons:
            return True, 'not enough data yet'

        rate = deployment.success_rate()
        comp_rate = deployment.comparison_rate()

        if rate < self._min_success_rate or comp_rate < self._min_success_rate:
            deployment.rollback(f'success rate {rate:.2f} below threshold {self._min_success_rate}')
            return False, f'rollback: success_rate={rate:.2f}, comparison_rate={comp_rate:.2f}'

        current_pct = deployment.router.canary_pct
        next_pct = None
        for step in self._steps:
            if step > current_pct:
                next_pct = step
                break

        if next_pct is not None:
            deployment.router.canary_pct = next_pct
            return True, f'expanded from {current_pct}% to {next_pct}%'

        return True, f'fully rolled out at {current_pct}%'


class CanaryEngine:
    """Top-level canary deployment and traffic management."""

    def __init__(self) -> None:
        self._versions: Dict[str, CanaryVersion] = {}
        self._deployments: Dict[str, CanaryDeployment] = {}
        self._lock = threading.Lock()
        self._expander = ProgressiveExpander()

    def register_version(self, module: str, stable_fn: Callable[..., Any],
                         canary_fn: Callable[..., Any],
                         stable_label: str = 'stable',
                         canary_label: str = 'canary') -> None:
        with self._lock:
            self._versions[module] = CanaryVersion(module, stable_fn, canary_fn, stable_label, canary_label)

    def start_deployment(self, module: str, version_tag: str,
                         initial_pct: float = 10.0) -> Optional[CanaryDeployment]:
        with self._lock:
            if module not in self._versions:
                return None
            dep = CanaryDeployment(module, version_tag, initial_pct)
            self._deployments[dep.deployment_id] = dep
            return dep

    def execute(self, module: str, *args: Any,
                deployment_id: Optional[str] = None,
                **kwargs: Any) -> Any:
        version = self._versions.get(module)
        if version is None:
            raise ValueError(f'Unknown module: {module}')

        dep = self._find_deployment(module, deployment_id)

        if dep and not dep.active:
            return version.stable_fn(*args, **kwargs)

        use_canary = dep and dep.router.route()

        if use_canary:
            try:
                canary_result = version.canary_fn(*args, **kwargs)
                stable_result = version.stable_fn(*args, **kwargs)
                if dep:
                    dep.canary_requests += 1
                    result = self._compare_and_record(version, dep, stable_result, canary_result)
                    return result if result is not None else canary_result
                return canary_result
            except Exception as e:
                if dep:
                    dep.record_comparison(ComparisonResult(module, False, None, None, 1.0, str(e)))
                return version.stable_fn(*args, **kwargs)
        else:
            return version.stable_fn(*args, **kwargs)

    def _find_deployment(self, module: str,
                         deployment_id: Optional[str] = None) -> Optional[CanaryDeployment]:
        if deployment_id:
            return self._deployments.get(deployment_id)
        for dep in self._deployments.values():
            if dep.module == module and dep.active:
                return dep
        return None

    @staticmethod
    def _compare_and_record(version: CanaryVersion, dep: CanaryDeployment,
                            stable: Any, canary: Any) -> Optional[Any]:
        result = dep.comparator.compare(stable, canary)
        result.module = version.module
        dep.record_comparison(result)
        if result.passed:
            return canary
        return None

    def evaluate_deployment(self, deployment_id: str) -> Tuple[bool, str]:
        dep = self._deployments.get(deployment_id)
        if dep is None:
            return False, 'deployment not found'
        return self._expander.evaluate(dep)

    def rollback_deployment(self, deployment_id: str,
                            reason: str = 'manual') -> bool:
        dep = self._deployments.get(deployment_id)
        if dep is None:
            return False
        dep.rollback(reason)
        return True

    def promote_deployment(self, deployment_id: str) -> bool:
        dep = self._deployments.get(deployment_id)
        if dep is None:
            return False
        dep.promote()
        return True

    def list_deployments(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [dep.summary(module=dep.module) for dep in self._deployments.values()]

    def active_deployments(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [dep.summary(module=dep.module) for dep in self._deployments.values() if dep.active]

    def deployment_detail(self, deployment_id: str) -> Optional[Dict[str, Any]]:
        dep = self._deployments.get(deployment_id)
        if dep is None:
            return None
        info = dep.summary()
        info['comparisons'] = [c.to_dict() for c in dep.comparisons[-50:]]
        return info

    def summary(self) -> Dict[str, Any]:
        with self._lock:
            return {
                'registered_modules': list(self._versions.keys()),
                'total_deployments': len(self._deployments),
                'active_deployments': sum(1 for d in self._deployments.values() if d.active),
                'deployments': self.list_deployments(),
            }

    def report_text(self) -> str:
        s = self.summary()
        return (
            f'Canary Deploy Engine\n'
            f'  Modules: {s["registered_modules"]}\n'
            f'  Deployments: {s["total_deployments"]} ({s["active_deployments"]} active)'
        )

    def export_artifacts(self, dir: str) -> List[str]:
        os.makedirs(dir, exist_ok=True)
        paths = []
        sp = os.path.join(dir, 'canary_deploy.json')
        with open(sp, 'w') as f:
            json.dump(self.summary(), f, indent=2)
        paths.append(sp)
        for dep_id, dep in self._deployments.items():
            dp = os.path.join(dir, f'canary_{dep_id}.json')
            with open(dp, 'w') as f:
                json.dump(self.deployment_detail(dep_id), f, indent=2)
            paths.append(dp)
        return paths
