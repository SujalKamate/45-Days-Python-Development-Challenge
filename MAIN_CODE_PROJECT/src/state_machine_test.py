"""Property-based state machine testing for comprehensive state validation."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Type
import copy
import datetime
import hashlib
import inspect
import json
import os
import random
import threading
import time
import traceback


class Operation:
    """A single state transition operation with pre/post conditions."""

    def __init__(
        self,
        name: str,
        run: Callable[..., Any],
        args_generator: Optional[Callable[[random.Random], tuple]] = None,
        precond: Optional[Callable[..., bool]] = None,
        postcond: Optional[Callable[..., bool]] = None,
    ) -> None:
        self.name = name
        self._run = run
        self._args_gen = args_generator or (lambda rng: ())
        self._precond = precond or (lambda *a, **kw: True)
        self._postcond = postcond or (lambda *a, **kw: True)

    def generate_args(self, rng: random.Random) -> tuple:
        args = self._args_gen(rng)
        if not isinstance(args, tuple):
            args = (args,)
        return args

    def check_precond(self, state: Any, *args: Any, **kwargs: Any) -> bool:
        try:
            return self._precond(state, *args, **kwargs)
        except Exception:
            return False

    def run(self, state: Any, *args: Any, **kwargs: Any) -> Any:
        return self._run(state, *args, **kwargs)

    def check_postcond(self, state: Any, *args: Any, **kwargs: Any) -> bool:
        try:
            return self._postcond(state, *args, **kwargs)
        except Exception:
            return False


class StateMachine:
    """Base model of application state with operations and invariants."""

    def __init__(self) -> None:
        self._operations: List[Operation] = []
        self._invariants: List[Callable[..., bool]] = []
        self._state: Any = None

    def add_operation(self, op: Operation) -> None:
        self._operations.append(op)

    def add_invariant(self, fn: Callable[..., bool]) -> None:
        self._invariants.append(fn)

    @property
    def operations(self) -> List[Operation]:
        return self._operations

    @property
    def invariants(self) -> List[Callable[..., bool]]:
        return self._invariants

    def init_state(self) -> Any:
        return {}

    def check_invariants(self, state: Any) -> List[str]:
        failures: List[str] = []
        for fn in self._invariants:
            try:
                if not fn(state):
                    failures.append(getattr(fn, '__name__', repr(fn)))
            except Exception as e:
                failures.append(f'{getattr(fn, "__name__", repr(fn))}: {e}')
        return failures


class ExecutionStep:
    """A single executed operation in a sequence."""

    def __init__(self, op_name: str, args: tuple, pre_state: Any, post_state: Any, result: Any, error: Optional[str] = None) -> None:
        self.op_name = op_name
        self.args = args
        self.pre_state = copy.deepcopy(pre_state)
        self.post_state = copy.deepcopy(post_state)
        self.result = result
        self.error = error

    def to_dict(self) -> Dict[str, Any]:
        return {
            'operation': self.op_name,
            'args': repr(self.args),
            'pre_state': repr(self.pre_state),
            'post_state': repr(self.post_state),
            'result': repr(self.result),
            'error': self.error,
        }


class SequenceResult:
    """Result of executing a sequence of operations."""

    def __init__(self) -> None:
        self.steps: List[ExecutionStep] = []
        self.invariant_failures: List[str] = []
        self.failed_step: Optional[int] = None
        self.error: Optional[str] = None

    @property
    def passed(self) -> bool:
        return self.failed_step is None and not self.invariant_failures

    def to_dict(self) -> Dict[str, Any]:
        return {
            'passed': self.passed,
            'steps': [s.to_dict() for s in self.steps],
            'invariant_failures': self.invariant_failures,
            'failed_step': self.failed_step,
            'error': self.error,
        }


class OperationSequenceGenerator:
    """Generates random sequences of operations respecting preconditions."""

    def __init__(self, machine: StateMachine, rng: Optional[random.Random] = None) -> None:
        self._machine = machine
        self._rng = rng or random.Random()

    def generate(self, min_len: int = 3, max_len: int = 20) -> List[Operation]:
        length = self._rng.randint(min_len, max_len)
        state = self._machine.init_state()
        sequence: List[Operation] = []
        ops = self._machine.operations

        for _ in range(length):
            candidates = [op for op in ops if op.check_precond(state, *op.generate_args(self._rng))]
            if not candidates:
                continue
            op = self._rng.choice(candidates)
            sequence.append(op)
            args = op.generate_args(self._rng)
            try:
                result = op.run(state, *args)
                if not op.check_postcond(state, *args):
                    pass
            except Exception:
                pass
        return sequence


class SequenceExecutor:
    """Executes an operation sequence against the state machine and validates."""

    def __init__(self, machine: StateMachine) -> None:
        self._machine = machine

    def execute(self, ops: List[Operation], args_list: List[tuple]) -> SequenceResult:
        result = SequenceResult()
        state = self._machine.init_state()

        for i, (op, args) in enumerate(zip(ops, args_list)):
            pre_state = copy.deepcopy(state)
            try:
                if not op.check_precond(state, *args):
                    result.failed_step = i
                    result.error = f'precondition failed at step {i} for {op.name}'
                    break
                output = op.run(state, *args)
                if not op.check_postcond(state, *args):
                    result.failed_step = i
                    result.error = f'postcondition failed at step {i} for {op.name}'
                    break
            except Exception as e:
                result.failed_step = i
                result.error = f'exception at step {i} ({op.name}): {e}'
                result.steps.append(ExecutionStep(op.name, args, pre_state, state, None, result.error))
                break

            result.steps.append(ExecutionStep(op.name, args, pre_state, copy.deepcopy(state), output))

            inv_fails = self._machine.check_invariants(state)
            if inv_fails:
                result.invariant_failures = inv_fails
                result.failed_step = i
                result.error = f'invariant failure at step {i}: {inv_fails}'
                break

        return result

    def execute_sequence(self, sequence: List[Operation], rng: random.Random) -> SequenceResult:
        args_list = [op.generate_args(rng) for op in sequence]
        return self.execute(sequence, args_list)


class SequenceShrinker:
    """Shrinks a failing sequence to the minimal reproduction."""

    def __init__(self, machine: StateMachine) -> None:
        self._executor = SequenceExecutor(machine)

    def shrink(self, ops: List[Operation], args_list: List[tuple], rng: random.Random, max_steps: int = 100) -> Tuple[List[Operation], List[tuple]]:
        best_ops = list(ops)
        best_args = list(args_list)

        for _ in range(max_steps):
            if len(best_ops) <= 1:
                break
            idx = rng.randrange(len(best_ops))
            candidate_ops = best_ops[:idx] + best_ops[idx + 1:]
            candidate_args = best_args[:idx] + best_args[idx + 1:]
            result = self._executor.execute(candidate_ops, candidate_args)
            if not result.passed:
                best_ops = candidate_ops
                best_args = candidate_args
                continue
            if len(best_ops) <= 1:
                break
            idx = rng.randrange(len(best_ops))
            candidate_ops = list(best_ops)
            candidate_args = list(best_args)
            op = candidate_ops[idx]
            orig_args = candidate_args[idx]
            new_args = op.generate_args(rng)
            if new_args != orig_args:
                candidate_args[idx] = new_args
                result = self._executor.execute(candidate_ops, candidate_args)
                if not result.passed:
                    best_args = candidate_args
        return best_ops, best_args


class StateMachineTester:
    """Top-level state machine testing orchestrator."""

    def __init__(self, machine: StateMachine, seed: int = 0) -> None:
        self._machine = machine
        self._rng = random.Random(seed)
        self._generator = OperationSequenceGenerator(machine, self._rng)
        self._executor = SequenceExecutor(machine)
        self._shrinker = SequenceShrinker(machine)
        self._results: List[SequenceResult] = []
        self._best_failure: Optional[SequenceResult] = None

    def run_sequences(self, num_sequences: int = 50, min_len: int = 3, max_len: int = 20) -> List[SequenceResult]:
        self._results.clear()
        for _ in range(num_sequences):
            ops = self._generator.generate(min_len, max_len)
            args_list = [op.generate_args(self._rng) for op in ops]
            result = self._executor.execute(ops, args_list)
            self._results.append(result)

            if not result.passed:
                if self._best_failure is None or len(result.steps) < len(self._best_failure.steps):
                    shrunk_ops, shrunk_args = self._shrinker.shrink(ops, args_list, self._rng)
                    shrunk_result = self._executor.execute(shrunk_ops, shrunk_args)
                    self._best_failure = shrunk_result

        return self._results

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
            'sequences': self.total,
            'passed': self.passed,
            'failed': self.failed,
            'pass_rate': round(self.passed / max(self.total, 1) * 100, 1),
            'has_failure': self._best_failure is not None,
        }

    def failure_report(self) -> Optional[Dict[str, Any]]:
        if self._best_failure is None:
            return None
        return self._best_failure.to_dict()

    def report_text(self) -> str:
        s = self.summary()
        lines = [
            'State Machine Testing Report',
            f'  Sequences: {s["sequences"]}',
            f'  Passed: {s["passed"]}',
            f'  Failed: {s["failed"]}',
            f'  Pass rate: {s["pass_rate"]}%',
        ]
        if self._best_failure:
            lines.append('  Minimal Failure Reproduction:')
            fr = self.failure_report()
            if fr:
                for step in fr.get('steps', []):
                    lines.append(f'    {step["operation"]}({step["args"]}) -> error: {step.get("error", "invariant")}')
        return '\n'.join(lines)

    def export_report(self, path: str) -> None:
        report = {
            'summary': self.summary(),
            'results': [r.to_dict() for r in self._results],
            'minimal_failure': self.failure_report(),
        }
        with open(path, 'w') as f:
            json.dump(report, f, indent=2, default=str)

    def export_artifacts(self, dir: str) -> List[str]:
        os.makedirs(dir, exist_ok=True)
        paths = []
        rp = os.path.join(dir, 'state_machine_report.json')
        self.export_report(rp)
        paths.append(rp)
        return paths
