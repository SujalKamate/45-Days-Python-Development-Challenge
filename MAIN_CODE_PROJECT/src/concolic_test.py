"""Concolic testing framework combining concrete execution with symbolic path exploration."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union
import collections
import copy
import datetime
import hashlib
import inspect
import json
import os
import random
import threading
import time


class SymbolicExpr:
    """Tree node representing a symbolic expression."""

    def __init__(self, op: str, args: List[Any], label: Optional[str] = None) -> None:
        self.op = op
        self.args = args
        self.label = label

    def __repr__(self) -> str:
        if self.label:
            return self.label
        return f'{self.op}({", ".join(repr(a) for a in self.args)})'

    def simplify(self) -> SymbolicExpr:
        if self.op == 'input' and self.label:
            return self
        const_args = [a.simplify() if isinstance(a, SymbolicExpr) else a for a in self.args]
        if self.op == 'add':
            nums = [a for a in const_args if isinstance(a, (int, float))]
            if len(nums) == len(const_args):
                return sum(nums)
        if self.op == 'sub':
            if all(isinstance(a, (int, float)) for a in const_args):
                return const_args[0] - const_args[1]
        if self.op == 'mul':
            nums = [a for a in const_args if isinstance(a, (int, float))]
            if len(nums) == len(const_args):
                result = 1
                for n in nums:
                    result *= n
                return result
        return SymbolicExpr(self.op, const_args, self.label)

    def to_dict(self) -> Any:
        if self.label:
            return {'type': 'input', 'label': self.label}
        return {'op': self.op, 'args': [a.to_dict() if isinstance(a, SymbolicExpr) else a for a in self.args]}

    @staticmethod
    def from_dict(d: Any) -> SymbolicExpr:
        if isinstance(d, dict):
            if d.get('type') == 'input':
                return SymbolicExpr('input', [], d['label'])
            args = [SymbolicExpr.from_dict(a) for a in d.get('args', [])]
            return SymbolicExpr(d['op'], args)
        return d


class PathCondition:
    """A single branch condition encountered during execution."""

    def __init__(self, expr: SymbolicExpr, taken: bool, line: int) -> None:
        self.expr = expr
        self.taken = taken
        self.line = line

    def negated(self) -> PathCondition:
        return PathCondition(self.expr, not self.taken, self.line)

    def __repr__(self) -> str:
        return f'L{self.line}: {self.expr} -> {"T" if self.taken else "F"}'


class ConcolicState:
    """Maps variable names to (concrete_value, symbolic_expr) pairs."""

    def __init__(self) -> None:
        self._symbols: Dict[str, SymbolicExpr] = {}
        self._concrete: Dict[str, Any] = {}

    def declare_input(self, name: str, value: Any) -> Any:
        self._symbols[name] = SymbolicExpr('input', [], name)
        self._concrete[name] = value
        return value

    def get_symbolic(self, name: str) -> Optional[SymbolicExpr]:
        return self._symbols.get(name)

    def get_concrete(self, name: str) -> Any:
        return self._concrete.get(name)

    def set_var(self, name: str, concrete: Any, symbolic: Optional[SymbolicExpr] = None) -> None:
        self._concrete[name] = concrete
        if symbolic is not None:
            self._symbols[name] = symbolic

    def tracked_names(self) -> List[str]:
        return list(self._symbols.keys())

    def concolic(self, name: str) -> Tuple[Any, Optional[SymbolicExpr]]:
        return self._concrete.get(name), self._symbols.get(name)


class ConstraintSolver:
    """Solves path constraints by negating branch conditions and computing new inputs."""

    def __init__(self) -> None:
        self._max_attempts = 100

    def solve(self, path_conditions: List[PathCondition], negate_idx: int, initial_inputs: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        new_inputs = dict(initial_inputs)
        target = path_conditions[negate_idx]
        negated = target.negated()

        attempts = 0
        while attempts < self._max_attempts:
            attempts += 1
            candidate = self._mutate(new_inputs, target)
            if self._check_condition(negated, candidate):
                return candidate
        return None

    def _mutate(self, inputs: Dict[str, Any], condition: PathCondition) -> Dict[str, Any]:
        candidate = dict(inputs)
        for k in candidate:
            v = candidate[k]
            if isinstance(v, int):
                delta = random.choice([-5, -3, -1, 1, 3, 5])
                candidate[k] = v + delta
            elif isinstance(v, float):
                candidate[k] = v + random.uniform(-5.0, 5.0)
            elif isinstance(v, str):
                if v and random.random() < 0.5:
                    clist = list(v)
                    if clist:
                        idx = random.randrange(len(clist))
                        clist[idx] = chr((ord(clist[idx]) + random.choice([-1, 1])) % 256)
                        candidate[k] = ''.join(clist)
            elif isinstance(v, bool):
                candidate[k] = not v
        return candidate

    def _check_condition(self, pc: PathCondition, inputs: Dict[str, Any]) -> bool:
        try:
            val = self._eval_expr(pc.expr, inputs)
            if isinstance(val, bool):
                return val == pc.taken
            return False
        except Exception:
            return False

    def _eval_expr(self, expr: Any, inputs: Dict[str, Any]) -> Any:
        if isinstance(expr, SymbolicExpr):
            if expr.op == 'input' and expr.label:
                return inputs.get(expr.label, 0)
            args = [self._eval_expr(a, inputs) if isinstance(a, SymbolicExpr) else a for a in expr.args]
            if expr.op == 'add':
                return sum(args)
            if expr.op == 'sub':
                return args[0] - args[1]
            if expr.op == 'mul':
                result = 1
                for a in args:
                    result *= a
                return result
            if expr.op == 'eq':
                return args[0] == args[1]
            if expr.op == 'ne':
                return args[0] != args[1]
            if expr.op == 'lt':
                return args[0] < args[1]
            if expr.op == 'le':
                return args[0] <= args[1]
            if expr.op == 'gt':
                return args[0] > args[1]
            if expr.op == 'ge':
                return args[0] >= args[1]
            if expr.op == 'and':
                return all(args)
            if expr.op == 'or':
                return any(args)
            if expr.op == 'not':
                return not args[0]
            if expr.op == 'neg':
                return -args[0]
            return args[0] if args else 0
        return expr


class ConcolicTracer:
    """Traces a function execution, recording path conditions symbolically."""

    def __init__(self) -> None:
        self._state = ConcolicState()
        self._path: List[PathCondition] = []
        self._coverage: Set[int] = set()
        self._result: Any = None

    def declare_input(self, name: str, value: Any) -> Any:
        return self._state.declare_input(name, value)

    def _make_symbolic(self, val: Any, op: str, args: List[Any]) -> Any:
        sym_args = []
        for a in args:
            if isinstance(a, SymbolicExpr):
                sym_args.append(a)
            elif isinstance(a, int) or isinstance(a, float):
                sym_args.append(a)
            elif isinstance(a, bool):
                sym_args.append(a)
            else:
                sym_args.append(a)
        return SymbolicExpr(op, sym_args)

    def _record_branch(self, condition: Any, line: int) -> bool:
        result = bool(condition)
        sym = None
        if isinstance(condition, SymbolicExpr):
            sym = condition
        elif hasattr(condition, '_sym_expr'):
            sym = condition._sym_expr
        if sym is not None:
            self._path.append(PathCondition(sym, result, line))
        self._coverage.add(line)
        return result

    def trace(self, fn: Callable, *args: Any, **kwargs: Any) -> Any:
        import ast as _ast
        try:
            source = inspect.getsource(fn)
            lines = source.split('\n')
        except (OSError, TypeError):
            lines = ['unknown']
        result = fn(*args, **kwargs)
        self._result = result
        return result

    @property
    def path(self) -> List[PathCondition]:
        return self._path

    @property
    def coverage(self) -> Set[int]:
        return self._coverage

    def path_signature(self) -> str:
        sig = '-'.join(f'{p.line}:{"T" if p.taken else "F"}' for p in self._path)
        return hashlib.md5(sig.encode()).hexdigest()[:12]

    def result(self) -> Any:
        return self._result


class PathExplorer:
    """Explores execution paths by negating branch conditions iteratively."""

    def __init__(self, timeout_s: float = 30.0) -> None:
        self._solver = ConstraintSolver()
        self._explored: Set[str] = set()
        self._test_inputs: List[Dict[str, Any]] = []
        self._timeout = timeout_s
        self._coverage: Set[int] = set()
        self._lock = threading.Lock()

    def explore(self, fn: Callable, initial_inputs: Dict[str, Any], max_paths: int = 20) -> List[Dict[str, Any]]:
        start = time.time()
        queue = collections.deque([initial_inputs])
        self._test_inputs = [initial_inputs]
        seen_sigs: Set[str] = set()

        while queue and len(self._test_inputs) < max_paths and (time.time() - start) < self._timeout:
            inputs = queue.popleft()
            tracer = ConcolicTracer()
            for k, v in inputs.items():
                tracer.declare_input(k, v)
            try:
                tracer.trace(fn, **inputs)
            except Exception:
                continue

            sig = tracer.path_signature()
            with self._lock:
                if sig in seen_sigs:
                    continue
                seen_sigs.add(sig)
                self._coverage.update(tracer.coverage)
                self._explored.add(sig)

            path = tracer.path
            for idx in range(len(path) - 1, -1, -1):
                new_inputs = self._solver.solve(path, idx, inputs)
                if new_inputs:
                    t2 = ConcolicTracer()
                    for k2, v2 in new_inputs.items():
                        t2.declare_input(k2, v2)
                    try:
                        t2.trace(fn, **new_inputs)
                        s2 = t2.path_signature()
                        if s2 not in seen_sigs:
                            queue.append(new_inputs)
                            self._test_inputs.append(new_inputs)
                            seen_sigs.add(s2)
                            with self._lock:
                                self._coverage.update(t2.coverage)
                    except Exception:
                        continue
                    if len(self._test_inputs) >= max_paths:
                        break

        return self._test_inputs

    def covered_lines(self) -> Set[int]:
        with self._lock:
            return set(self._coverage)

    def explored_paths(self) -> Set[str]:
        with self._lock:
            return set(self._explored)

    def export_test_inputs(self, path: str) -> None:
        payload = {
            'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'num_inputs': len(self._test_inputs),
            'inputs': self._test_inputs,
            'coverage_lines': sorted(self._coverage),
        }
        with open(path, 'w') as f:
            json.dump(payload, f, indent=2, default=str)

    def load_test_inputs(self, path: str) -> List[Dict[str, Any]]:
        with open(path) as f:
            data = json.load(f)
            self._test_inputs = data.get('inputs', [])
            return self._test_inputs


class ConcolicTestRunner:
    """High-level interface for running concolic tests."""

    def __init__(self) -> None:
        self._explorer = PathExplorer()
        self._tracer: Optional[ConcolicTracer] = None

    def generate_inputs(self, fn: Callable, initial_inputs: Dict[str, Any], max_paths: int = 20) -> List[Dict[str, Any]]:
        return self._explorer.explore(fn, initial_inputs, max_paths)

    def trace(self, fn: Callable, **inputs: Any) -> ConcolicTracer:
        tracer = ConcolicTracer()
        for k, v in inputs.items():
            tracer.declare_input(k, v)
        tracer.trace(fn, **inputs)
        self._tracer = tracer
        return tracer

    def coverage_report(self) -> Dict[str, Any]:
        return {
            'covered_lines': sorted(self._explorer.covered_lines()),
            'paths_explored': len(self._explorer.explored_paths()),
            'num_test_inputs': len(self._explorer._test_inputs) if hasattr(self._explorer, '_test_inputs') else 0,
        }

    def export_artifacts(self, dir: str) -> List[str]:
        os.makedirs(dir, exist_ok=True)
        paths = []
        inputs_path = os.path.join(dir, 'test_inputs.json')
        self._explorer.export_test_inputs(inputs_path)
        paths.append(inputs_path)
        report_path = os.path.join(dir, 'coverage_report.json')
        with open(report_path, 'w') as f:
            json.dump(self.coverage_report(), f, indent=2)
        paths.append(report_path)
        return paths
