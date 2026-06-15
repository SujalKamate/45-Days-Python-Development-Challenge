"""Automatic command-line interface generation from module signatures and type metadata."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple, get_type_hints
import datetime
import inspect
import json
import os
import shlex
import sys
import time
import uuid


class CLIArgument:
    """An argument inferred from a function parameter."""

    def __init__(self, name: str, type_hint: str = 'str',
                 default: Any = None, required: bool = True,
                 help_text: str = '') -> None:
        self.name = name
        self.type_hint = type_hint
        self.default = default
        self.required = required
        self.help_text = help_text
        self.has_default = default is not inspect.Parameter.empty

    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'type': self.type_hint,
            'default': repr(self.default) if self.has_default else None,
            'required': self.required,
            'help': self.help_text,
        }

    def format_usage(self) -> str:
        if self.has_default:
            return f'[--{self.name} {self.type_hint.upper()}]'
        return f'<{self.name}:{self.type_hint}>'


class CLICommand:
    """A single generated CLI command backed by a callable."""

    def __init__(self, name: str, fn: Callable[..., Any],
                 description: str = '', aliases: Optional[List[str]] = None) -> None:
        self.name = name
        self.fn = fn
        self.description = description or fn.__doc__ or ''
        self.aliases = aliases or []
        self.arguments: List[CLIArgument] = []

    def _infer_args(self) -> None:
        try:
            hints = get_type_hints(self.fn)
        except Exception:
            hints = {}
        sig = inspect.signature(self.fn)
        type_map = {
            str: 'str', int: 'int', float: 'float', bool: 'bool',
            list: 'list', dict: 'dict', Any: 'any',
        }

        for pname, param in sig.parameters.items():
            if pname in ('self', 'cls', 'args', 'kwargs'):
                continue
            hint = hints.get(pname, str)
            type_str = type_map.get(hint, hint.__name__ if hasattr(hint, '__name__') else 'str')
            is_required = param.default is inspect.Parameter.empty
            default = param.default if not is_required else None
            help_text = ''
            if self.description and ':' in pname:
                help_text = self.description
            arg = CLIArgument(pname, type_str, default, is_required, help_text)
            self.arguments.append(arg)

    def to_dict(self) -> Dict[str, Any]:
        if not self.arguments:
            self._infer_args()
        return {
            'name': self.name,
            'description': self.description,
            'aliases': self.aliases,
            'arguments': [a.to_dict() for a in self.arguments],
        }

    def usage(self) -> str:
        if not self.arguments:
            self._infer_args()
        parts = [f'  {self.name}']
        parts.extend(a.format_usage() for a in self.arguments)
        return ' '.join(parts)

    def help_text(self) -> str:
        if not self.arguments:
            self._infer_args()
        lines = [f'Command: {self.name}', f'  {self.description}', '']
        if self.aliases:
            lines.append(f'Aliases: {", ".join(self.aliases)}')
            lines.append('')
        lines.append('Arguments:')
        for arg in self.arguments:
            req = '(required)' if arg.required else f'(default: {arg.default})'
            lines.append(f'  --{arg.name} <{arg.type_hint}> {req}')
        return '\n'.join(lines)


class ArgumentParser:
    """Parse CLI-style args from a token list against a command definition."""

    @staticmethod
    def parse(args: List[str], command: CLICommand) -> Dict[str, Any]:
        parsed: Dict[str, Any] = {}
        i = 0
        arg_map = {a.name: a for a in command.arguments}

        while i < len(args):
            token = args[i]
            if token.startswith('--'):
                name = token[2:]
                if name in arg_map:
                    arg_def = arg_map[name]
                    if arg_def.type_hint == 'bool':
                        parsed[name] = True
                        i += 1
                    elif i + 1 < len(args):
                        parsed[name] = ArgumentParser._convert(args[i + 1], arg_def.type_hint)
                        i += 2
                    else:
                        parsed[name] = True
                        i += 1
                else:
                    i += 1
            elif not token.startswith('-'):
                remaining = [a for a in command.arguments if a.required and a.name not in parsed]
                if remaining:
                    arg_def = remaining[0]
                    parsed[arg_def.name] = ArgumentParser._convert(token, arg_def.type_hint)
                    i += 1
                else:
                    i += 1
            else:
                i += 1
        return parsed

    @staticmethod
    def _convert(value: str, target_type: str) -> Any:
        if target_type == 'int':
            return int(value)
        if target_type == 'float':
            return float(value)
        if target_type == 'bool':
            return value.lower() in ('true', '1', 'yes')
        return value


class CLIHelpBuilder:
    """Build help documentation for generated CLI."""

    @staticmethod
    def full_help(commands: Dict[str, CLICommand], app_name: str = 'app') -> str:
        lines = [
            f'{app_name} - Auto-generated CLI',
            f'Usage: {app_name} <command> [args...]',
            '',
            'Commands:',
        ]

        for name, cmd in sorted(commands.items()):
            usage = cmd.usage()
            desc = cmd.description[:50] if cmd.description else ''
            lines.append(f'  {usage}')
            if desc:
                lines.append(f'    {desc}')

        lines.append('')
        lines.append('Run "<command> --help" for per-command details.')
        return '\n'.join(lines)


class CLIHistory:
    """Session-persistent execution history with replay support."""

    def __init__(self) -> None:
        self._entries: List[Dict[str, Any]] = []
        self._session_id = uuid.uuid4().hex[:8]

    def record(self, command: str, args: Dict[str, Any],
               result: Any = None, status: str = 'ok',
               elapsed_s: float = 0.0) -> Dict[str, Any]:
        entry = {
            'id': uuid.uuid4().hex[:12],
            'session': self._session_id,
            'command': command,
            'args': args,
            'result': repr(result)[:200] if result is not None else None,
            'status': status,
            'elapsed_s': round(elapsed_s, 4),
            'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        self._entries.append(entry)
        return entry

    def entries(self, limit: int = 100) -> List[Dict[str, Any]]:
        return self._entries[-limit:]

    def last(self) -> Optional[Dict[str, Any]]:
        return self._entries[-1] if self._entries else None

    def replay(self, index: int = -1) -> Optional[Dict[str, Any]]:
        if not self._entries:
            return None
        return self._entries[index]

    def save(self, path: str) -> None:
        with open(path, 'w') as f:
            json.dump(self._entries, f, indent=2)

    def load(self, path: str) -> None:
        try:
            with open(path, 'r') as f:
                self._entries = json.load(f)
        except (IOError, json.JSONDecodeError):
            pass


class CommandGenerator:
    """Generate CLI commands from module/class introspection."""

    @staticmethod
    def from_module(module: Any, prefix: str = '',
                    skip_private: bool = True) -> Dict[str, CLICommand]:
        commands: Dict[str, CLICommand] = {}
        for name, obj in inspect.getmembers(module):
            if skip_private and name.startswith('_'):
                continue
            if inspect.isfunction(obj) or inspect.ismethod(obj):
                cmd_name = f'{prefix}{name}' if prefix else name
                cmd = CLICommand(cmd_name, obj)
                cmd._infer_args()
                commands[cmd_name] = cmd
        return commands

    @staticmethod
    def from_class(cls: type, prefix: str = '',
                   skip_private: bool = True) -> Dict[str, CLICommand]:
        commands: Dict[str, CLICommand] = {}
        for name, method in inspect.getmembers(cls, predicate=inspect.isfunction):
            if skip_private and name.startswith('_'):
                continue
            cmd_name = f'{prefix}{name}' if prefix else name
            cmd = CLICommand(cmd_name, method)
            cmd._infer_args()
            commands[cmd_name] = cmd
        return commands

    @staticmethod
    def from_instance(obj: Any, prefix: str = '',
                      skip_private: bool = True) -> Dict[str, CLICommand]:
        return CommandGenerator.from_class(type(obj), prefix, skip_private)


class CLIExecutionContext:
    """Holds parsed args and provides execution helpers."""

    def __init__(self, command: str, args: Dict[str, Any],
                 raw_line: str = '') -> None:
        self.command = command
        self.args = args
        self.raw_line = raw_line
        self.start_time = time.time()

    def get(self, name: str, default: Any = None) -> Any:
        return self.args.get(name, default)


class CLIDispatcher:
    """Route user input to commands and return results."""

    def __init__(self, commands: Dict[str, CLICommand],
                 history: CLIHistory) -> None:
        self._commands = commands
        self._history = history
        self._alias_map: Dict[str, str] = {}
        for name, cmd in commands.items():
            for alias in cmd.aliases:
                self._alias_map[alias] = name

    def resolve(self, name: str) -> Optional[CLICommand]:
        if name in self._commands:
            return self._commands[name]
        if name in self._alias_map:
            return self._commands.get(self._alias_map[name])
        return None

    def dispatch_line(self, line: str) -> Dict[str, Any]:
        parts = shlex.split(line.strip())
        if not parts:
            return {'status': 'empty', 'command': '', 'result': None}
        cmd_name = parts[0]
        cmd_args = parts[1:]

        if cmd_name in ('help', '--help', '-h'):
            return self._handle_help(cmd_args)
        if cmd_name == 'history':
            return self._handle_history()
        if cmd_name == 'replay':
            return self._handle_replay(cmd_args)

        cmd = self.resolve(cmd_name)
        if cmd is None:
            return {'status': 'error', 'command': cmd_name,
                    'error': f'Unknown command: {cmd_name}', 'result': None}

        try:
            parsed = ArgumentParser.parse(cmd_args, cmd)
            ctx = CLIExecutionContext(cmd_name, parsed, line)
            start = time.perf_counter()
            result = cmd.fn(**parsed)
            elapsed = time.perf_counter() - start
            self._history.record(cmd_name, parsed, result, 'ok', elapsed)
            return {'status': 'ok', 'command': cmd_name,
                    'result': result, 'elapsed_s': round(elapsed, 4)}
        except Exception as e:
            elapsed = time.perf_counter() - ctx.start_time if 'ctx' in dir() else 0
            self._history.record(cmd_name, {}, None, 'error', elapsed)
            return {'status': 'error', 'command': cmd_name,
                    'error': str(e), 'result': None}

    def _handle_help(self, args: List[str]) -> Dict[str, Any]:
        if args:
            cmd = self.resolve(args[0])
            if cmd:
                return {'status': 'ok', 'command': 'help',
                        'result': cmd.help_text()}
        result = CLIHelpBuilder.full_help(self._commands)
        return {'status': 'ok', 'command': 'help', 'result': result}

    def _handle_history(self) -> Dict[str, Any]:
        entries = self._history.entries(20)
        return {'status': 'ok', 'command': 'history', 'result': entries}

    def _handle_replay(self, args: List[str]) -> Dict[str, Any]:
        idx = int(args[0]) if args else -1
        entry = self._history.replay(idx)
        if entry and entry.get('command'):
            return self.dispatch_line(f"{entry['command']} {' '.join(f'--{k}={v}' for k, v in entry.get('args', {}).items())}")
        return {'status': 'error', 'command': 'replay', 'error': 'No entry to replay'}


class CLIGeneratorEngine:
    """Top-level automatic CLI generation engine."""

    def __init__(self, app_name: str = 'app') -> None:
        self._app_name = app_name
        self._commands: Dict[str, CLICommand] = {}
        self._history = CLIHistory()
        self._dispatcher = CLIDispatcher(self._commands, self._history)

    @property
    def commands(self) -> Dict[str, CLICommand]:
        return self._commands

    @property
    def history(self) -> CLIHistory:
        return self._history

    def register_command(self, name: str, fn: Callable[..., Any],
                         description: str = '',
                         aliases: Optional[List[str]] = None) -> CLICommand:
        cmd = CLICommand(name, fn, description, aliases)
        cmd._infer_args()
        self._commands[name] = cmd
        return cmd

    def register_from_module(self, module: Any, prefix: str = '') -> int:
        cmds = CommandGenerator.from_module(module, prefix)
        self._commands.update(cmds)
        return len(cmds)

    def register_from_class(self, cls: type, prefix: str = '') -> int:
        cmds = CommandGenerator.from_class(cls, prefix)
        self._commands.update(cmds)
        return len(cmds)

    def register_from_instance(self, obj: Any, prefix: str = '') -> int:
        cmds = CommandGenerator.from_instance(obj, prefix)
        self._commands.update(cmds)
        return len(cmds)

    def remove_command(self, name: str) -> bool:
        return self._commands.pop(name, None) is not None

    def list_commands(self) -> List[str]:
        return list(self._commands.keys())

    def run_line(self, line: str) -> Dict[str, Any]:
        return self._dispatcher.dispatch_line(line)

    def run_interactive(self, banner: str = '') -> None:
        if banner:
            print(banner)
        print(self._dispatcher._handle_help([])['result'])
        while True:
            try:
                line = input(f'{self._app_name}> ').strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not line:
                continue
            if line.lower() in ('quit', 'exit'):
                break
            result = self.run_line(line)
            if result['status'] == 'ok' and result['result'] is not None:
                r = result['result']
                if isinstance(r, str):
                    print(r)
                else:
                    print(json.dumps(r, indent=2, default=str))
            elif result['status'] == 'error':
                print(f'Error: {result.get("error", "unknown")}', file=sys.stderr)

    def summary(self) -> Dict[str, Any]:
        return {
            'app_name': self._app_name,
            'commands': len(self._commands),
            'command_names': self.list_commands(),
            'history_entries': len(self._history.entries(9999)),
        }

    def report_text(self) -> str:
        s = self.summary()
        return (
            f'CLI Generator Engine\n'
            f'  App: {s["app_name"]}\n'
            f'  Commands: {s["commands"]}\n'
            f'  History entries: {s["history_entries"]}'
        )

    def export_artifacts(self, dir: str) -> List[str]:
        os.makedirs(dir, exist_ok=True)
        paths = []
        sp = os.path.join(dir, 'cli_generator.json')
        cmds_data = {n: c.to_dict() for n, c in self._commands.items()}
        data = {'summary': self.summary(), 'commands': cmds_data}
        with open(sp, 'w') as f:
            json.dump(data, f, indent=2)
        paths.append(sp)
        hp = os.path.join(dir, 'cli_history.json')
        self._history.save(hp)
        paths.append(hp)
        return paths
