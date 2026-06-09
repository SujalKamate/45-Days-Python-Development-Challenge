from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import json
import math
import os
import random
import statistics
import time


@dataclass
class DataPoint:
    name: str = ''
    value: float = 0.0
    active: bool = False
    metadata: Optional[Dict[str, str]] = None

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

    def keys(self) -> List[str]:
        return ['name', 'value', 'active']

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    def to_dict(self) -> Dict[str, Any]:
        return {'name': self.name, 'value': self.value, 'active': self.active}

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> DataPoint:
        return DataPoint(
            name=str(d.get('name', '')),
            value=float(d.get('value', 0)),
            active=bool(d.get('active', False)),
            metadata=d.get('metadata') if isinstance(d.get('metadata'), dict) else None,
        )


@dataclass
class Summary:
    count: int = 0
    min_val: float = 0.0
    max_val: float = 0.0
    avg: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {'count': self.count, 'min': self.min_val, 'max': self.max_val, 'avg': self.avg}


@dataclass
class DatasetResult:
    total_items: int = 0
    active_items: int = 0
    summary: Optional[Summary] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'total_items': self.total_items,
            'active_items': self.active_items,
            'summary': self.summary.to_dict() if self.summary else {},
        }


@dataclass
class BaseAppState:
    history: List[str] = field(default_factory=list)
    records: Dict[str, Any] = field(default_factory=dict)
    flags: Dict[str, bool] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    runs: int = 0
    errors: int = 0


class BaseApp:
    def __init__(self) -> None:
        self.state = BaseAppState()
        self.output_dir = Path('outputs')
        self.output_dir.mkdir(exist_ok=True)
        self.seed = 42
        random.seed(self.seed)

    # ── Logging / state mutation helpers ───────────────────────────────

    def log(self, message: str) -> None:
        stamp = datetime.now().strftime('%H:%M:%S')
        entry = f'[{stamp}] {message}'
        self.state.history.append(entry)
        print(entry)

    def section(self, title: str) -> None:
        print()
        print('=' * 70)
        print(title)
        print('=' * 70)

    def non_empty(self, value: Any) -> bool:
        return bool(str(value).strip())

    def safe_int(self, value: Any, default: int = 0) -> int:
        try:
            return int(str(value).strip())
        except Exception:
            return default

    def safe_float(self, value: Any, default: float = 0.0) -> float:
        try:
            return float(str(value).strip())
        except Exception:
            return default

    def clamp(self, value: float, low: float, high: float) -> float:
        return max(low, min(high, value))

    def normalize_text(self, value: str) -> str:
        return ' '.join(str(value).strip().split())

    def normalize_key(self, value: str) -> str:
        return self.normalize_text(value).lower().replace(' ', '_')

    def split_words(self, value: str) -> List[str]:
        cleaned = ''.join(ch.lower() if ch.isalnum() else ' ' for ch in value)
        return [part for part in cleaned.split() if part]

    def chunk(self, items: List[Any], size: int) -> List[List[Any]]:
        size = max(1, size)
        return [items[i:i + size] for i in range(0, len(items), size)]

    def format_kv(self, key: str, value: Any) -> str:
        return f'{key:<20} : {value}'

    def render_table(self, rows: List[Dict[str, Any] | DataPoint]) -> str:
        if not rows:
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
        path = self.output_dir / name
        path.write_text(json.dumps(payload, indent=2, default=str), encoding='utf-8')
        return path

    def load_json(self, path: Path) -> Dict[str, Any]:
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding='utf-8'))
        except Exception:
            return {}

    def save_text(self, name: str, content: str) -> Path:
        path = self.output_dir / name
        path.write_text(content, encoding='utf-8')
        return path

    def load_text(self, path: Path) -> str:
        if not path.exists():
            return ''
        return path.read_text(encoding='utf-8')

    def record(self, key: str, value: Any) -> None:
        self.state.records[key] = value

    def toggle(self, key: str, default: bool = False) -> bool:
        current = self.state.flags.get(key, default)
        self.state.flags[key] = not current
        return self.state.flags[key]

    def summarize_list(self, values: List[float]) -> Summary:
        if not values:
            return Summary()
        return Summary(
            count=len(values),
            min_val=min(values),
            max_val=max(values),
            avg=round(sum(values) / len(values), 4),
        )

    def stats_from_numbers(self, values: List[float]) -> Dict[str, Any]:
        if not values:
            return {'mean': 0, 'median': 0, 'mode': None, 'stdev': 0}
        try:
            mode_value = statistics.mode(values)
        except Exception:
            mode_value = None
        return {
            'mean': round(statistics.mean(values), 4),
            'median': round(statistics.median(values), 4),
            'mode': mode_value,
            'stdev': round(statistics.pstdev(values), 4) if len(values) > 1 else 0,
        }

    def history_tail(self, count: int = 5) -> List[str]:
        return self.state.history[-count:]

    def export_state(self) -> Path:
        payload = {
            'created_at': self.state.created_at,
            'runs': self.state.runs,
            'errors': self.state.errors,
            'records': self.state.records,
            'flags': self.state.flags,
            'history': self.history_tail(10),
        }
        return self.save_json('state.json', payload)

    def display_report(self) -> None:
        self.section('Summary')
        print(self.format_kv('Runs', self.state.runs))
        print(self.format_kv('Errors', self.state.errors))
        print(self.format_kv('Records', len(self.state.records)))
        print(self.format_kv('Flags', len(self.state.flags)))
        print(self.format_kv('History entries', len(self.state.history)))
        self.log(f'Exported to {self.export_state()}')

    def demo_data(self) -> List[DataPoint]:
        return [
            DataPoint(name='alpha', value=1, active=True),
            DataPoint(name='beta', value=2, active=False),
            DataPoint(name='gamma', value=3, active=True),
        ]

    def dataset(self) -> List[DataPoint]:
        return self.demo_data()

    def process_dataset(self, items: List[Dict[str, Any] | DataPoint]) -> Dict[str, Any]:
        typed = [DataPoint.from_dict(i) if isinstance(i, dict) else i for i in items]
        active = [item for item in typed if item.active]
        values = [item.value for item in active]
        summary = self.summarize_list(values) if values else Summary()
        return DatasetResult(
            total_items=len(items),
            active_items=len(active),
            summary=summary,
        ).to_dict()

    def finalize(self) -> None:
        self.export_state()
        self.log('Finalized successfully')
