from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Generator, List, Optional, Tuple
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

from import_validator import ImportValidationEngine


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

try:
    from .contracts import DataProvider, DataProcessor, AppRunner
except ImportError:
    from contracts import DataProvider, DataProcessor, AppRunner  # type: ignore[import-untyped]


@dataclass
class BaseAppState:
    history: List[str] = field(default_factory=list)
    records: Dict[str, Any] = field(default_factory=dict)
    flags: Dict[str, bool] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    runs: int = 0
    errors: int = 0
    perf_metrics: Dict[str, List[float]] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _next_id: int = 0


class _OutputProxy:
    def __init__(self, app: BaseApp) -> None:
        self._app = app

    def section(self, title: str) -> None:
        self._app.section(title)

    def kv(self, key: str, value: Any) -> None:
        print(self._app.format_kv(key, value))


class BaseApp(DataProvider, DataProcessor, AppRunner):
    def __init__(self) -> None:
        self.state = BaseAppState()
        self.output_dir = Path('outputs')
        self.output_dir.mkdir(exist_ok=True)
        self.timer = DriftCorrectedTimer()
        self.seed = 42
        random.seed(self.seed)
        self.output = _OutputProxy(self)
        self._tasks: Dict[str, Any] = {}
        self._next_id: int = 0
        self._import_val = ImportValidationEngine()

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

    @staticmethod
    def _compute_checksum(data: Dict[str, Any]) -> str:
        canonical = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode('utf-8')).hexdigest()

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

    def _report_data(self) -> Dict[str, Any]:
        return {
            'runs': self.state.runs,
            'errors': self.state.errors,
            'records': len(self.state.records),
            'flags': len(self.state.flags),
            'history_entries': len(self.state.history),
        }
        payload['_checksum'] = self._compute_checksum(payload)
        return self.save_json('state.json', payload)

    @contextmanager
    def _time_it(self, label: str) -> Generator[None, None, None]:
        start = time.perf_counter()
        try:
            yield
        finally:
            elapsed = time.perf_counter() - start
            self.state.perf_metrics.setdefault(label, []).append(round(elapsed, 6))

    def report_metrics(self) -> None:
        if not self.state.perf_metrics:
            return
        self.section('Performance Metrics')
        for label, timings in sorted(self.state.perf_metrics.items()):
            avg = sum(timings) / len(timings)
            total = sum(timings)
            print(self.format_kv(label, f'{avg*1000:.1f}ms avg ({total*1000:.1f}ms total, {len(timings)} call(s))'))

    def display_report(self) -> None:
        print(self.format_report())
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

    def run(self) -> None:
        self.state.runs += 1
        self.section('Processing')
        with self._time_it('dataset'):
            items = self.dataset()
        with self._time_it('process_dataset'):
            result = self.process_dataset(items)
        self.record('result', result)
        print(json.dumps(result, indent=2))
        self.display_report()
        self.report_metrics()

    def finalize(self) -> None:
        with self._time_it('export_state'):
            self.export_state()
        self.log('Finalized successfully')

    def iv_validate_source(self, source: str, filename: str = '') -> Any:
        return self._import_val.validate_source(source, filename)

    def iv_validate_file(self, path: str) -> Any:
        return self._import_val.validate_file(path)

    def iv_validate_module(self, module_name: str) -> Any:
        return self._import_val.validate_module(module_name)

    def iv_add_rule(self, rule: Any) -> None:
        self._import_val.add_rule(rule)

    def iv_remove_rule(self, name: str) -> bool:
        return self._import_val.remove_rule(name)

    def iv_list_rules(self) -> List[str]:
        return self._import_val.list_rules()

    def iv_set_strict(self, enabled: bool) -> None:
        self._import_val.set_strict_mode(enabled)

    def iv_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        return self._import_val.validation_history(limit)

    def iv_summary(self) -> Dict[str, Any]:
        return self._import_val.summary()

    def iv_report(self) -> str:
        return self._import_val.report_text()
