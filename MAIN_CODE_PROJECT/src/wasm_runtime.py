"""WebAssembly plugin runtime with WASI compatibility for sandboxed module execution."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Set, Tuple
import datetime
import hashlib
import inspect
import json
import os
import shutil
import struct
import sys
import tempfile
import threading
import time
import traceback
import uuid


class WASIError(Exception):
    pass


class WASIEndpoint:
    """A single WASI filesystem or network endpoint with access control."""

    def __init__(self, path: str, writable: bool = False, label: str = '') -> None:
        self.path = os.path.abspath(path)
        self.writable = writable
        self.label = label or os.path.basename(path)


class WASIContext:
    """WASI-compatible syscall interfaces exposed to plugins."""

    def __init__(self, plugin_id: str, endpoints: Optional[List[WASIEndpoint]] = None) -> None:
        self._plugin_id = plugin_id
        self._endpoints = {ep.path: ep for ep in (endpoints or [])}
        self._env: Dict[str, str] = {}
        self._args: List[str] = []
        self._stdout: List[str] = []
        self._stderr: List[str] = []
        self._clock_offset: float = 0.0

    def set_env(self, key: str, value: str) -> None:
        self._env[key] = value

    def set_args(self, args: List[str]) -> None:
        self._args = args

    def fd_write(self, fd: int, data: str) -> int:
        if fd == 1:
            self._stdout.append(data)
        elif fd == 2:
            self._stderr.append(data)
        return len(data.encode('utf-8'))

    def fd_read(self, fd: int, max_size: int = 4096) -> bytes:
        return b''

    def path_open(self, path: str, flags: int = 0) -> bool:
        resolved = os.path.abspath(path)
        for allowed_path, ep in self._endpoints.items():
            if resolved.startswith(allowed_path):
                if not ep.writable and flags & 2:
                    raise WASIError(f'read-only endpoint: {path}')
                return True
        raise WASIError(f'access denied: {path}')

    def clock_time_get(self) -> int:
        return int((time.time() + self._clock_offset) * 1_000_000_000)

    def random_get(self, length: int) -> bytes:
        return os.urandom(length)

    def proc_exit(self, code: int) -> None:
        raise SystemExit(code)

    @property
    def stdout(self) -> str:
        return ''.join(self._stdout)

    @property
    def stderr(self) -> str:
        return ''.join(self._stderr)


class WASMModule:
    """Represents a loaded WebAssembly module with exported functions."""

    def __init__(self, name: str, source: str = '', bytecode: bytes = b'') -> None:
        self.name = name
        self.source = source
        self.bytecode = bytecode or source.encode('utf-8')
        self._exports: Dict[str, Callable] = {}
        self._imports: List[str] = []
        self._hash = hashlib.sha256(self.bytecode).hexdigest()[:16]
        self._sandbox: Optional[WASIContext] = None

    def define_export(self, name: str, fn: Callable) -> None:
        self._exports[name] = fn

    def call_export(self, name: str, *args: Any, ctx: Optional[WASIContext] = None) -> Any:
        prev = self._sandbox
        if ctx:
            self._sandbox = ctx
        try:
            fn = self._exports.get(name)
            if fn is None:
                raise WASIError(f'export not found: {name}')
            return fn(*args)
        finally:
            if ctx:
                self._sandbox = prev

    @property
    def exports(self) -> List[str]:
        return list(self._exports.keys())

    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'exports': self.exports,
            'hash': self._hash,
            'size': len(self.bytecode),
        }


class WASMRuntime:
    """WebAssembly runtime that loads, sandboxes, and executes plugins."""

    def __init__(self) -> None:
        self._modules: Dict[str, WASMModule] = {}
        self._lock = threading.Lock()
        self._active_instances: int = 0

    def load_module(self, name: str, source: str) -> WASMModule:
        module = WASMModule(name, source)
        self._parse_module(module)
        with self._lock:
            self._modules[name] = module
        return module

    def load_module_from_file(self, path: str) -> WASMModule:
        name = os.path.splitext(os.path.basename(path))[0]
        with open(path, 'rb') as f:
            data = f.read()
        try:
            text = data.decode('utf-8')
        except UnicodeDecodeError:
            text = ''
        return self.load_module(name, text or data.hex())

    def _parse_module(self, module: WASMModule) -> None:
        module.define_export('_start', lambda: None)
        lines = module.source.split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith('export ') and '(' in line:
                parts = line.split('(')[0].strip()
                func_name = parts.replace('export ', '', 1).strip()
                if func_name and func_name != '_start':
                    module.define_export(func_name, lambda *a, **kw: None)

    def instantiate(self, name: str, ctx: WASIContext) -> bool:
        with self._lock:
            module = self._modules.get(name)
            if module is None:
                return False
        module._sandbox = ctx
        self._active_instances += 1
        return True

    def execute(self, name: str, export: str = '_start', *args: Any) -> Any:
        with self._lock:
            module = self._modules.get(name)
        if module is None:
            raise WASIError(f'module not found: {name}')
        try:
            return module.call_export(export, *args)
        except SystemExit:
            return None
        finally:
            self._active_instances -= 1

    @property
    def active_instances(self) -> int:
        return self._active_instances

    def list_modules(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [m.to_dict() for m in self._modules.values()]

    def unload(self, name: str) -> bool:
        with self._lock:
            return self._modules.pop(name, None) is not None


class PluginSandbox:
    """Sandboxed plugin execution environment."""

    def __init__(self, plugin_id: str, runtime: WASMRuntime,
                 endpoints: Optional[List[WASIEndpoint]] = None) -> None:
        self._plugin_id = plugin_id
        self._runtime = runtime
        self._ctx = WASIContext(plugin_id, endpoints)
        self._module_name = ''

    def load(self, name: str, source: str) -> None:
        self._runtime.load_module(name, source)
        self._module_name = name
        self._runtime.instantiate(name, self._ctx)

    def set_env(self, key: str, value: str) -> None:
        self._ctx.set_env(key, value)

    def set_args(self, args: List[str]) -> None:
        self._ctx.set_args(args)

    def run(self, export: str = '_start', *args: Any) -> Any:
        return self._runtime.execute(self._module_name, export, *args)

    @property
    def stdout(self) -> str:
        return self._ctx.stdout

    @property
    def stderr(self) -> str:
        return self._ctx.stderr


class PluginRegistry:
    """Manages plugin discovery, loading, and lifecycle."""

    def __init__(self, plugin_dir: str = '.plugins') -> None:
        self._runtime = WASMRuntime()
        self._sandboxes: Dict[str, PluginSandbox] = {}
        self._plugin_dir = plugin_dir
        self._lock = threading.Lock()
        os.makedirs(self._plugin_dir, exist_ok=True)

    def register_plugin(self, plugin_id: str, source: str,
                        endpoints: Optional[List[WASIEndpoint]] = None) -> PluginSandbox:
        sandbox = PluginSandbox(plugin_id, self._runtime, endpoints)
        sandbox.load(plugin_id, source)
        with self._lock:
            self._sandboxes[plugin_id] = sandbox
        return sandbox

    def register_plugin_from_path(self, file_path: str) -> Optional[PluginSandbox]:
        if not os.path.exists(file_path):
            return None
        plugin_id = os.path.splitext(os.path.basename(file_path))[0]
        with open(file_path, 'rb') as f:
            data = f.read()
        try:
            source = data.decode('utf-8')
        except UnicodeDecodeError:
            source = data.hex()
        return self.register_plugin(plugin_id, source)

    def get_plugin(self, plugin_id: str) -> Optional[PluginSandbox]:
        with self._lock:
            return self._sandboxes.get(plugin_id)

    def run_plugin(self, plugin_id: str, export: str = '_start', *args: Any) -> Any:
        sandbox = self.get_plugin(plugin_id)
        if sandbox is None:
            raise WASIError(f'plugin not found: {plugin_id}')
        return sandbox.run(export, *args)

    def unload_plugin(self, plugin_id: str) -> bool:
        with self._lock:
            return self._sandboxes.pop(plugin_id, None) is not None

    def list_plugins(self) -> List[Dict[str, Any]]:
        return self._runtime.list_modules()

    def discover_plugins(self) -> List[str]:
        if not os.path.isdir(self._plugin_dir):
            return []
        discovered = []
        for fname in os.listdir(self._plugin_dir):
            if fname.endswith(('.wasm', '.wat', '.py')):
                plugin_id = os.path.splitext(fname)[0]
                if plugin_id not in self._sandboxes:
                    path = os.path.join(self._plugin_dir, fname)
                    self.register_plugin_from_path(path)
                    discovered.append(plugin_id)
        return discovered

    def export_artifacts(self, dir: str) -> List[str]:
        os.makedirs(dir, exist_ok=True)
        paths = []
        sp = os.path.join(dir, 'wasm_plugins.json')
        with open(sp, 'w') as f:
            json.dump(self.list_plugins(), f, indent=2, default=str)
        paths.append(sp)
        return paths
