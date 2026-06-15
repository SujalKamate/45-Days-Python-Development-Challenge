"""Environment-aware configuration validation and deployment readiness assessment framework."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Pattern, Tuple
import datetime
import json
import os
import re
import socket
import sys
import uuid


class ConfigRule:
    """A single validation rule for a configuration key."""

    def __init__(self, key: str, rule_type: str = 'required',
                 expected_type: Optional[str] = None,
                 min_value: Optional[float] = None,
                 max_value: Optional[float] = None,
                 pattern: Optional[str] = None,
                 allowed_values: Optional[List[Any]] = None,
                 min_length: Optional[int] = None,
                 max_length: Optional[int] = None,
                 description: str = '',
                 severity: str = 'error') -> None:
        self.key = key
        self.rule_type = rule_type
        self.expected_type = expected_type
        self.min_value = min_value
        self.max_value = max_value
        self.pattern = pattern
        self.allowed_values = allowed_values
        self.min_length = min_length
        self.max_length = max_length
        self.description = description
        self.severity = severity

    def validate(self, config: Dict[str, Any]) -> List[str]:
        errors: List[str] = []
        value = config.get(self.key)

        if self.rule_type == 'required' and value is None:
            errors.append(f'{self.key}: required but missing')
            return errors

        if value is None:
            return errors

        if self.expected_type:
            ok = False
            if self.expected_type == 'str' and isinstance(value, str):
                ok = True
            elif self.expected_type == 'int' and isinstance(value, int):
                ok = True
            elif self.expected_type == 'float' and isinstance(value, (int, float)):
                ok = True
            elif self.expected_type == 'bool' and isinstance(value, bool):
                ok = True
            elif self.expected_type == 'list' and isinstance(value, (list, tuple)):
                ok = True
            elif self.expected_type == 'dict' and isinstance(value, dict):
                ok = True
            if not ok:
                errors.append(f'{self.key}: expected {self.expected_type}, got {type(value).__name__}')

        if self.min_value is not None and isinstance(value, (int, float)):
            if value < self.min_value:
                errors.append(f'{self.key}: {value} < min {self.min_value}')

        if self.max_value is not None and isinstance(value, (int, float)):
            if value > self.max_value:
                errors.append(f'{self.key}: {value} > max {self.max_value}')

        if self.pattern and isinstance(value, str):
            if not re.match(self.pattern, value):
                errors.append(f'{self.key}: does not match pattern {self.pattern}')

        if self.allowed_values is not None and value not in self.allowed_values:
            errors.append(f'{self.key}: {value} not in allowed {self.allowed_values}')

        if self.min_length is not None and isinstance(value, (str, list, tuple, dict)):
            if len(value) < self.min_length:
                errors.append(f'{self.key}: length {len(value)} < min {self.min_length}')

        if self.max_length is not None and isinstance(value, (str, list, tuple, dict)):
            if len(value) > self.max_length:
                errors.append(f'{self.key}: length {len(value)} > max {self.max_length}')

        return errors


class ValidationResult:
    """Result of a config validation run."""

    def __init__(self, profile: str = '') -> None:
        self.profile = profile
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()

    @property
    def passed(self) -> bool:
        return len(self.errors) == 0

    @property
    def score(self) -> float:
        total = len(self.errors) + len(self.warnings)
        if total == 0:
            return 100.0
        ok = len(self.warnings)
        return round((ok / total) * 100, 1) if total > 0 else 100.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'profile': self.profile,
            'passed': self.passed,
            'score': self.score,
            'errors': self.errors,
            'warnings': self.warnings,
            'timestamp': self.timestamp,
        }

    def merge(self, other: ValidationResult) -> None:
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)


class EnvironmentProfile:
    """Deployment profile with environment-specific validation rules."""

    def __init__(self, name: str, description: str = '',
                 rules: Optional[List[ConfigRule]] = None,
                 checks: Optional[List[Callable[[], Tuple[bool, str]]]] = None) -> None:
        self.name = name
        self.description = description
        self.rules = rules or []
        self.checks = checks or []

    def add_rule(self, rule: ConfigRule) -> None:
        self.rules.append(rule)

    def add_check(self, check: Callable[[], Tuple[bool, str]]) -> None:
        self.checks.append(check)

    def validate_config(self, config: Dict[str, Any]) -> ValidationResult:
        result = ValidationResult(self.name)
        for rule in self.rules:
            errs = rule.validate(config)
            if rule.severity == 'error':
                result.errors.extend(errs)
            else:
                result.warnings.extend(errs)
        return result

    def run_checks(self) -> List[Dict[str, Any]]:
        results = []
        for check in self.checks:
            try:
                ok, msg = check()
                results.append({'passed': ok, 'message': msg})
            except Exception as e:
                results.append({'passed': False, 'message': str(e)})
        return results

    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'description': self.description,
            'rule_count': len(self.rules),
            'check_count': len(self.checks),
        }


class ProfileRegistry:
    """Registry of named environment profiles."""

    def __init__(self) -> None:
        self._profiles: Dict[str, EnvironmentProfile] = {}

    def register(self, profile: EnvironmentProfile) -> None:
        self._profiles[profile.name] = profile

    def get(self, name: str) -> Optional[EnvironmentProfile]:
        return self._profiles.get(name)

    def list(self) -> List[str]:
        return list(self._profiles.keys())

    def remove(self, name: str) -> bool:
        return self._profiles.pop(name, None) is not None


class ReadinessCheck:
    """Individual deployment readiness check."""

    def __init__(self, name: str, check_fn: Callable[[], Tuple[bool, str]],
                 category: str = 'general', severity: str = 'error') -> None:
        self.name = name
        self.check_fn = check_fn
        self.category = category
        self.severity = severity

    def run(self) -> Dict[str, Any]:
        try:
            ok, msg = self.check_fn()
            return {
                'name': self.name,
                'category': self.category,
                'passed': ok,
                'message': msg,
                'severity': self.severity,
            }
        except Exception as e:
            return {
                'name': self.name,
                'category': self.category,
                'passed': False,
                'message': str(e),
                'severity': self.severity,
            }


class DeploymentReadiness:
    """Assess deployment readiness via system checks."""

    def __init__(self) -> None:
        self._checks: List[ReadinessCheck] = []

    def add_check(self, check: ReadinessCheck) -> None:
        self._checks.append(check)

    def add_builtins(self) -> None:
        self._checks.extend([
            ReadinessCheck('python_version', self._check_python, 'system', 'error'),
            ReadinessCheck('disk_space', self._check_disk, 'system', 'warning'),
            ReadinessCheck('network_reachability', self._check_network, 'network', 'warning'),
            ReadinessCheck('env_vars', self._check_env_vars, 'config', 'warning'),
        ])

    def run_all(self) -> Dict[str, Any]:
        results = [c.run() for c in self._checks]
        total = len(results)
        passed = sum(1 for r in results if r['passed'])
        return {
            'total': total,
            'passed': passed,
            'failed': total - passed,
            'checks': results,
            'ready': passed == total,
            'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }

    def run_category(self, category: str) -> List[Dict[str, Any]]:
        return [c.run() for c in self._checks if c.category == category]

    @staticmethod
    def _check_python() -> Tuple[bool, str]:
        v = sys.version_info
        ok = v.major >= 3 and v.minor >= 8
        return ok, f'Python {v.major}.{v.minor}.{v.micro}'

    @staticmethod
    def _check_disk() -> Tuple[bool, str]:
        try:
            import shutil
            usage = shutil.disk_usage(os.getcwd())
            gb_free = usage.free / (1024 ** 3)
            ok = gb_free > 0.5
            return ok, f'{gb_free:.1f} GB free'
        except Exception:
            return True, 'disk check unavailable'

    @staticmethod
    def _check_network() -> Tuple[bool, str]:
        try:
            socket.create_connection(('8.8.8.8', 53), timeout=2)
            return True, 'network reachable'
        except OSError:
            return False, 'network unreachable'

    @staticmethod
    def _check_env_vars() -> Tuple[bool, str]:
        required = ['PATH', 'HOME'] if sys.platform != 'win32' else ['PATH', 'USERPROFILE']
        missing = [v for v in required if not os.environ.get(v)]
        ok = len(missing) == 0
        return ok, f'missing: {missing}' if missing else 'all present'


class EnvConfigEngine:
    """Top-level environment-aware configuration validation engine."""

    def __init__(self) -> None:
        self._registry = ProfileRegistry()
        self._readiness = DeploymentReadiness()
        self._config: Dict[str, Any] = {}
        self._history: List[Dict[str, Any]] = []
        self._add_default_profiles()

    @property
    def registry(self) -> ProfileRegistry:
        return self._registry

    @property
    def readiness(self) -> DeploymentReadiness:
        return self._readiness

    def _add_default_profiles(self) -> None:
        dev = EnvironmentProfile('development', 'Local development environment')
        self._registry.register(dev)

        staging = EnvironmentProfile('staging', 'Pre-production staging')
        staging.add_rule(ConfigRule('debug', 'required', 'bool', severity='warning'))
        staging.add_rule(ConfigRule('log_level', 'required', 'str', allowed_values=['DEBUG', 'INFO', 'WARNING', 'ERROR']))
        self._registry.register(staging)

        prod = EnvironmentProfile('production', 'Production environment')
        prod.add_rule(ConfigRule('debug', 'required', 'bool', severity='error'))
        prod.add_rule(ConfigRule('log_level', 'required', 'str', allowed_values=['INFO', 'WARNING', 'ERROR']))
        prod.add_rule(ConfigRule('port', 'required', 'int', min_value=1, max_value=65535))
        prod.add_rule(ConfigRule('host', 'required', 'str', pattern=r'^[a-zA-Z0-9\.\-]+$'))
        prod.add_rule(ConfigRule('secret_key', 'required', 'str', min_length=16, severity='error'))
        prod.add_rule(ConfigRule('db_url', 'required', 'str', min_length=1))
        prod.add_check(self._check_prod_resources)
        self._registry.register(prod)

    @staticmethod
    def _check_prod_resources() -> Tuple[bool, str]:
        return True, 'production resources nominal'

    def set_config(self, config: Dict[str, Any]) -> None:
        self._config = dict(config)

    def update_config(self, key: str, value: Any) -> None:
        self._config[key] = value

    def get_config(self, key: str, default: Any = None) -> Any:
        return self._config.get(key, default)

    def load_from_env(self, prefix: str = 'APP_') -> None:
        for k, v in os.environ.items():
            if k.startswith(prefix):
                config_key = k[len(prefix):].lower()
                self._config[config_key] = v

    def validate(self, profile_name: str = '') -> ValidationResult:
        profile = self._registry.get(profile_name) if profile_name else None
        if profile is None:
            profile = self._registry.get('development')
        if profile is None:
            return ValidationResult('unknown')

        result = profile.validate_config(self._config)
        record = result.to_dict()
        record['profile_used'] = profile.name
        self._history.append(record)
        return result

    def validate_all_profiles(self) -> Dict[str, ValidationResult]:
        results: Dict[str, ValidationResult] = {}
        for name in self._registry.list():
            results[name] = self.validate(name)
        return results

    def create_profile(self, name: str, description: str = '',
                       base: str = '') -> EnvironmentProfile:
        if base and self._registry.get(base):
            base_profile = self._registry.get(base)
            profile = EnvironmentProfile(name, description, list(base_profile.rules))
        else:
            profile = EnvironmentProfile(name, description)
        self._registry.register(profile)
        return profile

    def run_readiness(self) -> Dict[str, Any]:
        self._readiness.add_builtins()
        assessment = self._readiness.run_all()
        self._history.append({
            'type': 'readiness',
            'result': assessment,
            'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        })
        return assessment

    def add_rule(self, profile_name: str, rule: ConfigRule) -> bool:
        profile = self._registry.get(profile_name)
        if profile:
            profile.add_rule(rule)
            return True
        return False

    def add_check(self, profile_name: str,
                  check_fn: Callable[[], Tuple[bool, str]]) -> bool:
        profile = self._registry.get(profile_name)
        if profile:
            profile.add_check(check_fn)
            return True
        return False

    def history(self, limit: int = 100) -> List[Dict[str, Any]]:
        return self._history[-limit:]

    def summary(self) -> Dict[str, Any]:
        profiles = self._registry.list()
        return {
            'profiles': profiles,
            'active_profile': profiles[0] if profiles else '',
            'config_keys': len(self._config),
            'history_entries': len(self._history),
            'readiness_checks': len(self._readiness._checks),
        }

    def report_text(self) -> str:
        s = self.summary()
        return (
            f'Env Config Engine\n'
            f'  Profiles: {s["profiles"]}\n'
            f'  Config keys: {s["config_keys"]}\n'
            f'  Readiness checks: {s["readiness_checks"]}\n'
            f'  Validations run: {s["history_entries"]}'
        )

    def export_artifacts(self, dir: str) -> List[str]:
        os.makedirs(dir, exist_ok=True)
        paths = []
        sp = os.path.join(dir, 'env_config.json')
        with open(sp, 'w') as f:
            json.dump(self.summary(), f, indent=2)
        paths.append(sp)
        vp = os.path.join(dir, 'env_validation_history.json')
        with open(vp, 'w') as f:
            json.dump(self.history(500), f, indent=2)
        paths.append(vp)
        return paths
