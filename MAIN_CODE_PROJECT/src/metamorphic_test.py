"""Metamorphic testing framework for validating non-deterministic processing modules."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple, TypeVar
import datetime
import hashlib
import inspect
import json
import os
import random
import threading
import time
import traceback


T = TypeVar('T')


class MetamorphicRelation:
    """Base class for metamorphic relations between source and follow-up executions."""

    def __init__(self, name: str, description: str = '') -> None:
        self.name = name
        self.description = description

    def derive_followup(self, source_input: Any) -> Any:
        raise NotImplementedError

    def check(self, source_output: Any, followup_output: Any) -> bool:
        raise NotImplementedError

    def violation_message(self, source_input: Any, source_output: Any, followup_input: Any, followup_output: Any) -> str:
        return (
            f'MR-{self.name} violated:\n'
            f'  source input: {source_input}\n'
            f'  source output: {source_output}\n'
            f'  followup input: {followup_input}\n'
            f'  followup output: {followup_output}'
        )


class IdentityRelation(MetamorphicRelation):
    """idempotency: applying operation twice yields same result."""

    def __init__(self) -> None:
        super().__init__('idempotency', 'Applying operation twice yields identical result')

    def derive_followup(self, source_input: Any) -> Any:
        return source_input

    def check(self, source_output: Any, followup_output: Any) -> bool:
        return source_output == followup_output


class PermutationRelation(MetamorphicRelation):
    """permutation: reordering input preserves output (e.g. sorting, sum)."""

    def __init__(self, shuffle_fn: Optional[Callable[[Any], Any]] = None) -> None:
        super().__init__('permutation', 'Reordering input preserves output invariants')
        self._shuffle = shuffle_fn or self._default_shuffle

    @staticmethod
    def _default_shuffle(items: Any) -> Any:
        if isinstance(items, list):
            c = list(items)
            random.shuffle(c)
            return c
        if isinstance(items, dict):
            keys = list(items.keys())
            random.shuffle(keys)
            return {k: items[k] for k in keys}
        return items

    def derive_followup(self, source_input: Any) -> Any:
        return self._shuffle(source_input)

    def check(self, source_output: Any, followup_output: Any) -> bool:
        return source_output == followup_output


class AddRemoveRelation(MetamorphicRelation):
    """add/remove neutral element: adding then removing has no effect."""

    def __init__(self, add_fn: Callable[[Any], Any], remove_fn: Callable[[Any], Any]) -> None:
        super().__init__('add_remove', 'Adding then removing neutral element preserves output')
        self._add = add_fn
        self._remove = remove_fn

    def derive_followup(self, source_input: Any) -> Any:
        return self._remove(self._add(source_input))

    def check(self, source_output: Any, followup_output: Any) -> bool:
        return source_output == followup_output


class MonotonicityRelation(MetamorphicRelation):
    """monotonicity: larger input yields larger-or-equal output."""

    def __init__(self, scale_fn: Callable[[Any], Any]) -> None:
        super().__init__('monotonicity', 'Increasing input does not decrease output')
        self._scale = scale_fn

    def derive_followup(self, source_input: Any) -> Any:
        return self._scale(source_input)

    def check(self, source_output: Any, followup_output: Any) -> bool:
        return followup_output >= source_output


class CompositeRelation(MetamorphicRelation):
    """Apply multiple relations in sequence."""

    def __init__(self, relations: List[MetamorphicRelation]) -> None:
        super().__init__('composite', ' | '.join(r.name for r in relations))
        self._relations = relations

    def derive_followup(self, source_input: Any) -> Any:
        val = source_input
        for r in self._relations:
            val = r.derive_followup(val)
        return val

    def check(self, source_output: Any, followup_output: Any) -> bool:
        for r in self._relations:
            if not r.check(source_output, followup_output):
                return False
        return True


class MetamorphicTestResult:
    """Result of a single metamorphic test execution."""

    def __init__(self, relation_name: str, passed: bool, message: str = '', elapsed_ms: float = 0.0) -> None:
        self.relation_name = relation_name
        self.passed = passed
        self.message = message
        self.elapsed_ms = elapsed_ms
        self.timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            'relation': self.relation_name,
            'passed': self.passed,
            'message': self.message,
            'elapsed_ms': round(self.elapsed_ms, 3),
            'timestamp': self.timestamp,
        }


class MetamorphicTestSuite:
    """A collection of metamorphic relations applied to a target function."""

    def __init__(self, target: Callable, name: str = '') -> None:
        self.target = target
        self.name = name or getattr(target, '__name__', 'unknown')
        self._relations: List[MetamorphicRelation] = []
        self._test_cases: List[Any] = []
        self._results: List[MetamorphicTestResult] = []
        self._lock = threading.Lock()

    def add_relation(self, relation: MetamorphicRelation) -> None:
        self._relations.append(relation)

    def add_test_case(self, test_input: Any) -> None:
        self._test_cases.append(test_input)

    def run(self, timeout_s: float = 10.0) -> List[MetamorphicTestResult]:
        self._results.clear()
        for case in self._test_cases:
            for relation in self._relations:
                t0 = time.perf_counter()
                try:
                    followup_input = relation.derive_followup(case)
                    source_output = self.target(case) if callable(case) else self._call_target(case)
                    followup_output = self.target(followup_input) if callable(followup_input) else self._call_target(followup_input)
                    passed = relation.check(source_output, followup_output)
                    msg = '' if passed else relation.violation_message(case, source_output, followup_input, followup_output)
                except Exception as e:
                    passed = False
                    msg = f'exception: {e}\n{traceback.format_exc()}'
                elapsed = (time.perf_counter() - t0) * 1000
                result = MetamorphicTestResult(relation.name, passed, msg, elapsed)
                with self._lock:
                    self._results.append(result)
        return self._results

    def _call_target(self, inp: Any) -> Any:
        if isinstance(inp, dict):
            return self.target(**inp)
        if isinstance(inp, (list, tuple)):
            return self.target(*inp)
        return self.target(inp)

    @property
    def passed(self) -> int:
        return sum(1 for r in self._results if r.passed)

    @property
    def failed(self) -> int:
        return sum(1 for r in self._results if not r.passed)

    @property
    def total(self) -> int:
        return len(self._results)

    def summary(self) -> Dict[str, Any]:
        return {
            'suite': self.name,
            'passed': self.passed,
            'failed': self.failed,
            'total': self.total,
            'pass_rate': round(self.passed / self.total * 100, 1) if self.total else 0.0,
        }

    def violations(self) -> List[MetamorphicTestResult]:
        return [r for r in self._results if not r.passed]

    def report_text(self) -> str:
        s = self.summary()
        lines = [
            f'Metamorphic Test Report: {s["suite"]}',
            f'  Passed: {s["passed"]} / {s["total"]} ({s["pass_rate"]}%)',
        ]
        for v in self.violations():
            lines.append(f'  FAIL {v.relation_name}: {v.message[:200]}')
        return '\n'.join(lines)


class MetamorphicTestRunner:
    """Orchestrates metamorphic testing across multiple suites with reporting."""

    def __init__(self) -> None:
        self._suites: List[MetamorphicTestSuite] = []
        self._lock = threading.Lock()

    def create_suite(self, target: Callable, name: str = '') -> MetamorphicTestSuite:
        suite = MetamorphicTestSuite(target, name)
        with self._lock:
            self._suites.append(suite)
        return suite

    def run_all(self, timeout_s: float = 10.0) -> Dict[str, List[MetamorphicTestResult]]:
        results: Dict[str, List[MetamorphicTestResult]] = {}
        for suite in self._suites:
            results[suite.name] = suite.run(timeout_s)
        return results

    def summary(self) -> List[Dict[str, Any]]:
        return [s.summary() for s in self._suites]

    def total_summary(self) -> Dict[str, Any]:
        total_passed = sum(s.passed for s in self._suites)
        total_failed = sum(s.failed for s in self._suites)
        total_all = total_passed + total_failed
        return {
            'suites': len(self._suites),
            'passed': total_passed,
            'failed': total_failed,
            'total': total_all,
            'pass_rate': round(total_passed / total_all * 100, 1) if total_all else 0.0,
        }

    def generate_report(self, format: str = 'text') -> str:
        if format == 'text':
            lines = ['=' * 60, 'Metamorphic Testing Report', '=' * 60]
            ts = self.total_summary()
            lines.append(f'Total: {ts["passed"]}/{ts["total"]} passed ({ts["pass_rate"]}%)')
            for s in self._suites:
                lines.append('')
                lines.append(s.report_text())
            return '\n'.join(lines)
        if format == 'json':
            return json.dumps({
                'total_summary': self.total_summary(),
                'suites': [s.summary() for s in self._suites],
                'violations': {s.name: [r.to_dict() for r in s.violations()] for s in self._suites},
            }, indent=2)
        return ''

    def export_report(self, path: str, format: str = 'json') -> None:
        content = self.generate_report(format)
        with open(path, 'w') as f:
            f.write(content)

    def export_artifacts(self, dir: str) -> List[str]:
        os.makedirs(dir, exist_ok=True)
        paths = []
        rp = os.path.join(dir, 'metamorphic_report.json')
        self.export_report(rp, 'json')
        paths.append(rp)
        return paths
