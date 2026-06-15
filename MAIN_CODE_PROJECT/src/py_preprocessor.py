"""Custom Python preprocessor directive framework for conditional and controlled module execution."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple
import datetime
import json
import os
import re
import threading
import time
import uuid


_DIRECTIVE_RE = re.compile(
    r'^\s*#\s*(?P<name>[a-zA-Z_][a-zA-Z0-9_]*)'
    r'(?:\((?P<args>[^)]*)\))?\s*(?:#.*)?$'
)


class Directive:
    """A single preprocessor directive with parsed name and arguments."""

    def __init__(self, name: str, raw_args: str = '',
                 args: Optional[List[str]] = None,
                 kwargs: Optional[Dict[str, str]] = None,
                 lineno: int = 0) -> None:
        self.name = name.lower()
        self.raw_args = raw_args
        self.args = args or []
        self.kwargs = kwargs or {}
        self.lineno = lineno

    def __repr__(self) -> str:
        return f'Directive({self.name}, args={self.args}, kwargs={self.kwargs})'


class DirectiveParseError(Exception):
    pass


class DirectiveParser:
    """Parses #directive lines from source text."""

    def parse(self, source: str) -> List[Directive]:
        directives: List[Directive] = []
        for lineno, line in enumerate(source.splitlines(), start=1):
            stripped = line.strip()
            if not stripped.startswith('#'):
                continue
            m = _DIRECTIVE_RE.match(stripped)
            if not m:
                continue
            name = m.group('name').lower()
            raw_args = m.group('args') or ''
            if raw_args.strip():
                parsed = self._parse_args(raw_args)
            else:
                parsed = {}, []
            kwargs, args = parsed
            directives.append(Directive(name, raw_args, args, kwargs, lineno))
        return directives

    def _parse_args(self, raw: str) -> Tuple[Dict[str, str], List[str]]:
        kwargs: Dict[str, str] = {}
        args: List[str] = []
        parts = [p.strip() for p in raw.split(',') if p.strip()]
        for part in parts:
            if '=' in part:
                k, v = part.split('=', 1)
                kwargs[k.strip()] = v.strip().strip('"\'')
            else:
                args.append(part.strip().strip('"\''))
        return kwargs, args


class DirectiveContext:
    """Context passed to directive handlers during execution."""

    def __init__(self, directive: Directive, module_name: str = '',
                 globals_dict: Optional[Dict[str, Any]] = None) -> None:
        self.directive = directive
        self.module_name = module_name
        self.globals = globals_dict or {}
        self.start_time = time.time()
        self.result: Any = None


DirectiveHandler = Callable[[DirectiveContext], Any]


class DirectiveRegistry:
    """Registry of built-in and custom directive handlers."""

    def __init__(self) -> None:
        self._handlers: Dict[str, DirectiveHandler] = {}
        self._register_builtins()

    def _register_builtins(self) -> None:
        self.register('skip', self._handle_skip)
        self.register('repeat', self._handle_repeat)
        self.register('timeout', self._handle_timeout)
        self.register('retry', self._handle_retry)
        self.register('depends_on', self._handle_depends_on)
        self.register('log', self._handle_log)

    def register(self, name: str, handler: DirectiveHandler) -> None:
        self._handlers[name.lower()] = handler

    def unregister(self, name: str) -> bool:
        return self._handlers.pop(name.lower(), None) is not None

    def get(self, name: str) -> Optional[DirectiveHandler]:
        return self._handlers.get(name.lower())

    def list(self) -> List[str]:
        return list(self._handlers.keys())

    @staticmethod
    def _handle_skip(ctx: DirectiveContext) -> str:
        return 'skip'

    @staticmethod
    def _handle_repeat(ctx: DirectiveContext) -> int:
        n = int(ctx.directive.args[0]) if ctx.directive.args else 1
        return max(1, n)

    @staticmethod
    def _handle_timeout(ctx: DirectiveContext) -> float:
        sec = float(ctx.directive.args[0]) if ctx.directive.args else 30.0
        return max(0.1, sec)

    @staticmethod
    def _handle_retry(ctx: DirectiveContext) -> int:
        n = int(ctx.directive.args[0]) if ctx.directive.args else 3
        return max(1, n)

    @staticmethod
    def _handle_depends_on(ctx: DirectiveContext) -> str:
        return ctx.directive.args[0] if ctx.directive.args else ''

    @staticmethod
    def _handle_log(ctx: DirectiveContext) -> str:
        return ctx.directive.args[0] if ctx.directive.args else 'info'


class ExecutionPlan:
    """Resolved execution plan for a module with directives applied."""

    def __init__(self, module_name: str, source: str = '') -> None:
        self.module_name = module_name
        self.source = source
        self.directives: List[Directive] = []
        self.skip = False
        self.repeat = 1
        self.timeout_s: Optional[float] = None
        self.retry = 1
        self.depends_on: List[str] = []
        self.log_level = 'info'
        self.custom: Dict[str, Any] = {}

    def apply(self, directive: Directive, value: Any) -> None:
        name = directive.name
        if name == 'skip':
            self.skip = True
        elif name == 'repeat':
            self.repeat = int(value) if isinstance(value, (int, float)) else 1
        elif name == 'timeout':
            self.timeout_s = float(value) if value else None
        elif name == 'retry':
            self.retry = int(value) if isinstance(value, (int, float)) else 1
        elif name == 'depends_on':
            self.depends_on.append(str(value) if value else '')
        elif name == 'log':
            self.log_level = str(value) if value else 'info'
        else:
            self.custom[name] = value

    def to_dict(self) -> Dict[str, Any]:
        return {
            'module': self.module_name,
            'skip': self.skip,
            'repeat': self.repeat,
            'timeout_s': self.timeout_s,
            'retry': self.retry,
            'depends_on': self.depends_on,
            'log_level': self.log_level,
            'custom': self.custom,
            'directive_count': len(self.directives),
        }


class DirectiveExecutor:
    """Executes a module function subject to parsed directives."""

    def __init__(self, registry: DirectiveRegistry) -> None:
        self._registry = registry

    def execute(self, fn: Callable[..., Any], plan: ExecutionPlan,
                *args: Any, **kwargs: Any) -> Any:
        if plan.skip:
            return None

        last_exc: Optional[Exception] = None
        for attempt in range(plan.retry):
            try:
                def _run() -> Any:
                    result = None
                    for _ in range(plan.repeat):
                        result = fn(*args, **kwargs)
                    return result

                if plan.timeout_s is not None:
                    result = self._run_with_timeout(_run, plan.timeout_s)
                else:
                    result = _run()
                return result
            except Exception as e:
                last_exc = e
                if attempt < plan.retry - 1:
                    time.sleep(0.5 * (attempt + 1))
                    continue
                raise

        if last_exc:
            raise last_exc
        return None

    def _run_with_timeout(self, fn: Callable[[], Any], timeout_s: float) -> Any:
        result: List[Any] = [None]
        exc: List[Optional[Exception]] = [None]
        thread = threading.Thread(target=lambda: self._target(fn, result, exc), daemon=True)
        thread.start()
        thread.join(timeout_s)
        if thread.is_alive():
            raise TimeoutError(f'Execution timed out after {timeout_s}s')
        if exc[0]:
            raise exc[0]
        return result[0]

    @staticmethod
    def _target(fn: Callable[[], Any], result: List[Any],
                exc: List[Optional[Exception]]) -> None:
        try:
            result[0] = fn()
        except Exception as e:
            exc[0] = e


class PreprocessorEngine:
    """Top-level preprocessor directive framework."""

    def __init__(self) -> None:
        self._parser = DirectiveParser()
        self._registry = DirectiveRegistry()
        self._executor = DirectiveExecutor(self._registry)
        self._history: List[Dict[str, Any]] = []

    @property
    def registry(self) -> DirectiveRegistry:
        return self._registry

    def parse(self, source: str) -> List[Directive]:
        return self._parser.parse(source)

    def plan_from_source(self, module_name: str, source: str) -> ExecutionPlan:
        plan = ExecutionPlan(module_name, source)
        directives = self._parser.parse(source)
        plan.directives = directives
        for d in directives:
            handler = self._registry.get(d.name)
            if handler:
                ctx = DirectiveContext(d, module_name)
                try:
                    value = handler(ctx)
                    plan.apply(d, value)
                except Exception:
                    pass
        return plan

    def execute(self, fn: Callable[..., Any], plan: ExecutionPlan,
                *args: Any, **kwargs: Any) -> Any:
        start = time.time()
        try:
            result = self._executor.execute(fn, plan, *args, **kwargs)
            status = 'completed'
        except TimeoutError:
            result = None
            status = 'timeout'
        except Exception as e:
            result = None
            status = 'error'
        elapsed = time.time() - start
        record = {
            'module': plan.module_name,
            'status': status,
            'elapsed_s': round(elapsed, 4),
            'skip': plan.skip,
            'repeat': plan.repeat,
            'retry': plan.retry,
            'timeout_s': plan.timeout_s,
            'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        self._history.append(record)
        return result

    def register_directive(self, name: str, handler: DirectiveHandler) -> None:
        self._registry.register(name, handler)

    def unregister_directive(self, name: str) -> bool:
        return self._registry.unregister(name)

    def list_directives(self) -> List[str]:
        return self._registry.list()

    def history(self, limit: int = 100) -> List[Dict[str, Any]]:
        return self._history[-limit:]

    def summary(self) -> Dict[str, Any]:
        return {
            'directives_registered': len(self._registry.list()),
            'executions': len(self._history),
            'last_status': self._history[-1]['status'] if self._history else None,
        }

    def report_text(self) -> str:
        s = self.summary()
        return (
            f'Preprocessor Directive Engine\n'
            f'  Registered directives: {s["directives_registered"]}\n'
            f'  Total executions: {s["executions"]}\n'
            f'  Last status: {s["last_status"]}'
        )

    def export_artifacts(self, dir: str) -> List[str]:
        os.makedirs(dir, exist_ok=True)
        paths = []
        sp = os.path.join(dir, 'preprocessor.json')
        with open(sp, 'w') as f:
            json.dump(self.summary(), f, indent=2)
        paths.append(sp)
        hp = os.path.join(dir, 'preprocessor_history.json')
        with open(hp, 'w') as f:
            json.dump(self.history(limit=500), f, indent=2)
        paths.append(hp)
        return paths
