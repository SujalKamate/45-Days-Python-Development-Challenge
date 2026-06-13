"""Coverage-guided regression test selection for optimized CI feedback."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Set, Tuple
import datetime
import hashlib
import json
import os
import re
import threading
import time


class CoverageMap:
    """Maps tests to the source files/lines they cover."""

    def __init__(self) -> None:
        self._test_coverage: Dict[str, Set[str]] = {}
        self._lock = threading.Lock()

    def record(self, test_name: str, covered_files: Set[str]) -> None:
        with self._lock:
            if test_name not in self._test_coverage:
                self._test_coverage[test_name] = set()
            self._test_coverage[test_name].update(covered_files)

    def record_line(self, test_name: str, file_path: str, line: int) -> None:
        with self._lock:
            key = f'{file_path}:{line}'
            if test_name not in self._test_coverage:
                self._test_coverage[test_name] = set()
            self._test_coverage[test_name].add(key)

    def tests_for_file(self, file_path: str) -> Set[str]:
        with self._lock:
            return {t for t, files in self._test_coverage.items()
                    if any(f.startswith(file_path) or f.split(':')[0] == file_path for f in files)}

    def files_for_test(self, test_name: str) -> Set[str]:
        with self._lock:
            raw = self._test_coverage.get(test_name, set())
            return {f.split(':')[0] for f in raw}

    def all_tests(self) -> Set[str]:
        with self._lock:
            return set(self._test_coverage.keys())

    def export(self, path: str) -> None:
        payload = {k: sorted(v) for k, v in self._test_coverage.items()}
        with open(path, 'w') as f:
            json.dump(payload, f, indent=2)

    @staticmethod
    def load(path: str) -> CoverageMap:
        cm = CoverageMap()
        with open(path) as f:
            data = json.load(f)
        cm._test_coverage = {k: set(v) for k, v in data.items()}
        return cm


class ChangeAnalyzer:
    """Detects changed files between code versions."""

    @staticmethod
    def from_git_diff(ref: str = 'HEAD') -> Set[str]:
        import subprocess
        try:
            result = subprocess.run(
                ['git', 'diff', '--name-only', ref],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0:
                return {f.replace('\\', '/') for f in result.stdout.strip().split('\n') if f.strip()}
        except Exception:
            pass
        return set()

    @staticmethod
    def from_file_list(file_paths: List[str]) -> Set[str]:
        return set(file_paths)

    @staticmethod
    def from_path(repo_path: str, ref: str = 'HEAD') -> Set[str]:
        import subprocess
        try:
            result = subprocess.run(
                ['git', '-C', repo_path, 'diff', '--name-only', ref],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0:
                return {f.replace('\\', '/') for f in result.stdout.strip().split('\n') if f.strip()}
        except Exception:
            pass
        return set()


class RiskScorer:
    """Scores tests by risk based on change impact and historical data."""

    def __init__(self) -> None:
        self._historical_failures: Dict[str, int] = {}
        self._lock = threading.Lock()

    def record_failure(self, test_name: str) -> None:
        with self._lock:
            self._historical_failures[test_name] = self._historical_failures.get(test_name, 0) + 1

    def score(self, test_name: str, changed_files: Set[str], covered_files: Set[str]) -> float:
        score = 0.0
        overlap = changed_files & covered_files
        score += len(overlap) * 10.0
        with self._lock:
            score += self._historical_failures.get(test_name, 0) * 5.0
        return score


class TestSelector:
    """Selects and prioritizes tests based on code changes and coverage."""

    def __init__(self, coverage: CoverageMap) -> None:
        self._coverage = coverage
        self._scorer = RiskScorer()
        self._selected: List[Tuple[str, float]] = []

    def select(self, changed_files: Set[str], min_score: float = 0.0) -> List[Tuple[str, float]]:
        impacted: Dict[str, float] = {}

        for test_name in self._coverage.all_tests():
            covered = self._coverage.files_for_test(test_name)
            overlap = changed_files & covered
            if overlap:
                risk = self._scorer.score(test_name, changed_files, covered)
                if risk >= min_score:
                    impacted[test_name] = risk

        self._selected = sorted(impacted.items(), key=lambda x: -x[1])
        return self._selected

    def select_by_file(self, changed_files: Set[str], file_path: str) -> List[Tuple[str, float]]:
        tests = self._coverage.tests_for_file(file_path)
        scored = [(t, self._scorer.score(t, changed_files, self._coverage.files_for_test(t)))
                  for t in tests]
        self._selected = sorted(scored, key=lambda x: -x[1])
        return self._selected

    @property
    def selected_tests(self) -> List[str]:
        return [t for t, _ in self._selected]

    @property
    def total_available(self) -> int:
        return len(self._coverage.all_tests())

    @property
    def reduction_pct(self) -> float:
        total = self.total_available
        if total == 0:
            return 0.0
        selected = len(self._selected)
        return round((1 - selected / total) * 100, 1)


class RegressionTestRunner:
    """Executes selected tests and tracks results."""

    def __init__(self) -> None:
        self._results: List[Dict[str, Any]] = []
        self._lock = threading.Lock()

    def run(self, test_name: str, test_fn: Callable[..., bool], timeout_s: float = 30.0) -> Dict[str, Any]:
        t0 = time.perf_counter()
        try:
            passed = test_fn()
            error = None
        except Exception as e:
            passed = False
            error = str(e)
        elapsed = (time.perf_counter() - t0) * 1000
        result = {
            'test': test_name,
            'passed': passed,
            'error': error,
            'elapsed_ms': round(elapsed, 3),
            'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        with self._lock:
            self._results.append(result)
        return result

    def run_batch(self, tests: List[Tuple[str, Callable[..., bool]]], max_workers: int = 4) -> List[Dict[str, Any]]:
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {
                pool.submit(self.run, name, fn): name
                for name, fn in tests
            }
            for future in concurrent.futures.as_completed(futures):
                try:
                    future.result()
                except Exception:
                    pass
        with self._lock:
            return list(self._results)

    @property
    def passed(self) -> int:
        return sum(1 for r in self._results if r.get('passed'))

    @property
    def failed(self) -> int:
        return sum(1 for r in self._results if not r.get('passed'))

    @property
    def total(self) -> int:
        return len(self._results)

    def failures(self) -> List[Dict[str, Any]]:
        return [r for r in self._results if not r.get('passed')]

    def clear(self) -> None:
        with self._lock:
            self._results.clear()


class RegressionTestSelectionPipeline:
    """End-to-end pipeline: coverage → change analysis → selection → execution → report."""

    def __init__(self, coverage: Optional[CoverageMap] = None) -> None:
        self._coverage = coverage or CoverageMap()
        self._selector = TestSelector(self._coverage)
        self._runner = RegressionTestRunner()
        self._change_set: Set[str] = set()
        self._report: Optional[Dict[str, Any]] = None

    def set_change_set(self, changed_files: Set[str]) -> None:
        self._change_set = changed_files

    def detect_changes_from_git(self, ref: str = 'HEAD') -> Set[str]:
        self._change_set = ChangeAnalyzer.from_git_diff(ref)
        return self._change_set

    def select_tests(self, min_score: float = 0.0) -> List[Tuple[str, float]]:
        return self._selector.select(self._change_set, min_score)

    def run_selected(self, test_map: Dict[str, Callable[..., bool]], max_workers: int = 4) -> Dict[str, Any]:
        selected = self._selector.selected_tests
        tests_to_run = [(n, fn) for n, fn in test_map.items() if n in selected]
        self._runner.run_batch(tests_to_run, max_workers)
        self._build_report()
        return self._report or {}

    def _build_report(self) -> None:
        self._report = {
            'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'changed_files': sorted(self._change_set),
            'total_tests_available': self._selector.total_available,
            'tests_selected': len(self._selector.selected_tests),
            'reduction_pct': self._selector.reduction_pct,
            'selected_tests': self._selector.selected_tests,
            'executed': self._runner.total,
            'passed': self._runner.passed,
            'failed': self._runner.failed,
            'failures': self._runner.failures(),
        }

    def report(self) -> Dict[str, Any]:
        if self._report is None:
            return {}
        return dict(self._report)

    def export_report(self, path: str) -> None:
        if self._report:
            with open(path, 'w') as f:
                json.dump(self._report, f, indent=2, default=str)

    def export_artifacts(self, dir: str) -> List[str]:
        os.makedirs(dir, exist_ok=True)
        paths = []
        if self._report:
            rp = os.path.join(dir, 'regression_selection_report.json')
            self.export_report(rp)
            paths.append(rp)
        cp = os.path.join(dir, 'coverage_map.json')
        self._coverage.export(cp)
        paths.append(cp)
        return paths
