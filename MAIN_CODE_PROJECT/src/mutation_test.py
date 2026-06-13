"""AST-based mutation testing framework for measuring test suite effectiveness."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Set, Tuple
import ast
import copy
import datetime
import hashlib
import inspect
import json
import os
import threading
import time
import traceback
import uuid


_MUTATION_OPERATORS = {
    'ReplaceBinOp': [
        (ast.Add, ast.Sub), (ast.Sub, ast.Add),
        (ast.Mult, ast.Div), (ast.Div, ast.Mult),
        (ast.Mod, ast.Mult), (ast.Pow, ast.Mult),
        (ast.BitAnd, ast.BitOr), (ast.BitOr, ast.BitAnd),
        (ast.LShift, ast.RShift), (ast.RShift, ast.LShift),
    ],
    'ReplaceCmpOp': [
        (ast.Eq, ast.NotEq), (ast.NotEq, ast.Eq),
        (ast.Lt, ast.Gt), (ast.Gt, ast.Lt),
        (ast.LtE, ast.GtE), (ast.GtE, ast.LtE),
        (ast.Lt, ast.LtE), (ast.Gt, ast.GtE),
    ],
    'ReplaceBoolOp': [
        (ast.And, ast.Or), (ast.Or, ast.And),
    ],
    'ReplaceUnaryOp': [
        (ast.Not, ast.USub),
    ],
    'DeleteIfBody': [],
    'DeleteWhileBody': [],
    'ReplaceConstant': [],
    'ReplaceName': [],
}


def _ast_op_name(op: Any) -> str:
    return op.__class__.__name__


class Mutation:
    """A single mutation applied to source code."""

    def __init__(self, mutator: str, location: str, original: str, mutated: str, lineno: int) -> None:
        self.id = uuid.uuid4().hex[:12]
        self.mutator = mutator
        self.location = location
        self.original = original
        self.mutated = mutated
        self.lineno = lineno

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'mutator': self.mutator,
            'location': self.location,
            'original': self.original,
            'mutated': self.mutated,
            'lineno': self.lineno,
        }


class Mutant:
    """A mutated variant of the source code with execution state."""

    def __init__(self, mutation: Mutation, source: str) -> None:
        self.mutation = mutation
        self.source = source
        self.killed = False
        self.error: Optional[str] = None
        self.elapsed_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'mutation': self.mutation.to_dict(),
            'killed': self.killed,
            'error': self.error,
            'elapsed_ms': round(self.elapsed_ms, 3),
        }


class BinOpReplacer(ast.NodeTransformer):
    def __init__(self, target_op: Any, replacement_op: Any) -> None:
        self._target = target_op
        self._replacement = replacement_op
        self.mutations: List[Mutation] = []

    def visit_BinOp(self, node: ast.BinOp) -> ast.AST:
        if isinstance(node.op, self._target):
            original = _ast_op_name(node.op)
            mutated = _ast_op_name(self._replacement())
            self.mutations.append(Mutation(
                'ReplaceBinOp', f'BinOp.{original}->{mutated}',
                original, mutated, node.lineno or 0,
            ))
            node.op = self._replacement()
        self.generic_visit(node)
        return node


class CmpOpReplacer(ast.NodeTransformer):
    def __init__(self, target_op: Any, replacement_op: Any) -> None:
        self._target = target_op
        self._replacement = replacement_op
        self.mutations: List[Mutation] = []

    def visit_Compare(self, node: ast.Compare) -> ast.AST:
        new_ops: List[ast.cmpop] = []
        for op in node.ops:
            if isinstance(op, self._target):
                original = _ast_op_name(op)
                mutated = _ast_op_name(self._replacement())
                self.mutations.append(Mutation(
                    'ReplaceCmpOp', f'Compare.{original}->{mutated}',
                    original, mutated, node.lineno or 0,
                ))
                new_ops.append(self._replacement())
            else:
                new_ops.append(op)
        node.ops = new_ops
        self.generic_visit(node)
        return node


class BoolOpReplacer(ast.NodeTransformer):
    def __init__(self, target_op: Any, replacement_op: Any) -> None:
        self._target = target_op
        self._replacement = replacement_op
        self.mutations: List[Mutation] = []

    def visit_BoolOp(self, node: ast.BoolOp) -> ast.AST:
        if isinstance(node.op, self._target):
            original = _ast_op_name(node.op)
            mutated = _ast_op_name(self._replacement())
            self.mutations.append(Mutation(
                'ReplaceBoolOp', f'BoolOp.{original}->{mutated}',
                original, mutated, node.lineno or 0,
            ))
            node.op = self._replacement()
        self.generic_visit(node)
        return node


class IfBodyDeleter(ast.NodeTransformer):
    def __init__(self) -> None:
        self.mutations: List[Mutation] = []

    def visit_If(self, node: ast.If) -> ast.AST:
        if node.body:
            self.mutations.append(Mutation(
                'DeleteIfBody', 'If.body',
                f'body:{len(node.body)} stmts', 'deleted', node.lineno or 0,
            ))
            node.body = [ast.Pass()]
        self.generic_visit(node)
        return node


class ConstantReplacer(ast.NodeTransformer):
    def __init__(self) -> None:
        self.mutations: List[Mutation] = []
        self._count = 0

    def visit_Constant(self, node: ast.Constant) -> ast.AST:
        if isinstance(node.value, bool):
            self.mutations.append(Mutation(
                'ReplaceConstant', 'bool flip',
                str(node.value), str(not node.value), node.lineno or 0,
            ))
            node.value = not node.value
        elif isinstance(node.value, int) and node.value != 0:
            orig = node.value
            node.value = node.value + 1
            self.mutations.append(Mutation(
                'ReplaceConstant', 'int +1',
                str(orig), str(node.value), node.lineno or 0,
            ))
        elif isinstance(node.value, str) and len(node.value) > 0:
            orig = node.value
            node.value = node.value + '_mut'
            self.mutations.append(Mutation(
                'ReplaceConstant', 'str append',
                orig, node.value, node.lineno or 0,
            ))
        self.generic_visit(node)
        return node


class MutationGenerator:
    """Generates mutants by applying AST transformations."""

    def __init__(self, source: str) -> None:
        self._source = source
        self._tree = ast.parse(source)

    def generate_all(self) -> List[Mutant]:
        mutants: List[Mutant] = []

        for target_op, replacement_op in _MUTATION_OPERATORS.get('ReplaceBinOp', []):
            replacer = BinOpReplacer(target_op, replacement_op)
            tree = copy.deepcopy(self._tree)
            replacer.visit(tree)
            for m in replacer.mutations:
                mutated_source = ast.unparse(tree)
                mutants.append(Mutant(m, mutated_source))

        for target_op, replacement_op in _MUTATION_OPERATORS.get('ReplaceCmpOp', []):
            replacer = CmpOpReplacer(target_op, replacement_op)
            tree = copy.deepcopy(self._tree)
            replacer.visit(tree)
            for m in replacer.mutations:
                mutated_source = ast.unparse(tree)
                mutants.append(Mutant(m, mutated_source))

        for target_op, replacement_op in _MUTATION_OPERATORS.get('ReplaceBoolOp', []):
            replacer = BoolOpReplacer(target_op, replacement_op)
            tree = copy.deepcopy(self._tree)
            replacer.visit(tree)
            for m in replacer.mutations:
                mutated_source = ast.unparse(tree)
                mutants.append(Mutant(m, mutated_source))

        deleter = IfBodyDeleter()
        tree = copy.deepcopy(self._tree)
        deleter.visit(tree)
        for m in deleter.mutations:
            mutated_source = ast.unparse(tree)
            mutants.append(Mutant(m, mutated_source))

        const = ConstantReplacer()
        tree = copy.deepcopy(self._tree)
        const.visit(tree)
        for m in const.mutations:
            mutated_source = ast.unparse(tree)
            mutants.append(Mutant(m, mutated_source))

        return mutants


class MutationTestRunner:
    """Runs a test function against each mutant to determine killed/survived."""

    def __init__(self, mutants: List[Mutant], test_fn: Callable[..., bool]) -> None:
        self._mutants = mutants
        self._test_fn = test_fn
        self._lock = threading.Lock()

    def run_all(self, max_workers: int = 4, timeout_s: float = 10.0) -> List[Mutant]:
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {pool.submit(self._test_mutant, m): m for m in self._mutants}
            for future in concurrent.futures.as_completed(futures, timeout=timeout_s + 5):
                try:
                    future.result(timeout=timeout_s)
                except Exception as e:
                    m = futures[future]
                    with self._lock:
                        m.killed = False
                        m.error = f'timeout/error: {e}'
        return self._mutants

    def _test_mutant(self, mutant: Mutant) -> None:
        t0 = time.perf_counter()
        try:
            compiled = compile(mutant.source, '<mutant>', 'exec')
            ns: Dict[str, Any] = {}
            exec(compiled, ns)
            passed = self._test_fn(ns)
            mutant.killed = not passed
        except Exception as e:
            mutant.killed = False
            mutant.error = f'{e}'
        mutant.elapsed_ms = (time.perf_counter() - t0) * 1000


class MutationReport:
    """Aggregates mutation testing results and produces metrics."""

    def __init__(self, mutants: List[Mutant], original_source: str = '') -> None:
        self._mutants = mutants
        self._original = original_source

    @property
    def total(self) -> int:
        return len(self._mutants)

    @property
    def killed(self) -> int:
        return sum(1 for m in self._mutants if m.killed)

    @property
    def survived(self) -> int:
        return sum(1 for m in self._mutants if not m.killed)

    @property
    def score(self) -> float:
        return round(self.killed / self.total * 100, 1) if self.total else 0.0

    def surviving_mutants(self) -> List[Mutant]:
        return [m for m in self._mutants if not m.killed]

    def killed_mutants(self) -> List[Mutant]:
        return [m for m in self._mutants if m.killed]

    def summary(self) -> Dict[str, Any]:
        return {
            'total_mutants': self.total,
            'killed': self.killed,
            'survived': self.survived,
            'mutation_score': self.score,
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            'summary': self.summary(),
            'mutants': [m.to_dict() for m in self._mutants],
        }

    def report_text(self) -> str:
        lines = [
            'Mutation Testing Report',
            f'  Total mutants: {self.total}',
            f'  Killed: {self.killed}',
            f'  Survived: {self.survived}',
            f'  Mutation Score: {self.score}%',
        ]
        survivors = self.surviving_mutants()
        if survivors:
            lines.append('  Surviving Mutations (test gaps):')
            for m in survivors[:20]:
                lines.append(f'    [{m.mutation.id}] {m.mutation.mutator} at L{m.mutation.lineno}: '
                             f'{m.mutation.original} -> {m.mutation.mutated}')
            if len(survivors) > 20:
                lines.append(f'    ... and {len(survivors) - 20} more')
        return '\n'.join(lines)

    def export(self, path: str) -> None:
        with open(path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)


class MutationTester:
    """Top-level mutation testing interface."""

    def __init__(self) -> None:
        self._last_report: Optional[MutationReport] = None

    def test_function(self, fn: Callable, test_fn: Callable[..., bool], max_workers: int = 4, timeout_s: float = 10.0) -> MutationReport:
        try:
            source = inspect.getsource(fn)
        except (OSError, TypeError):
            source = ''
        gen = MutationGenerator(source)
        mutants = gen.generate_all()
        runner = MutationTestRunner(mutants, test_fn)
        runner.run_all(max_workers, timeout_s)
        report = MutationReport(mutants, source)
        self._last_report = report
        return report

    def test_source(self, source: str, test_fn: Callable[..., bool], max_workers: int = 4, timeout_s: float = 10.0) -> MutationReport:
        gen = MutationGenerator(source)
        mutants = gen.generate_all()
        runner = MutationTestRunner(mutants, test_fn)
        runner.run_all(max_workers, timeout_s)
        report = MutationReport(mutants, source)
        self._last_report = report
        return report

    @property
    def last_report(self) -> Optional[MutationReport]:
        return self._last_report

    def export_artifacts(self, dir: str) -> List[str]:
        os.makedirs(dir, exist_ok=True)
        paths = []
        if self._last_report:
            rp = os.path.join(dir, 'mutation_report.json')
            self._last_report.export(rp)
            paths.append(rp)
        return paths
