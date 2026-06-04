"""I/O abstraction layer decoupling business logic from console and file operations.

Swap the handler for testing: use ``BufferedHandler`` to capture output
in memory instead of printing to stdout or writing to disk.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional
import json


class OutputHandler:
    """Production handler — prints to stdout and writes files to disk."""

    def __init__(self, output_dir: Optional[Path] = None) -> None:
        self.output_dir = output_dir or Path('outputs')
        self.output_dir.mkdir(exist_ok=True)

    def section(self, title: str) -> None:
        print()
        print('=' * 70)
        print(title)
        print('=' * 70)

    def kv(self, key: str, value: Any) -> None:
        print(f'{key:<20} : {value}')

    def write(self, text: str) -> None:
        print(text, end='')

    def log(self, message: str) -> None:
        stamp = __import__('datetime').datetime.now().strftime('%H:%M:%S')
        print(f'[{stamp}] {message}')

    def summary(self, state: Any) -> None:
        self.section('Summary')
        self.kv('Runs', getattr(state, 'runs', 0))
        self.kv('Errors', getattr(state, 'errors', 0))
        self.kv('Records', len(getattr(state, 'records', {})))
        self.kv('Flags', len(getattr(state, 'flags', {})))
        self.kv('History entries', len(getattr(state, 'history', [])))

    def save_json(self, name: str, payload: Dict[str, Any]) -> Path:
        path = self.output_dir / name
        path.write_text(json.dumps(payload, indent=2, default=str), encoding='utf-8')
        return path

    def save_text(self, name: str, content: str) -> Path:
        path = self.output_dir / name
        path.write_text(content, encoding='utf-8')
        return path


class BufferedHandler(OutputHandler):
    """Test-oriented handler — buffers output in memory, no side effects."""

    def __init__(self, output_dir: Optional[Path] = None) -> None:
        super().__init__(output_dir)
        self.buffer: List[str] = []
        self.saved: Dict[str, Dict[str, Any]] = {}

    def section(self, title: str) -> None:
        self.buffer.append(f'=== {title} ===')

    def kv(self, key: str, value: Any) -> None:
        self.buffer.append(f'{key}: {value}')

    def write(self, text: str) -> None:
        self.buffer.append(text)

    def log(self, message: str) -> None:
        self.buffer.append(f'[LOG] {message}')

    def save_json(self, name: str, payload: Dict[str, Any]) -> Path:
        self.saved[name] = payload
        return self.output_dir / name
