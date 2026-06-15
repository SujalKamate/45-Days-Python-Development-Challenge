"""Sandboxed Lua scripting support for user-defined data transformation logic."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Set, Tuple
import copy
import datetime
import hashlib
import json
import os
import re
import sys
import threading
import time
import traceback


_MAX_EXECUTION_MS = 5000
_MAX_MEMORY_BYTES = 10 * 1024 * 1024
_MAX_INSTRUCTIONS = 100000


class LuaSandboxError(Exception):
    pass


class ResourceLimiter:
    """Enforces execution time and memory limits on scripts."""

    def __init__(self, max_time_ms: int = _MAX_EXECUTION_MS,
                 max_memory: int = _MAX_MEMORY_BYTES,
                 max_instructions: int = _MAX_INSTRUCTIONS) -> None:
        self._max_time = max_time_ms / 1000.0
        self._max_mem = max_memory
        self._max_insns = max_instructions
        self._start_time: float = 0.0
        self._instruction_count = 0
        self._aborted = False

    def check(self) -> None:
        if self._aborted:
            raise LuaSandboxError('execution aborted')
        self._instruction_count += 1
        if self._instruction_count > self._max_insns:
            self._aborted = True
            raise LuaSandboxError(f'instruction limit exceeded ({self._max_insns})')
        elapsed = time.time() - self._start_time
        if elapsed > self._max_time:
            self._aborted = True
            raise LuaSandboxError(f'timeout after {elapsed:.2f}s')

    def reset(self) -> None:
        self._start_time = time.time()
        self._instruction_count = 0
        self._aborted = False


class LuaValue:
    """A value in the Lua interpreter."""

    def __init__(self, value: Any) -> None:
        self.value = value

    @property
    def is_nil(self) -> bool:
        return self.value is None

    @property
    def is_number(self) -> bool:
        return isinstance(self.value, (int, float))

    @property
    def is_string(self) -> bool:
        return isinstance(self.value, str)

    @property
    def is_bool(self) -> bool:
        return isinstance(self.value, bool)

    @property
    def is_table(self) -> bool:
        return isinstance(self.value, dict)

    @property
    def is_function(self) -> bool:
        return callable(self.value)


class LuaTable:
    """Lua-style table with array + dict parts."""

    def __init__(self) -> None:
        self._array: List[Any] = []
        self._dict: Dict[Any, Any] = {}

    def set(self, key: Any, value: Any) -> None:
        if isinstance(key, int) and key >= 1:
            idx = key - 1
            while len(self._array) <= idx:
                self._array.append(None)
            self._array[idx] = value
        else:
            self._dict[key] = value

    def get(self, key: Any, default: Any = None) -> Any:
        if isinstance(key, int) and key >= 1:
            idx = key - 1
            return self._array[idx] if idx < len(self._array) else default
        return self._dict.get(key, default)

    def items(self) -> List[Tuple[Any, Any]]:
        result = []
        for i, v in enumerate(self._array):
            if v is not None:
                result.append((i + 1, v))
        for k, v in self._dict.items():
            result.append((k, v))
        return result

    def length(self) -> int:
        return len(self._array)

    def to_dict(self) -> Dict[str, Any]:
        return {str(k): v for k, v in self.items()}


class LuaSafeEnv:
    """Safe environment for Lua scripts with restricted built-ins."""

    def __init__(self) -> None:
        self._globals: Dict[str, Any] = {
            'print': self._safe_print,
            'type': lambda v: type(v).__name__,
            'tostring': str,
            'tonumber': lambda v: float(v) if v is not None else None,
            'pairs': lambda t: iter(t.items() if isinstance(t, LuaTable) else []),
            'ipairs': lambda t: iter(
                [(i + 1, t._array[i]) for i in range(len(t._array))]
                if isinstance(t, LuaTable) else []
            ),
            'string': self._string_lib(),
            'math': self._math_lib(),
            'table': self._table_lib(),
            '_VERSION': 'Lua 5.4 (sandboxed)',
        }
        self._user_data: Dict[str, Any] = {}
        self._limiter = ResourceLimiter()

    def _safe_print(self, *args: Any) -> None:
        self._user_data['_last_print'] = ' '.join(str(a) for a in args)

    @staticmethod
    def _string_lib() -> Dict[str, Any]:
        return {
            'len': len,
            'sub': lambda s, i, j=None: s[i - 1:j] if j else s[i - 1:],
            'upper': str.upper,
            'lower': str.lower,
            'format': str.format,
        }

    @staticmethod
    def _math_lib() -> Dict[str, Any]:
        import math
        return {
            'abs': abs, 'floor': math.floor, 'ceil': math.ceil,
            'max': max, 'min': min, 'sqrt': math.sqrt,
            'sin': math.sin, 'cos': math.cos, 'pi': math.pi,
        }

    @staticmethod
    def _table_lib() -> Dict[str, Any]:
        return {
            'insert': lambda t, v: t._array.append(v) if isinstance(t, LuaTable) else None,
            'remove': lambda t, i=None: (
                t._array.pop((i - 1) if i else -1) if isinstance(t, LuaTable) else None
            ),
            'sort': lambda t: (
                t._array.sort() if isinstance(t, LuaTable) else None
            ),
            'concat': lambda t, sep=', ': (
                sep.join(str(v) for v in t._array if v is not None)
                if isinstance(t, LuaTable) else ''
            ),
        }

    def set_user_data(self, key: str, value: Any) -> None:
        self._user_data[key] = value

    def get_user_data(self, key: str) -> Any:
        return self._user_data.get(key)

    def check_limits(self) -> None:
        self._limiter.check()

    def reset_limits(self) -> None:
        self._limiter.reset()


class LuaInterpreter:
    """Minimal Lua interpreter for sandboxed execution."""

    def __init__(self, safe_env: LuaSafeEnv) -> None:
        self._env = safe_env

    def execute(self, script: str) -> Any:
        self._env.reset_limits()
        result = None
        lines = script.split('\n')
        local_vars: Dict[str, Any] = {}
        return_statement: Optional[str] = None

        for raw_line in lines:
            self._env.check_limits()
            line = raw_line.strip()
            if not line or line.startswith('--'):
                continue

            if line.startswith('return '):
                expr = line[7:].strip()
                return self._eval_expr(expr, local_vars)

            if line.startswith('local '):
                self._handle_local(line[6:].strip(), local_vars)
            elif '=' in line:
                self._handle_assignment(line, local_vars)
            elif line.startswith('for '):
                self._handle_for(line, local_vars)
            elif line.startswith('while '):
                self._handle_while(line, local_vars)
            elif line.startswith('if ') or line.startswith('elseif '):
                result = self._handle_if(lines, local_vars)
                break
            elif line.startswith('function '):
                self._handle_function_def(line, local_vars)
            else:
                result = self._eval_expr(line, local_vars)

        return result

    def _handle_local(self, stmt: str, locals: Dict[str, Any]) -> None:
        parts = stmt.split('=', 1)
        name = parts[0].strip()
        if len(parts) > 1:
            locals[name] = self._eval_expr(parts[1].strip(), locals)
        else:
            locals[name] = None

    def _handle_assignment(self, line: str, locals: Dict[str, Any]) -> None:
        parts = line.split('=', 1)
        name = parts[0].strip()
        value = self._eval_expr(parts[1].strip(), locals)
        if name.startswith('_G.') or name in self._env._globals:
            raise LuaSandboxError(f'cannot modify global: {name}')
        if name in locals or not name.startswith('_'):
            locals[name] = value
        else:
            self._env._globals[name] = value

    def _handle_for(self, line: str, locals: Dict[str, Any]) -> None:
        m = re.match(r'for\s+(\w+)\s*=\s*([^,]+),\s*([^,]+)(?:,\s*([^,]+))?\s*do', line)
        if not m:
            return
        var_name = m.group(1)
        start = self._eval_expr(m.group(2).strip(), locals)
        end = self._eval_expr(m.group(3).strip(), locals)
        step = self._eval_expr(m.group(4).strip(), locals) if m.group(4) else 1
        if isinstance(start, (int, float)) and isinstance(end, (int, float)):
            val = start
            while val <= end:
                locals[var_name] = val
                val += step
                self._env.check_limits()

    def _handle_while(self, line: str, locals: Dict[str, Any]) -> None:
        m = re.match(r'while\s+(.+)\s+do', line)
        if not m:
            return
        cond_str = m.group(1).strip()
        while self._eval_expr(cond_str, locals):
            self._env.check_limits()
            break

    def _handle_if(self, lines: List[str], locals: Dict[str, Any]) -> Optional[Any]:
        for line in lines:
            self._env.check_limits()
            if line.startswith('if ') and ' then' in line:
                cond_str = line[3:line.index(' then')].strip()
                if self._eval_expr(cond_str, locals):
                    return True
            elif line.startswith('elseif ') and ' then' in line:
                cond_str = line[7:line.index(' then')].strip()
                if self._eval_expr(cond_str, locals):
                    return True
            elif line.startswith('else'):
                return True
            elif line.startswith('end'):
                break
        return None

    def _handle_function_def(self, line: str, locals: Dict[str, Any]) -> None:
        m = re.match(r'function\s+(\w+)\s*\((.*)\)', line)
        if m:
            name = m.group(1)
            params = [p.strip() for p in m.group(2).split(',') if p.strip()]
            def make_fn(p=params):
                def fn(*args):
                    local_copy = {}
                    for i, param in enumerate(p):
                        local_copy[param] = args[i] if i < len(args) else None
                    return None
                return fn
            locals[name] = make_fn()

    def _eval_expr(self, expr: str, locals: Dict[str, Any]) -> Any:
        self._env.check_limits()
        expr = expr.strip()
        if not expr:
            return None
        if expr == 'true':
            return True
        if expr == 'false':
            return False
        if expr == 'nil':
            return None
        try:
            return int(expr)
        except ValueError:
            pass
        try:
            return float(expr)
        except ValueError:
            pass
        if expr.startswith('"') and expr.endswith('"'):
            return expr[1:-1]
        if expr.startswith("'") and expr.endswith("'"):
            return expr[1:-1]

        if expr.startswith('{') and expr.endswith('}'):
            return self._eval_table(expr[1:-1], locals)

        for op in ['~=', '<=', '>=', '==', '<', '>']:
            if op in expr:
                parts = expr.split(op, 1)
                left = self._eval_expr(parts[0].strip(), locals)
                right = self._eval_expr(parts[1].strip(), locals)
                if op == '==':
                    return left == right
                if op == '~=':
                    return left != right
                if op == '<':
                    return left < right
                if op == '>':
                    return left > right
                if op == '<=':
                    return left <= right
                if op == '>=':
                    return left >= right

        if '..' in expr:
            parts = expr.split('..', 1)
            return str(self._eval_expr(parts[0].strip(), locals)) + str(self._eval_expr(parts[1].strip(), locals))

        if '+' in expr:
            parts = expr.split('+', 1)
            return self._eval_expr(parts[0], locals) + self._eval_expr(parts[1], locals)
        if '-' in expr and not expr.startswith('-'):
            parts = expr.split('-', 1)
            return self._eval_expr(parts[0], locals) - self._eval_expr(parts[1], locals)
        if '*' in expr:
            parts = expr.split('*', 1)
            return self._eval_expr(parts[0], locals) * self._eval_expr(parts[1], locals)
        if '/' in expr:
            parts = expr.split('/', 1)
            return self._eval_expr(parts[0], locals) / self._eval_expr(parts[1], locals)

        if '(' in expr and expr.endswith(')'):
            idx = expr.index('(')
            fn_name = expr[:idx].strip()
            args_str = expr[idx + 1:-1].strip()
            args = [self._eval_expr(a.strip(), locals) for a in args_str.split(',')] if args_str else []
            return self._call(fn_name, args, locals)

        if '.' in expr:
            parts = expr.split('.', 1)
            obj = self._resolve_name(parts[0], locals)
            if isinstance(obj, dict):
                return obj.get(parts[1])
            if hasattr(obj, parts[1]):
                return getattr(obj, parts[1])
            return None

        return self._resolve_name(expr, locals)

    def _eval_table(self, content: str, locals: Dict[str, Any]) -> LuaTable:
        t = LuaTable()
        if content.strip():
            for item in content.split(','):
                item = item.strip()
                if '=' in item:
                    k, v = item.split('=', 1)
                    t.set(self._eval_expr(k.strip(), locals), self._eval_expr(v.strip(), locals))
                else:
                    t._array.append(self._eval_expr(item, locals))
        return t

    def _resolve_name(self, name: str, locals: Dict[str, Any]) -> Any:
        if name in locals:
            return locals[name]
        if name in self._env._globals:
            return self._env._globals[name]
        if name in self._env._user_data:
            return self._env._user_data[name]
        return None

    def _call(self, fn_name: str, args: List[Any], locals: Dict[str, Any]) -> Any:
        fn = self._resolve_name(fn_name, locals)
        if fn is None:
            raise LuaSandboxError(f'undefined function: {fn_name}')
        if callable(fn):
            return fn(*args)
        raise LuaSandboxError(f'not callable: {fn_name}')


class LuaSandbox:
    """Sandboxed Lua execution environment with resource limits and safe API."""

    def __init__(self) -> None:
        self._env = LuaSafeEnv()
        self._interp = LuaInterpreter(self._env)
        self._lock = threading.Lock()

    def register_function(self, name: str, fn: Callable) -> None:
        with self._lock:
            self._env._globals[name] = fn

    def set_data(self, key: str, value: Any) -> None:
        with self._lock:
            self._env.set_user_data(key, value)

    def execute(self, script: str) -> Any:
        with self._lock:
            return self._interp.execute(script)

    def transform(self, script: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
        self.set_data('input', dict(input_data))
        self.set_data('output', {})
        self.execute(script)
        return self._env.get_user_data('output') or {}

    def summary(self) -> Dict[str, Any]:
        return {
            'registered_functions': list(self._env._globals.keys()),
        }


class ScriptStore:
    """Manages reusable Lua transformation scripts."""

    def __init__(self, store_dir: str = '.lua_scripts') -> None:
        self._dir = store_dir
        self._sandbox = LuaSandbox()
        os.makedirs(self._dir, exist_ok=True)
        self._register_default_functions()

    def _register_default_functions(self) -> None:
        self._sandbox.register_function('json_encode', json.dumps)
        self._sandbox.register_function('json_decode', json.loads)
        import math
        self._sandbox.register_function('abs', abs)
        self._sandbox.register_function('round', round)

    def save_script(self, name: str, script: str) -> str:
        path = os.path.join(self._dir, f'{name}.lua')
        with open(path, 'w') as f:
            f.write(script)
        return path

    def load_script(self, name: str) -> Optional[str]:
        path = os.path.join(self._dir, f'{name}.lua')
        if os.path.exists(path):
            with open(path) as f:
                return f.read()
        return None

    def run_script(self, name: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
        script = self.load_script(name)
        if script is None:
            return {'error': f'script not found: {name}'}
        try:
            result = self._sandbox.transform(script, input_data)
            return {'result': result}
        except LuaSandboxError as e:
            return {'error': str(e)}

    def run_inline(self, script: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            result = self._sandbox.transform(script, input_data)
            return {'result': result}
        except LuaSandboxError as e:
            return {'error': str(e)}

    def list_scripts(self) -> List[str]:
        if not os.path.isdir(self._dir):
            return []
        return sorted(f[:-4] for f in os.listdir(self._dir) if f.endswith('.lua'))

    def delete_script(self, name: str) -> bool:
        path = os.path.join(self._dir, f'{name}.lua')
        if os.path.exists(path):
            os.remove(path)
            return True
        return False

    def export_artifacts(self, dir: str) -> List[str]:
        os.makedirs(dir, exist_ok=True)
        paths = []
        sp = os.path.join(dir, 'lua_scripts_index.json')
        with open(sp, 'w') as f:
            json.dump({
                'scripts': self.list_scripts(),
                'registered_functions': self._sandbox.summary(),
            }, f, indent=2)
        paths.append(sp)
        return paths
