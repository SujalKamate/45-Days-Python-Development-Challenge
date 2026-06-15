"""Interactive debugging REPL with advanced module introspection and execution analysis."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple
import datetime
import difflib
import json
import os
import readline
import rlcompleter
import sys
import time
import traceback
import uuid


class REPLCommand:
    """Parsed REPL command with name and arguments."""

    def __init__(self, raw: str) -> None:
        self.raw = raw.strip()
        parts = self.raw.split()
        self.name = parts[0].lower() if parts else ''
        self.args = parts[1:] if len(parts) > 1 else []

    @property
    def valid(self) -> bool:
        return bool(self.name)

    def arg(self, index: int, default: str = '') -> str:
        return self.args[index] if index < len(self.args) else default


class ModuleInspector:
    """Introspect modules, objects, and runtime state."""

    def __init__(self, modules: Optional[Dict[str, Any]] = None) -> None:
        self._modules = modules or {}

    def register(self, name: str, module: Any) -> None:
        self._modules[name] = module

    def list_modules(self) -> List[str]:
        return list(self._modules.keys())

    def get_module(self, name: str) -> Optional[Any]:
        return self._modules.get(name)

    def inspect(self, target: Any) -> Dict[str, Any]:
        info: Dict[str, Any] = {}
        info['type'] = type(target).__name__
        info['module'] = getattr(target, '__module__', '')
        info['id'] = id(target)
        if hasattr(target, '__dict__'):
            info['dict_keys'] = list(getattr(target, '__dict__', {}).keys())
        if hasattr(target, '__annotations__'):
            info['annotations'] = getattr(target, '__annotations__', {})
        if callable(target):
            import inspect
            try:
                sig = inspect.signature(target)
                info['signature'] = str(sig)
                info['parameters'] = list(sig.parameters.keys())
            except (ValueError, TypeError):
                pass
        if isinstance(target, (str, int, float, bool)):
            info['value'] = target
        return info

    def module_attrs(self, name: str) -> Dict[str, Any]:
        mod = self._modules.get(name)
        if mod is None:
            return {}
        result: Dict[str, Any] = {}
        for attr in dir(mod):
            if attr.startswith('_'):
                continue
            obj = getattr(mod, attr)
            result[attr] = type(obj).__name__
        return result

    def state_snapshot(self, target: Any) -> Dict[str, Any]:
        snapshot: Dict[str, Any] = {}
        if hasattr(target, '__dict__'):
            for k, v in target.__dict__.items():
                if k.startswith('_'):
                    continue
                snapshot[k] = self._deep_repr(v)
        elif hasattr(target, 'to_dict') and callable(target.to_dict):
            snapshot = target.to_dict()
        return snapshot

    def _deep_repr(self, value: Any, depth: int = 2) -> Any:
        if depth <= 0:
            return type(value).__name__
        if isinstance(value, (str, int, float, bool, type(None))):
            return value
        if isinstance(value, (list, tuple)):
            return [self._deep_repr(v, depth - 1) for v in value[:10]]
        if isinstance(value, dict):
            return {k: self._deep_repr(v, depth - 1) for k, v in list(value.items())[:10]}
        if hasattr(value, '__dict__'):
            return {k: self._deep_repr(v, depth - 1) for k, v in value.__dict__.items() if not k.startswith('_')}
        return str(value)[:100]


class ExecutionTracer:
    """Execute callables with tracing, timing, and result capture."""

    def __init__(self) -> None:
        self._traces: List[Dict[str, Any]] = []

    def trace(self, fn: Callable[..., Any], *args: Any,
              label: str = '', **kwargs: Any) -> Dict[str, Any]:
        trace_id = uuid.uuid4().hex[:12]
        start = time.perf_counter()
        exc: Optional[str] = None
        result: Any = None
        try:
            result = fn(*args, **kwargs)
            status = 'ok'
        except Exception as e:
            exc = traceback.format_exc()
            status = 'error'
        elapsed = time.perf_counter() - start
        record = {
            'trace_id': trace_id,
            'label': label or fn.__name__,
            'fn': fn.__name__,
            'args': repr(args)[:200],
            'kwargs': repr(kwargs)[:200],
            'status': status,
            'elapsed_s': round(elapsed, 6),
            'error': exc,
            'result': repr(result)[:500] if status == 'ok' else None,
            'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        self._traces.append(record)
        return record

    def history(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self._traces[-limit:]

    def clear(self) -> None:
        self._traces.clear()

    def summary(self) -> Dict[str, Any]:
        total = len(self._traces)
        errors = sum(1 for t in self._traces if t['status'] == 'error')
        ok = total - errors
        avg_time = sum(t['elapsed_s'] for t in self._traces) / total if total else 0.0
        return {
            'total': total,
            'ok': ok,
            'errors': errors,
            'avg_elapsed_s': round(avg_time, 6),
        }


class StateComparator:
    """Compare historical execution states and produce diffs."""

    def diff(self, before: Dict[str, Any], after: Dict[str, Any]) -> str:
        before_json = json.dumps(before, indent=2, default=str, sort_keys=True)
        after_json = json.dumps(after, indent=2, default=str, sort_keys=True)
        diff = difflib.unified_diff(
            before_json.splitlines(),
            after_json.splitlines(),
            fromfile='before',
            tofile='after',
            lineterm='',
        )
        return '\n'.join(diff)

    def changed_keys(self, before: Dict[str, Any], after: Dict[str, Any]) -> Dict[str, Tuple[Any, Any]]:
        changes: Dict[str, Tuple[Any, Any]] = {}
        all_keys = set(before.keys()) | set(after.keys())
        for k in all_keys:
            bv = before.get(k)
            av = after.get(k)
            if bv != av:
                changes[k] = (bv, av)
        return changes


class DebugREPL:
    """Interactive debugging REPL with command dispatch."""

    COMMANDS: Dict[str, str] = {
        'help': 'Show this help',
        'modules': 'List registered modules',
        'inspect': 'Inspect a module or object: inspect <name>',
        'attrs': 'List module attributes: attrs <name>',
        'state': 'Show current state snapshot: state [name]',
        'run': 'Execute a callable with tracing: run <name> [args...]',
        'trace': 'Show execution trace history: trace [limit]',
        'diff': 'Compare two state snapshots: diff <key1> <key2>',
        'history': 'Show REPL command history',
        'export': 'Export REPL artifacts: export <dir>',
        'clear': 'Clear trace history',
        'quit': 'Exit the REPL',
    }

    def __init__(self, inspector: ModuleInspector, tracer: ExecutionTracer,
                 state_getter: Optional[Callable[[str], Dict[str, Any]]] = None) -> None:
        self._inspector = inspector
        self._tracer = tracer
        self._state_getter = state_getter
        self._history: List[str] = []
        self._running = True
        self._callables: Dict[str, Callable[..., Any]] = {}

    def register_callable(self, name: str, fn: Callable[..., Any]) -> None:
        self._callables[name] = fn

    def run(self, banner: str = '') -> None:
        if banner:
            print(banner)
        print('Type "help" for commands, "quit" to exit.')
        while self._running:
            try:
                raw = input('debug> ').strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not raw:
                continue
            self._history.append(raw)
            cmd = REPLCommand(raw)
            self._dispatch(cmd)

    def _dispatch(self, cmd: REPLCommand) -> None:
        dispatch = {
            'help': self._cmd_help,
            'modules': self._cmd_modules,
            'inspect': self._cmd_inspect,
            'attrs': self._cmd_attrs,
            'state': self._cmd_state,
            'run': self._cmd_run,
            'trace': self._cmd_trace,
            'diff': self._cmd_diff,
            'history': self._cmd_history,
            'export': self._cmd_export,
            'clear': self._cmd_clear,
            'quit': self._cmd_quit,
            'exit': self._cmd_quit,
        }
        handler = dispatch.get(cmd.name)
        if handler:
            handler(cmd)
        else:
            print(f'Unknown command: {cmd.name}. Type "help" for commands.')

    def _cmd_help(self, cmd: REPLCommand) -> None:
        print(f'{"Command":<20} Description')
        print('-' * 50)
        for name, desc in sorted(self.COMMANDS.items()):
            print(f'{name:<20} {desc}')

    def _cmd_modules(self, cmd: REPLCommand) -> None:
        modules = self._inspector.list_modules()
        if not modules:
            print('No modules registered.')
            return
        print(f'Registered modules ({len(modules)}):')
        for m in sorted(modules):
            print(f'  - {m}')

    def _cmd_inspect(self, cmd: REPLCommand) -> None:
        name = cmd.arg(0)
        if not name:
            print('Usage: inspect <name>')
            return
        obj: Any = self._inspector.get_module(name) or self._callables.get(name)
        if obj is None:
            print(f'Not found: {name}')
            return
        info = self._inspector.inspect(obj)
        print(f'Inspect: {name}')
        for k, v in info.items():
            print(f'  {k}: {v}')

    def _cmd_attrs(self, cmd: REPLCommand) -> None:
        name = cmd.arg(0)
        if not name:
            print('Usage: attrs <name>')
            return
        attrs = self._inspector.module_attrs(name)
        if not attrs:
            print(f'Module not found or no public attrs: {name}')
            return
        print(f'Attributes of {name}:')
        for attr, typ in sorted(attrs.items()):
            print(f'  {attr}: {typ}')

    def _cmd_state(self, cmd: REPLCommand) -> None:
        name = cmd.arg(0)
        if self._state_getter:
            state = self._state_getter(name) if name else self._state_getter('')
        else:
            obj = self._inspector.get_module(name) if name else None
            state = self._inspector.state_snapshot(obj) if obj else {}
        if not state:
            print('No state available.')
            return
        print(json.dumps(state, indent=2, default=str))

    def _cmd_run(self, cmd: REPLCommand) -> None:
        name = cmd.arg(0)
        if not name:
            print('Usage: run <name> [args...]')
            return
        fn = self._callables.get(name)
        if fn is None:
            print(f'No callable registered: {name}')
            return
        args = cmd.args[1:]
        parsed_args = [self._parse_arg(a) for a in args]
        record = self._tracer.trace(fn, *parsed_args, label=name)
        status = record['status']
        elapsed = record['elapsed_s']
        print(f'[{status}] {name} completed in {elapsed*1000:.2f}ms')
        if record['result']:
            print(f'Result: {record["result"][:200]}')
        if record['error']:
            print(f'Error:\n{record["error"]}')

    def _cmd_trace(self, cmd: REPLCommand) -> None:
        limit = int(cmd.arg(0, '10'))
        traces = self._tracer.history(limit)
        if not traces:
            print('No traces available.')
            return
        print(f'Last {len(traces)} traces:')
        print(f'{"ID":<14} {"Label":<20} {"Status":<8} {"Time(ms)":<10} {"Timestamp"}')
        print('-' * 80)
        for t in reversed(traces):
            ms = t['elapsed_s'] * 1000
            print(f'{t["trace_id"]:<14} {t["label"]:<20} {t["status"]:<8} {ms:<10.2f} {t["timestamp"]}')

    def _cmd_diff(self, cmd: REPLCommand) -> None:
        k1 = cmd.arg(0)
        k2 = cmd.arg(1)
        if not k1 or not k2:
            print('Usage: diff <key1> <key2>')
            return
        if not self._state_getter:
            print('No state getter configured.')
            return
        s1 = self._state_getter(k1)
        s2 = self._state_getter(k2)
        if not s1 or not s2:
            print('One or both states not found.')
            return
        diff = StateComparator().diff(s1, s2)
        print(diff if diff else '(identical)')

    def _cmd_history(self, cmd: REPLCommand) -> None:
        if not self._history:
            print('No command history.')
            return
        for i, h in enumerate(self._history, 1):
            print(f'{i:4}: {h}')

    def _cmd_export(self, cmd: REPLCommand) -> None:
        dir = cmd.arg(0, 'debug_output')
        os.makedirs(dir, exist_ok=True)
        traces = self._tracer.history(9999)
        tp = os.path.join(dir, 'traces.json')
        with open(tp, 'w') as f:
            json.dump(traces, f, indent=2)
        hp = os.path.join(dir, 'repl_history.json')
        with open(hp, 'w') as f:
            json.dump(self._history, f, indent=2)
        print(f'Exported to {dir}/')

    def _cmd_clear(self, cmd: REPLCommand) -> None:
        self._tracer.clear()
        print('Trace history cleared.')

    def _cmd_quit(self, cmd: REPLCommand) -> None:
        self._running = False
        print('Exiting debug REPL.')

    @staticmethod
    def _parse_arg(arg: str) -> Any:
        if arg.lower() == 'true':
            return True
        if arg.lower() == 'false':
            return False
        if arg.lower() == 'none':
            return None
        try:
            return int(arg)
        except ValueError:
            pass
        try:
            return float(arg)
        except ValueError:
            pass
        return arg


class DebugREPLEngine:
    """Top-level interactive debugging REPL engine."""

    def __init__(self) -> None:
        self._inspector = ModuleInspector()
        self._tracer = ExecutionTracer()
        self._state_snapshots: Dict[str, Dict[str, Any]] = {}
        self._repl = DebugREPL(
            inspector=self._inspector,
            tracer=self._tracer,
            state_getter=self._get_state,
        )

    @property
    def inspector(self) -> ModuleInspector:
        return self._inspector

    @property
    def tracer(self) -> ExecutionTracer:
        return self._tracer

    @property
    def repl(self) -> DebugREPL:
        return self._repl

    def register_module(self, name: str, module: Any) -> None:
        self._inspector.register(name, module)

    def register_callable(self, name: str, fn: Callable[..., Any]) -> None:
        self._repl.register_callable(name, fn)

    def snapshot_state(self, key: str, state: Dict[str, Any]) -> None:
        self._state_snapshots[key] = state

    def _get_state(self, key: str) -> Dict[str, Any]:
        if not key:
            return {}
        return self._state_snapshots.get(key, {})

    def start_repl(self, banner: str = '=== Debug REPL ===') -> None:
        self._repl.run(banner)

    def trace_execution(self, fn: Callable[..., Any], *args: Any,
                        label: str = '', **kwargs: Any) -> Dict[str, Any]:
        return self._tracer.trace(fn, *args, label=label, **kwargs)

    def trace_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self._tracer.history(limit)

    def summary(self) -> Dict[str, Any]:
        return {
            'modules_registered': len(self._inspector.list_modules()),
            'callables_registered': len(self._repl._callables),
            'state_snapshots': len(self._state_snapshots),
            'traces': self._tracer.summary(),
        }

    def report_text(self) -> str:
        s = self.summary()
        ts = s['traces']
        return (
            f'Debug REPL Engine\n'
            f'  Modules: {s["modules_registered"]}\n'
            f'  Callables: {s["callables_registered"]}\n'
            f'  Snapshots: {s["state_snapshots"]}\n'
            f'  Traces: {ts["total"]} ({ts["ok"]} ok, {ts["errors"]} errors)'
        )

    def export_artifacts(self, dir: str) -> List[str]:
        os.makedirs(dir, exist_ok=True)
        paths = []
        sp = os.path.join(dir, 'debug_repl.json')
        with open(sp, 'w') as f:
            json.dump(self.summary(), f, indent=2)
        paths.append(sp)
        tp = os.path.join(dir, 'debug_traces.json')
        with open(tp, 'w') as f:
            json.dump(self._tracer.history(9999), f, indent=2)
        paths.append(tp)
        return paths
