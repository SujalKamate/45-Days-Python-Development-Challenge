from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import copy
import json
import math
import os
import random
import statistics
import threading
import time
import unicodedata

from resource_guard import ResourceGuard

from json_depth_guard import safe_json_loads

from decimal_utils import Money, safe_decimal

from drift_timer import DriftCorrectedTimer, Stopwatch


@dataclass
class BaseAppState:
    history: List[str] = field(default_factory=list)
    records: Dict[str, Any] = field(default_factory=dict)
    flags: Dict[str, bool] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    runs: int = 0
    errors: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock, compare=False, repr=False)


class BaseApp:
    def __init__(self, seed: int | None = None) -> None:
        self.state = BaseAppState()
        self.output_dir = Path('outputs')
        self.output_dir.mkdir(exist_ok=True)
        self.timer = DriftCorrectedTimer()
        self.seed = 42
        random.seed(self.seed)

    # ── Logging / state mutation helpers ───────────────────────────────

    def log(self, message: str) -> None:
        stamp = datetime.now().strftime('%H:%M:%S')
        entry = f'[{stamp}] {message}'
        self.state.history.append(entry)
        if len(self.state.history) > self.state.max_history:
            del self.state.history[:len(self.state.history) - self.state.max_history]
        print(entry)

    def rotate_logs(self, keep: int = 50) -> None:
        from pathlib import Path
        logs = sorted(Path(self.output_dir).glob('*.json*'))
        for p in logs[:-keep]:
            p.unlink()

    def section(self, title: str) -> None:
        print()
        print('=' * 70)
        print(title)
        print('=' * 70)

    def non_empty(self, value: Any) -> bool:
        if value is None:
            return False
        if isinstance(value, str):
            return value.strip() != ''
        if isinstance(value, (list, tuple, dict, set)):
            return len(value) > 0
        if isinstance(value, (int, float)):
            return value != 0
        return bool(str(value).strip())

    def safe_int(self, value: Any) -> int:
        return int(str(value).strip())

    def safe_float(self, value: Any) -> float:
        return float(str(value).strip())

    def safe_money(self, value: str | int | float) -> Money:
        """Convert *value* to an exact ``Money`` instance."""
        return Money(value)

    def clamp(self, value: float, low: float, high: float) -> float:
        return max(low, min(high, value))

    def normalize_text(self, value: str) -> str:
        return ' '.join(unicodedata.normalize('NFKC', str(value)).strip().split())

    def normalize_key(self, value: str) -> str:
        return self.normalize_text(value).lower().replace(' ', '_')

    def split_words(self, value: str) -> List[str]:
        cleaned = ''.join(
            ch.lower() if ch.isalnum() else ' '
            for ch in unicodedata.normalize('NFKC', str(value))
        )
        return [part for part in cleaned.split() if part]

    def chunk(self, items: List[Any], size: int) -> List[List[Any]]:
        size = max(1, size)
        return [items[i:i + size] for i in range(0, len(items), size)]

    def format_kv(self, key: str, value: Any) -> str:
        return f'{key:<20} : {value}'

    def render_table(self, rows: List[Dict[str, Any]]) -> str:
        if rows is None or not rows:
            return '(empty)'
        keys = list(rows[0].keys())
        widths = {k: max(len(k), max(len(str(row.get(k, ''))) for row in rows)) for k in keys}
        header = ' | '.join(k.ljust(widths[k]) for k in keys)
        lines = [header, '-+-'.join('-' * widths[k] for k in keys)]
        for row in rows:
            lines.append(' | '.join(str(row.get(k, '')).ljust(widths[k]) for k in keys))
        return '\n'.join(lines)

    # ── File I/O helpers ────────────────────────────────────────────────

    def save_json(self, name: str, payload: Dict[str, Any]) -> Path:
        path = self.output_dir / self._guard.qualify(name)
        path.write_text(json.dumps(payload, indent=2, default=str), encoding='utf-8')
        return path

    def load_json(self, path: Path) -> Dict[str, Any]:
        self._guard.check_path(path)
        if not path.exists():
            return {}
        try:
            return FileManager.read_json(path)
        except Exception:
            return {}

    def save_text(self, name: str, content: str) -> Path:
        path = self.output_dir / self._guard.qualify(name)
        path.write_text(content, encoding='utf-8')
        return path

    def load_text(self, path: Path) -> str:
        self._guard.check_path(path)
        if not path.exists():
            return ''

    def record(self, key: str, value: Any) -> None:
        self.state.records[key] = copy.deepcopy(value)

    def toggle(self, key: str, default: bool = False) -> bool:
        current = self.state.flags.get(key, default)
        self.state.flags[key] = not current
        return self.state.flags[key]

    def summarize_list(self, values: List[float]) -> Dict[str, Any]:
        from stat_guard import validate_sample_size
        validate_sample_size(values, 1, 'values')
        return {
            'count': len(values),
            'min': min(values),
            'max': max(values),
            'avg': round(sum(values) / len(values), 4),
        }

    def stats_from_numbers(self, values: List[float]) -> Dict[str, Any]:
        from stat_guard import validate_sample_size, safe_stdev
        validate_sample_size(values, 1, 'values')
        try:
            mode_value = statistics.mode(values)
        except Exception:
            mode_value = None
        return {
            'mean': round(statistics.mean(values), 4),
            'median': round(statistics.median(values), 4),
            'mode': mode_value,
            'stdev': round(safe_stdev(values), 4),
        }

    def history_tail(self, count: int = 5) -> List[str]:
        return self.state.history[-count:]

    def export_state(self) -> Path:
        payload = {
            'version': 1,
            'exported_at': datetime.now(timezone.utc).isoformat(),
            'app': {
                'created_at': self.state.created_at.isoformat() if self.state.created_at else None,
                'runs': self.state.runs,
                'errors': self.state.errors,
                'record_count': len(self.state.records),
                'flag_count': len(self.state.flags),
            },
            'summary': {
                'recent_history': self.history_tail(5),
                'history_count': len(self.state.history),
            },
            'metadata': {
                'records_summary': {k: self._describe_value(v) for k, v in list(self.state.records.items())[:20]},
                'flags': dict(self.state.flags),
            },
        }
        return self.save_json('state.json', payload)

    def _describe_value(self, value: Any) -> Dict[str, Any]:
        if isinstance(value, dict):
            return {'type': 'dict', 'keys': list(value.keys())[:10], 'size': len(value)}
        if isinstance(value, list):
            return {'type': 'list', 'length': len(value)}
        if isinstance(value, str):
            return {'type': 'str', 'length': len(value)}
        if isinstance(value, (int, float)):
            return {'type': type(value).__name__, 'value': value}
        if isinstance(value, bool):
            return {'type': 'bool', 'value': value}
        if value is None:
            return {'type': 'null'}
        return {'type': type(value).__name__}

    def display_report(self) -> None:
        self.section('Summary')
        print(self.format_kv('Runs', self.state.runs))
        print(self.format_kv('Errors', self.state.errors))
        print(self.format_kv('Records', len(self.state.records)))
        print(self.format_kv('Flags', len(self.state.flags)))
        print(self.format_kv('History entries', len(self.state.history)))
        self.log(f'Exported to {self.export_state()}')

    def demo_data(self) -> List[Dict[str, Any]]:
        return [
            {'name': 'alpha', 'value': 1, 'active': True},
            {'name': 'beta', 'value': 2, 'active': False},
            {'name': 'gamma', 'value': 3, 'active': True},
        ]

    def dataset(self) -> List[Dict[str, Any]]:
        return self.demo_data()

    def process_dataset(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        active = [item for item in items if item.get('active', False)]
        values = [item.get('value', 0) for item in active]
        return {
            'total_items': len(items),
            'active_items': len(active),
            'summary': self.summarize_list(values),
        }

    def find_duplicates(self, items: List[Any]) -> List[Any]:
        """Return duplicate entries in O(n) using a hash set.

        Each item is converted to a hashable key (tuple for dicts,
        ``str(item)`` for other unhashable types) for O(1) lookup.
        """
        seen: set[Any] = set()
        duplicates: List[Any] = []
        for item in items:
            if isinstance(item, dict):
                key = tuple(sorted(item.items()))
            else:
                try:
                    key = hash(item)
                except TypeError:
                    key = str(item)
            if key in seen:
                duplicates.append(item)
            else:
                seen.add(key)
        return duplicates

    def finalize(self) -> None:
        self.export_state()
        self.log('Finalized successfully')
