"""Refinement types and runtime contract enforcement framework."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple, Type
import datetime
import functools
import inspect
import json
import os
import threading
import traceback
import uuid


class ContractViolationError(Exception):
    """Raised when a contract (precondition/postcondition/invariant) is violated."""

    def __init__(self, contract_type: str, name: str, message: str,
                 context: Optional[Dict[str, Any]] = None) -> None:
        self.contract_type = contract_type
        self.contract_name = name
        self.context = context or {}
        full = f'[{contract_type}] {name}: {message}'
        if context:
            full += f' | context: {context}'
        super().__init__(full)
        self.violation_id = uuid.uuid4().hex[:8]
        self.timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()


class RefinedType:
    """A type constrained by a predicate."""

    def __init__(self, base_type: Type, predicate: Callable[[Any], bool],
                 name: str = '') -> None:
        self.base_type = base_type
        self.predicate = predicate
        self.name = name or f'{base_type.__name__}[refined]'

    def check(self, value: Any) -> bool:
        if not isinstance(value, self.base_type):
            return False
        try:
            return bool(self.predicate(value))
        except Exception:
            return False

    def validate(self, value: Any, label: str = 'value') -> Any:
        if not self.check(value):
            raise ContractViolationError(
                'type_refinement', self.name,
                f'{label} failed refinement check: {value!r}',
                {'value': repr(value)[:200], 'expected_type': self.name},
            )
        return value

    def __call__(self, value: Any) -> Any:
        return self.validate(value)


class Precondition:
    """Function precondition - validated before execution."""

    def __init__(self, predicate: Callable[..., bool],
                 description: str = '') -> None:
        self.predicate = predicate
        self.description = description

    def check(self, *args: Any, **kwargs: Any) -> bool:
        try:
            return bool(self.predicate(*args, **kwargs))
        except Exception:
            return False


class Postcondition:
    """Function postcondition - validated after execution."""

    def __init__(self, predicate: Callable[..., bool],
                 description: str = '') -> None:
        self.predicate = predicate
        self.description = description

    def check(self, result: Any, *args: Any, **kwargs: Any) -> bool:
        try:
            return bool(self.predicate(result, *args, **kwargs))
        except Exception:
            return False


class ClassInvariant:
    """Object/state invariant validated before and after public calls."""

    def __init__(self, predicate: Callable[[Any], bool],
                 description: str = '') -> None:
        self.predicate = predicate
        self.description = description

    def check(self, obj: Any) -> bool:
        try:
            return bool(self.predicate(obj))
        except Exception:
            return False


class ContractViolationRecord:
    """Record of a contract violation with execution trace."""

    def __init__(self, contract_type: str, name: str, message: str,
                 fn_name: str = '', args: tuple = (),
                 kwargs: Optional[Dict[str, Any]] = None,
                 trace: str = '') -> None:
        self.id = uuid.uuid4().hex[:12]
        self.contract_type = contract_type
        self.name = name
        self.message = message
        self.fn_name = fn_name
        self.args = [repr(a)[:100] for a in args]
        self.kwargs = {k: repr(v)[:100] for k, v in (kwargs or {}).items()}
        self.trace = trace
        self.timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'contract_type': self.contract_type,
            'name': self.name,
            'message': self.message,
            'function': self.fn_name,
            'args': self.args,
            'kwargs': self.kwargs,
            'timestamp': self.timestamp,
        }


class ContractRegistry:
    """Registry of contracts applied to functions and classes."""

    def __init__(self) -> None:
        self._preconditions: Dict[str, List[Precondition]] = {}
        self._postconditions: Dict[str, List[Postcondition]] = {}
        self._invariants: Dict[str, List[ClassInvariant]] = {}
        self._lock = threading.Lock()

    def add_precondition(self, fn_name: str, precondition: Precondition) -> None:
        with self._lock:
            self._preconditions.setdefault(fn_name, []).append(precondition)

    def add_postcondition(self, fn_name: str, postcondition: Postcondition) -> None:
        with self._lock:
            self._postconditions.setdefault(fn_name, []).append(postcondition)

    def add_invariant(self, class_name: str, invariant: ClassInvariant) -> None:
        with self._lock:
            self._invariants.setdefault(class_name, []).append(invariant)

    def get_preconditions(self, fn_name: str) -> List[Precondition]:
        with self._lock:
            return list(self._preconditions.get(fn_name, []))

    def get_postconditions(self, fn_name: str) -> List[Postcondition]:
        with self._lock:
            return list(self._postconditions.get(fn_name, []))

    def get_invariants(self, class_name: str) -> List[ClassInvariant]:
        with self._lock:
            return list(self._invariants.get(class_name, []))

    def summary(self) -> Dict[str, Any]:
        with self._lock:
            return {
                'preconditions': sum(len(v) for v in self._preconditions.values()),
                'postconditions': sum(len(v) for v in self._postconditions.values()),
                'invariants': sum(len(v) for v in self._invariants.values()),
                'functions_under_contract': len(self._preconditions),
            }


def contract(pre: Optional[Callable[..., bool]] = None,
             post: Optional[Callable[..., bool]] = None,
             pre_desc: str = '', post_desc: str = '') -> Callable[..., Any]:
    """Decorator that applies preconditions and postconditions to a function."""
    pre_cond = Precondition(pre, pre_desc) if pre else None
    post_cond = Postcondition(post, post_desc) if post else None

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        engine_ref = getattr(fn, '_contract_engine', None)

        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            fn_name = fn.__qualname__
            if pre_cond:
                if not pre_cond.check(*args, **kwargs):
                    raise ContractViolationError(
                        'precondition', fn_name, pre_desc or 'precondition failed',
                        {'args': [repr(a)[:100] for a in args], 'kwargs': {k: repr(v)[:100] for k, v in kwargs.items()}},
                    )
                if engine_ref:
                    engine_ref._record_violation('precondition', fn_name, pre_desc or 'failed')
            result = fn(*args, **kwargs)
            if post_cond:
                if not post_cond.check(result, *args, **kwargs):
                    raise ContractViolationError(
                        'postcondition', fn_name, post_desc or 'postcondition failed',
                        {'result': repr(result)[:200]},
                    )
                if engine_ref:
                    engine_ref._record_violation('postcondition', fn_name, post_desc or 'failed')
            return result
        return wrapper

    return decorator


class ContractEngine:
    """Top-level refinement types and runtime contract enforcement framework."""

    def __init__(self) -> None:
        self._registry = ContractRegistry()
        self._violations: List[ContractViolationRecord] = []
        self._lock = threading.Lock()
        self._enabled = True

    @property
    def registry(self) -> ContractRegistry:
        return self._registry

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled

    def refine(self, base_type: Type, predicate: Callable[[Any], bool],
               name: str = '') -> RefinedType:
        return RefinedType(base_type, predicate, name)

    def require(self, fn: Callable[..., Any],
                predicate: Callable[..., bool],
                description: str = '') -> Callable[..., Any]:
        self._registry.add_precondition(fn.__qualname__, Precondition(predicate, description))
        fn._contract_engine = self
        return contract(pre=predicate, pre_desc=description)(fn)

    def ensure(self, fn: Callable[..., Any],
               predicate: Callable[[Any], bool],
               description: str = '') -> Callable[..., Any]:
        self._registry.add_postcondition(fn.__qualname__, Postcondition(predicate, description))
        fn._contract_engine = self
        return contract(post=predicate, post_desc=description)(fn)

    def invariant(self, cls: type,
                  predicate: Callable[[Any], bool],
                  description: str = '') -> type:
        self._registry.add_invariant(cls.__name__, ClassInvariant(predicate, description))
        original_init = cls.__init__ if hasattr(cls, '__init__') else None

        def __init_wrapper(self_obj: Any, *args: Any, **kwargs: Any) -> None:
            if original_init:
                original_init(self_obj, *args, **kwargs)
            for inv in self._registry.get_invariants(type(self_obj).__name__):
                if not inv.check(self_obj):
                    raise ContractViolationError(
                        'invariant', type(self_obj).__name__,
                        inv.description or f'invariant failed after init',
                    )

        cls.__init__ = __init_wrapper
        return cls

    def check_value(self, value: Any, refined_type: RefinedType,
                    label: str = 'value') -> Any:
        return refined_type.validate(value, label)

    def _record_violation(self, ctype: str, name: str, message: str,
                          fn_name: str = '', args: tuple = (),
                          kwargs: Optional[Dict[str, Any]] = None) -> None:
        record = ContractViolationRecord(
            ctype, name, message, fn_name, args, kwargs,
            traceback.format_stack(limit=5),
        )
        with self._lock:
            self._violations.append(record)

    def violation_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self._lock:
            return [v.to_dict() for v in self._violations[-limit:]]

    def clear_violations(self) -> None:
        with self._lock:
            self._violations.clear()

    def summary(self) -> Dict[str, Any]:
        reg = self._registry.summary()
        with self._lock:
            return {
                'enabled': self._enabled,
                'contracts': reg,
                'violations': len(self._violations),
            }

    def report_text(self) -> str:
        s = self.summary()
        c = s['contracts']
        return (
            f'Contract Engine\n'
            f'  Enabled: {s["enabled"]}\n'
            f'  Pre/Post/Invariants: {c["preconditions"]}/{c["postconditions"]}/{c["invariants"]}\n'
            f'  Violations recorded: {s["violations"]}'
        )

    def export_artifacts(self, dir: str) -> List[str]:
        os.makedirs(dir, exist_ok=True)
        paths = []
        sp = os.path.join(dir, 'refinement_types.json')
        with open(sp, 'w') as f:
            json.dump(self.summary(), f, indent=2)
        paths.append(sp)
        vp = os.path.join(dir, 'contract_violations.json')
        with open(vp, 'w') as f:
            json.dump(self.violation_history(500), f, indent=2)
        paths.append(vp)
        return paths
