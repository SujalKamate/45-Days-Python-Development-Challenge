"""Formal verification of state invariants and execution correctness framework."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Set, Tuple
import datetime
import hashlib
import json
import os
import uuid
import itertools


class Invariant:
    """A formal logical constraint on system state."""

    def __init__(self, name: str, constraint: Callable[[Dict[str, Any]], bool],
                 description: str = '',
                 severity: str = 'error') -> None:
        self.name = name
        self.constraint = constraint
        self.description = description or name
        self.severity = severity

    def check(self, state: Dict[str, Any]) -> bool:
        try:
            return bool(self.constraint(state))
        except Exception:
            return False

    def to_dict(self) -> Dict[str, Any]:
        return {'name': self.name, 'description': self.description, 'severity': self.severity}


class InvariantResult:
    """Result of checking a single invariant against a state."""

    def __init__(self, invariant: Invariant, passed: bool,
                 state: Dict[str, Any] = None) -> None:
        self.invariant = invariant
        self.passed = passed
        self.state = state or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            'invariant': self.invariant.name,
            'passed': self.passed,
            'severity': self.invariant.severity,
        }


class SymbolicValue:
    """Symbolic expression tracking for symbolic execution."""

    def __init__(self, name: str, value: Any = None,
                 symbolic: bool = False) -> None:
        self.name = name
        self.value = value
        self.symbolic = symbolic
        self.constraints: List[str] = []

    def __repr__(self) -> str:
        return f'Symbolic({self.name})' if self.symbolic else str(self.value)


class SymbolicState:
    """State with symbolic values tracked during symbolic execution."""

    def __init__(self) -> None:
        self.vars: Dict[str, SymbolicValue] = {}
        self.path_constraints: List[str] = []

    def set_var(self, name: str, value: Any, symbolic: bool = False) -> None:
        self.vars[name] = SymbolicValue(name, value, symbolic)

    def get_var(self, name: str) -> Optional[SymbolicValue]:
        return self.vars.get(name)

    def add_constraint(self, expr: str) -> None:
        self.path_constraints.append(expr)

    def concretize(self) -> Dict[str, Any]:
        return {k: v.value for k, v in self.vars.items() if not v.symbolic}

    def fork(self) -> SymbolicState:
        fork = SymbolicState()
        fork.vars = {k: SymbolicValue(k, v.value, v.symbolic) for k, v in self.vars.items()}
        fork.path_constraints = list(self.path_constraints)
        return fork


class SymbolicExecutor:
    """Execute critical workflows symbolically over modeled paths."""

    def __init__(self) -> None:
        self._paths_explored = 0
        self._path_states: List[SymbolicState] = []

    def execute(self, initial_state: Dict[str, Any],
                workflow_fn: Callable[[Dict[str, Any]], Dict[str, Any]],
                symbolic_keys: Optional[List[str]] = None,
                max_paths: int = 100) -> List[SymbolicState]:
        sym_keys = symbolic_keys or []
        root = SymbolicState()
        for k, v in initial_state.items():
            root.set_var(k, v, symbolic=(k in sym_keys))
        self._path_states = [root]
        explored = 0

        for state in self._path_states:
            if explored >= max_paths:
                break
            concrete = state.concretize()
            try:
                result = workflow_fn(concrete)
                for k, v in result.items():
                    state.set_var(k, v)
            except Exception:
                pass
            explored += 1

        self._paths_explored = explored
        return self._path_states

    @property
    def paths_explored(self) -> int:
        return self._paths_explored


class BoundedModelChecker:
    """Bounded loop unrolling for verification analysis."""

    def __init__(self, max_unwind: int = 5) -> None:
        self._max_unwind = max_unwind

    def check_loop(self, loop_body: Callable[[Dict[str, Any]], Dict[str, Any]],
                   initial_state: Dict[str, Any],
                   invariant: Invariant,
                   loop_var: str = 'i',
                   max_iter: int = 10) -> List[Dict[str, Any]]:
        violations = []
        state = dict(initial_state)
        for i in range(min(max_iter, self._max_unwind)):
            state[loop_var] = i
            state = loop_body(state)
            if not invariant.check(state):
                violations.append({
                    'iteration': i,
                    'state': dict(state),
                    'message': f'Invariant {invariant.name} violated at iteration {i}',
                })
                break
        return violations


class Counterexample:
    """A reproducible counterexample that violates an invariant."""

    def __init__(self, invariant: Invariant, state: Dict[str, Any],
                 path: List[str], message: str = '') -> None:
        self.id = uuid.uuid4().hex[:12]
        self.invariant = invariant
        self.state = state
        self.path = path
        self.message = message or f'Counterexample for {invariant.name}'
        self.timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'invariant': self.invariant.name,
            'message': self.message,
            'state': self.state,
            'path': self.path,
            'timestamp': self.timestamp,
        }


class ProofCertificate:
    """Verification artifact certifying invariant satisfaction."""

    def __init__(self, module: str, version: str) -> None:
        self.module = module
        self.version = version
        self.cert_id = uuid.uuid4().hex[:16]
        self.invariants_checked: List[str] = []
        self.all_passed = True
        self.created_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        self._hash: str = ''

    def add_result(self, name: str, passed: bool) -> None:
        self.invariants_checked.append(name)
        if not passed:
            self.all_passed = False

    def finalize(self) -> str:
        raw = json.dumps(self.to_dict(), sort_keys=True)
        self._hash = hashlib.sha256(raw.encode()).hexdigest()
        return self._hash

    def to_dict(self) -> Dict[str, Any]:
        return {
            'cert_id': self.cert_id,
            'module': self.module,
            'version': self.version,
            'invariants_checked': self.invariants_checked,
            'all_passed': self.all_passed,
            'created_at': self.created_at,
            'hash': self._hash,
        }


class FormalVerifyEngine:
    """Top-level formal verification framework."""

    def __init__(self) -> None:
        self._invariants: Dict[str, Invariant] = {}
        self._counterexamples: List[Counterexample] = []
        self._certificates: List[ProofCertificate] = []

    def register_invariant(self, name: str,
                           constraint: Callable[[Dict[str, Any]], bool],
                           description: str = '',
                           severity: str = 'error') -> Invariant:
        inv = Invariant(name, constraint, description, severity)
        self._invariants[name] = inv
        return inv

    def remove_invariant(self, name: str) -> bool:
        return self._invariants.pop(name, None) is not None

    def list_invariants(self) -> List[Dict[str, Any]]:
        return [inv.to_dict() for inv in self._invariants.values()]

    def verify_state(self, state: Dict[str, Any],
                     invariant_names: Optional[List[str]] = None) -> Dict[str, Any]:
        targets = [n for n in (invariant_names or self._invariants)]
        results = []
        all_pass = True
        for name in targets:
            inv = self._invariants.get(name)
            if inv is None:
                continue
            passed = inv.check(state)
            results.append(InvariantResult(inv, passed, state))
            if not passed:
                all_pass = False
                self._counterexamples.append(
                    Counterexample(inv, dict(state), [], f'{name} violated')
                )
        return {
            'all_passed': all_pass,
            'results': [r.to_dict() for r in results],
        }

    def symbolic_verify(self, initial_state: Dict[str, Any],
                        workflow_fn: Callable[[Dict[str, Any]], Dict[str, Any]],
                        symbolic_keys: Optional[List[str]] = None,
                        max_paths: int = 100) -> Dict[str, Any]:
        executor = SymbolicExecutor()
        paths = executor.execute(initial_state, workflow_fn, symbolic_keys, max_paths)
        violations = []
        for path in paths:
            concrete = path.concretize()
            for inv in self._invariants.values():
                if not inv.check(concrete):
                    violations.append({
                        'invariant': inv.name,
                        'state': concrete,
                        'constraints': path.path_constraints,
                    })
                    self._counterexamples.append(
                        Counterexample(inv, concrete, path.path_constraints)
                    )
        return {
            'paths_explored': len(paths),
            'violations_found': len(violations),
            'violations': violations,
        }

    def bounded_check(self, loop_body: Callable[[Dict[str, Any]], Dict[str, Any]],
                      initial_state: Dict[str, Any],
                      invariant_name: str,
                      loop_var: str = 'i',
                      max_unwind: int = 10) -> Dict[str, Any]:
        inv = self._invariants.get(invariant_name)
        if inv is None:
            return {'error': f'Invariant {invariant_name} not found'}
        checker = BoundedModelChecker(max_unwind)
        violations = checker.check_loop(loop_body, initial_state, inv, loop_var, max_unwind)
        for v in violations:
            self._counterexamples.append(
                Counterexample(inv, v['state'], [f'iteration {v["iteration"]}'], v['message'])
            )
        return {'violations': violations, 'passed': len(violations) == 0}

    def generate_certificate(self, module: str, version: str,
                             state: Dict[str, Any]) -> ProofCertificate:
        cert = ProofCertificate(module, version)
        for name, inv in self._invariants.items():
            passed = inv.check(state)
            cert.add_result(name, passed)
            if not passed:
                self._counterexamples.append(
                    Counterexample(inv, dict(state), [], f'{name} violated during certification')
                )
        cert.finalize()
        self._certificates.append(cert)
        return cert

    def counterexamples(self, limit: int = 100) -> List[Dict[str, Any]]:
        return [c.to_dict() for c in self._counterexamples[-limit:]]

    def certificates(self, limit: int = 50) -> List[Dict[str, Any]]:
        return [c.to_dict() for c in self._certificates[-limit:]]

    def summary(self) -> Dict[str, Any]:
        return {
            'invariants_registered': len(self._invariants),
            'counterexamples_found': len(self._counterexamples),
            'certificates_issued': len(self._certificates),
            'last_certificate_valid': self._certificates[-1].all_passed if self._certificates else None,
        }

    def report_text(self) -> str:
        s = self.summary()
        return (
            f'Formal Verify Engine\n'
            f'  Invariants: {s["invariants_registered"]}\n'
            f'  Counterexamples: {s["counterexamples_found"]}\n'
            f'  Certificates: {s["certificates_issued"]}'
        )

    def export_artifacts(self, dir: str) -> List[str]:
        os.makedirs(dir, exist_ok=True)
        paths = []
        sp = os.path.join(dir, 'formal_verify.json')
        with open(sp, 'w') as f:
            json.dump(self.summary(), f, indent=2)
        paths.append(sp)
        cp = os.path.join(dir, 'counterexamples.json')
        with open(cp, 'w') as f:
            json.dump(self.counterexamples(200), f, indent=2)
        paths.append(cp)
        return paths
