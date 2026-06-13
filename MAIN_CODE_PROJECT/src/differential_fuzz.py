"""Differential fuzz testing across application versions for regression detection."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Set, Tuple
import datetime
import hashlib
import inspect
import json
import os
import random
import threading
import time
import traceback


_FUZZ_SEED_POOL = [
    0, 1, -1, 2**31 - 1, -(2**31),
    0.0, 1.0, -1.0, 1e308, -1e308,
    '', 'a', 'abc', 'hello world', '\x00\x01\xff',
    True, False,
    [], [None], [1, 2, 3], [[], []],
    {}, {'a': 1}, {(): None},
    None,
]


class FuzzInputGenerator:
    """Generates diverse inputs for fuzz testing."""

    def __init__(self, seed: int = 0) -> None:
        self._rng = random.Random(seed)
        self._seed = seed

    def random_int(self, min_v: int = -1000, max_v: int = 1000) -> int:
        return self._rng.randint(min_v, max_v)

    def random_float(self) -> float:
        return self._rng.uniform(-1e6, 1e6)

    def random_str(self, max_len: int = 32) -> str:
        length = self._rng.randint(0, max_len)
        return ''.join(chr(self._rng.randint(32, 126)) for _ in range(length))

    def random_bool(self) -> bool:
        return self._rng.choice([True, False])

    def random_list(self, depth: int = 0, max_len: int = 5) -> list:
        if depth > 2:
            return []
        length = self._rng.randint(0, max_len)
        return [self.random_value(depth + 1) for _ in range(length)]

    def random_dict(self, depth: int = 0, max_keys: int = 5) -> Dict[str, Any]:
        if depth > 2:
            return {}
        keys = [f'k{self._rng.randint(0, 20)}' for _ in range(self._rng.randint(0, max_keys))]
        return {k: self.random_value(depth + 1) for k in set(keys)}

    def random_bytes(self, max_len: int = 32) -> bytes:
        length = self._rng.randint(0, max_len)
        return bytes(self._rng.randint(0, 255) for _ in range(length))

    def random_value(self, depth: int = 0) -> Any:
        choices = [
            lambda: self.random_int(),
            lambda: self.random_int(-1_000_000, 1_000_000),
            lambda: self.random_float(),
            lambda: self.random_str(),
            lambda: self.random_bool(),
            lambda: None,
            lambda: self.random_list(depth),
            lambda: self.random_dict(depth),
            lambda: self.random_bytes(),
        ]
        return self._rng.choice(choices)()

    def generate_batch(self, n: int = 100) -> List[Any]:
        return [self.random_value() for _ in range(n)]

    def generate_kwargs(self, param_names: List[str], n: int = 100) -> List[Dict[str, Any]]:
        batches: List[Dict[str, Any]] = []
        for _ in range(n):
            kwargs = {}
            for p in param_names:
                kwargs[p] = self.random_value()
            batches.append(kwargs)
        return batches


class FuzzInput:
    """A single fuzz input with optional metadata."""

    def __init__(self, input_data: Any, input_id: str = '') -> None:
        self.data = input_data
        self.id = input_id or hashlib.md5(repr(input_data).encode()).hexdigest()[:12]
        self.size = len(repr(input_data))

    def serialize(self) -> str:
        return json.dumps({'id': self.id, 'data': self.data}, default=str)

    @staticmethod
    def deserialize(s: str) -> FuzzInput:
        d = json.loads(s)
        return FuzzInput(d['data'], d['id'])


class ExecutionResult:
    """Result of executing a target with a fuzz input."""

    def __init__(self, version: str, input_id: str, output: Any, error: Optional[str] = None, elapsed_ms: float = 0.0) -> None:
        self.version = version
        self.input_id = input_id
        self.output = output
        self.error = error
        self.elapsed_ms = elapsed_ms

    def to_dict(self) -> Dict[str, Any]:
        return {
            'version': self.version,
            'input_id': self.input_id,
            'output': repr(self.output),
            'error': self.error,
            'elapsed_ms': round(self.elapsed_ms, 3),
        }


class DifferentialResult:
    """Comparison result between two version executions for one input."""

    def __init__(self, input_id: str, input_data: Any, result_a: ExecutionResult, result_b: ExecutionResult) -> None:
        self.input_id = input_id
        self.input_data = input_data
        self.result_a = result_a
        self.result_b = result_b
        self._diff_key = self._compute_diff_key()

    def _compute_diff_key(self) -> str:
        if self.result_a.error or self.result_b.error:
            return 'error_diff' if self.result_a.error != self.result_b.error else 'both_error'
        try:
            eq = self.result_a.output == self.result_b.output
            return 'match' if eq else 'mismatch'
        except Exception:
            return 'compare_error'

    @property
    def is_diff(self) -> bool:
        return self._diff_key == 'mismatch' or self._diff_key == 'error_diff'

    @property
    def diff_type(self) -> str:
        return self._diff_key

    def to_dict(self) -> Dict[str, Any]:
        return {
            'input_id': self.input_id,
            'input': repr(self.input_data),
            'diff_type': self._diff_key,
            'version_a': self.result_a.to_dict(),
            'version_b': self.result_b.to_dict(),
        }


class DifferentialFuzzTester:
    """Executes fuzz inputs against two versions and detects differences."""

    def __init__(self, version_a: Callable, version_b: Callable, name_a: str = 'old', name_b: str = 'new') -> None:
        self._target_a = version_a
        self._target_b = version_b
        self._name_a = name_a
        self._name_b = name_b
        self._results: List[DifferentialResult] = []
        self._lock = threading.Lock()

    def _execute(self, fn: Callable, inp: Any, version: str) -> ExecutionResult:
        t0 = time.perf_counter()
        try:
            if isinstance(inp, dict):
                output = fn(**inp)
            elif isinstance(inp, (list, tuple)):
                output = fn(*inp)
            else:
                output = fn(inp)
            error = None
        except Exception as e:
            output = None
            error = f'{type(e).__name__}: {e}'
        elapsed = (time.perf_counter() - t0) * 1000
        return ExecutionResult(version, '', output, error, elapsed)

    def run_single(self, fuzz_input: FuzzInput) -> DifferentialResult:
        result_a = self._execute(self._target_a, fuzz_input.data, self._name_a)
        result_b = self._execute(self._target_b, fuzz_input.data, self._name_b)
        diff = DifferentialResult(fuzz_input.id, fuzz_input.data, result_a, result_b)
        with self._lock:
            self._results.append(diff)
        return diff

    def run_batch(self, inputs: List[FuzzInput], max_workers: int = 4) -> List[DifferentialResult]:
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {pool.submit(self.run_single, inp): inp for inp in inputs}
            for future in concurrent.futures.as_completed(futures):
                try:
                    future.result()
                except Exception:
                    pass
        with self._lock:
            return list(self._results)

    def differences(self) -> List[DifferentialResult]:
        return [r for r in self._results if r.is_diff]

    def matches(self) -> List[DifferentialResult]:
        return [r for r in self._results if not r.is_diff]

    def clear(self) -> None:
        with self._lock:
            self._results.clear()


class CaseMinimizer:
    """Minimizes a fuzz input to the smallest variant that still reproduces a difference."""

    def __init__(self, tester: DifferentialFuzzTester) -> None:
        self._tester = tester

    def minimize(self, result: DifferentialResult, max_steps: int = 50) -> DifferentialResult:
        if not result.is_diff:
            return result
        current = result.input_data
        best = result

        for _ in range(max_steps):
            reduced = self._try_reduce(current)
            if reduced is None:
                break
            fuzz = FuzzInput(reduced)
            new_result = self._tester.run_single(fuzz)
            if new_result.is_diff:
                current = reduced
                best = new_result
        return best

    def _try_reduce(self, data: Any) -> Any:
        if isinstance(data, list):
            if len(data) <= 1:
                return None
            idx = random.randrange(len(data))
            return data[:idx] + data[idx + 1:]
        if isinstance(data, dict):
            if not data:
                return None
            k = random.choice(list(data.keys()))
            c = dict(data)
            del c[k]
            return c
        if isinstance(data, str):
            if len(data) <= 1:
                return None
            idx = random.randrange(len(data))
            return data[:idx] + data[idx + 1:]
        if isinstance(data, bytes):
            if len(data) <= 1:
                return None
            idx = random.randrange(len(data))
            return data[:idx] + data[idx + 1:]
        if isinstance(data, int) or isinstance(data, float):
            return data // 2 if data != 0 else None
        return None


class FuzzCampaign:
    """Manages a large-scale fuzz campaign with reporting."""

    def __init__(self, tester: DifferentialFuzzTester, name: str = 'campaign') -> None:
        self._tester = tester
        self._name = name
        self._inputs: List[FuzzInput] = []
        self._generator = FuzzInputGenerator()
        self._start_time: Optional[float] = None

    def generate_inputs(self, count: int = 1000) -> List[FuzzInput]:
        values = self._generator.generate_batch(count)
        self._inputs = [FuzzInput(v) for v in values]
        return self._inputs

    def run(self, max_workers: int = 4) -> List[DifferentialResult]:
        self._start_time = time.time()
        if not self._inputs:
            self.generate_inputs(100)
        return self._tester.run_batch(self._inputs, max_workers)

    def report(self) -> Dict[str, Any]:
        diffs = self._tester.differences()
        matches = self._tester.matches()
        elapsed = (time.time() - self._start_time) if self._start_time else 0.0
        return {
            'campaign': self._name,
            'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'total_inputs': len(self._tester._results),
            'differences': len(diffs),
            'matches': len(matches),
            'diff_rate': round(len(diffs) / max(len(self._tester._results), 1) * 100, 2),
            'elapsed_seconds': round(elapsed, 2),
        }

    def export_results(self, path: str) -> None:
        report = self.report()
        report['differences_detail'] = [d.to_dict() for d in self._tester.differences()]
        with open(path, 'w') as f:
            json.dump(report, f, indent=2, default=str)

    def export_minimized(self, dir: str) -> List[str]:
        os.makedirs(dir, exist_ok=True)
        paths = []
        minimizer = CaseMinimizer(self._tester)
        for i, diff in enumerate(self._tester.differences()[:20]):
            minimized = minimizer.minimize(diff)
            mp = os.path.join(dir, f'minimized_{i}_{diff.input_id}.json')
            with open(mp, 'w') as f:
                json.dump({
                    'original': repr(diff.input_data),
                    'minimized': repr(minimized.input_data),
                    'diff_type': minimized.diff_type,
                }, f, indent=2, default=str)
            paths.append(mp)
        return paths


class DifferentialFuzzRunner:
    """Top-level differential fuzz testing interface."""

    def __init__(self) -> None:
        self._last_campaign: Optional[FuzzCampaign] = None

    def create_campaign(self, version_a: Callable, version_b: Callable, name_a: str = 'old', name_b: str = 'new', name: str = 'campaign') -> FuzzCampaign:
        tester = DifferentialFuzzTester(version_a, version_b, name_a, name_b)
        campaign = FuzzCampaign(tester, name)
        self._last_campaign = campaign
        return campaign

    def run_campaign(self, campaign: Optional[FuzzCampaign] = None, input_count: int = 500, max_workers: int = 4) -> Dict[str, Any]:
        c = campaign or self._last_campaign
        if c is None:
            raise ValueError('no campaign created')
        if not c._inputs:
            c.generate_inputs(input_count)
        c.run(max_workers)
        return c.report()

    def export_artifacts(self, dir: str) -> List[str]:
        os.makedirs(dir, exist_ok=True)
        paths = []
        if self._last_campaign:
            rp = os.path.join(dir, 'differential_fuzz_report.json')
            self._last_campaign.export_results(rp)
            paths.append(rp)
            mini_dir = os.path.join(dir, 'minimized')
            paths.extend(self._last_campaign.export_minimized(mini_dir))
        return paths
