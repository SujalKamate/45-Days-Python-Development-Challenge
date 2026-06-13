from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy as _deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Tuple
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

from file_manager import FileManage


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

from merkle_tree import MerkleTree, IncrementalStateReplicator


@dataclass
class BaseAppState:
    history: HistoryStore = field(default_factory=lambda: HistoryStore(1000))
    records: Dict[str, Any] = field(default_factory=dict)
    flags: Dict[str, bool] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    runs: int = 0
    errors: int = 0
    max_history: int = 1000
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
        self._replicator = IncrementalStateReplicator()
        self._guard = ResourceGuard('BaseApp', self.output_dir

    # ── Logging / state mutation helpers ───────────────────────────────

    def log(self, message: str) -> None:
        stamp = datetime.now().strftime('%H:%M:%S')
        entry = f'[{stamp}] {message}'
        self.state.history.append(entry)
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
        old_value = self.state.records.get(key)
        with self.state._lock:
            self._wal.log_update('main', key, old_value, value)
            self.state.records[key] = _deepcopy(value)

    def parallel_map(self, fn, items: List[Any]) -> List[Any]:
        return self._executor.execute_batch(items, fn)

    def parallel_run(self, fns: List) -> List[Any]:
        return self._executor.run_in_parallel(fns)

    def parallel_execute(self, fn) -> int:
        return self._executor.execute(fn)

    def shutdown_executor(self) -> None:
        self._executor.shutdown()

    def concurrent_gather(self, fns: List) -> List[Any]:
        return self._concurrent.gather(fns)

    def concurrent_run(self, fn, name: str = '') -> Any:
        task = self._concurrent.run(fn, name)
        return task.wait()

    def cancel_concurrent(self) -> None:
        self._concurrent.cancel_all()

    def close_concurrent(self) -> None:
        self._concurrent.close()

    def rate_acquire(self, key: str = 'default') -> None:
        self._rate_limiter.acquire(key)

    def rate_try_acquire(self, key: str = 'default') -> bool:
        return self._rate_limiter.try_acquire(key)

    def rate_configure(self, key: str, rate: float, capacity: int) -> None:
        self._rate_limiter.configure(key, rate, capacity)

    def rate_reset(self) -> None:
        self._rate_limiter.reset()

    def spec_execute(self, fn) -> Any:
        return self._hedged.execute(fn)

    def spec_map(self, fns: List) -> List[Any]:
        return self._hedged.map(fns)

    def sync_register(self, name: str) -> None:
        self._coordinator.register(name)

    def sync_unregister(self, name: str) -> None:
        self._coordinator.unregister(name)

    def sync_define_phases(self, phases: List[str]) -> None:
        self._coordinator.define_phases(phases)

    def sync_wait(self, phase: str) -> None:
        self._coordinator.wait(phase, type(self).__name__)

    def sync_set(self, key: str, value: Any) -> None:
        self._coordinator.set_phase_data(key, value)

    def sync_get(self, key: str) -> Optional[Any]:
        return self._coordinator.get_phase_data(key)

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
        return self.state.history.tail(count)

    def history_frequencies(self) -> Dict[str, int]:
        return self.state.history._cache.frequencies()

    def history_resize(self, new_max: int) -> int:
        return self.state.history._cache.resize(new_max)

    @staticmethod
    def _compute_checksum(data: Dict[str, Any]) -> str:
        canonical = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode('utf-8')).hexdigest()

    @staticmethod
    def _describe_value(value: Any) -> str:
        if isinstance(value, (str, bytes)):
            v = str(value)
            return repr(v[:50]) + ('...' if len(v) > 50 else '')
        if isinstance(value, (int, float, bool)):
            return str(value)
        if isinstance(value, (list, tuple)):
            return f'{type(value).__name__}[{len(value)}]'
        if isinstance(value, dict):
            return f'dict[{len(value)}]'
        if isinstance(value, set):
            return f'set[{len(value)}]'
        return type(value).__name__

    def export_state(self) -> Path:
        records_snapshot = dict(self.state.records)
        merkle_root = self._replicator.snapshot(records_snapshot)
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
                'records_snapshot': records_snapshot,
                'flags': dict(self.state.flags),
            },
            'merkle_root': merkle_root,
        }
        return self.save_json('state.json', payload)

    def verify_state(self, path: Optional[Path] = None) -> bool:
        path = path or self.output_dir / self._guard.qualify('state.json')
        data = self.load_json(path)
        stored_root = data.get('merkle_root', '')
        if not stored_root:
            return True
        metadata = data.get('metadata', {})
        records_snapshot = metadata.get('records_snapshot', {})
        return self._replicator.verify_state(records_snapshot, stored_root)

    def export_delta(self, name: str = 'state_delta.json') -> Path:
        records_export = dict(self.state.records)
        new_root, delta = self._replicator.compute_delta(records_export)
        if not delta:
            return self.save_json(name, {'merkle_root': new_root, 'delta': {}})
        payload = {
            'merkle_root': new_root,
            'delta': delta,
            'exported_at': datetime.now(timezone.utc).isoformat(),
        }
        return self.save_json(name, payload)

    def import_delta(self, path: Path) -> bool:
        data = self.load_json(path)
        if not data:
            return False
        delta = data.get('delta', {})
        expected_root = data.get('merkle_root', '')
        base_data = dict(self.state.records)
        try:
            merged = self._replicator.apply_delta(base_data, delta, expected_root)
            self.state.records = merged
            return True
        except ValueError:
            return False

    def _report_data(self) -> Dict[str, Any]:
        return {
            'runs': self.state.runs,
            'errors': self.state.errors,
            'records': len(self.state.records),
            'flags': len(self.state.flags),
            'history_entries': len(self.state.history),
        }

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

    def format_report(self) -> str:
        data = self._report_data()
        lines = [f'Runs: {data["runs"]}', f'Errors: {data["errors"]}',
                 f'Records: {data["records"]}', f'Flags: {data["flags"]}',
                 f'History entries: {data["history_entries"]}']
        return '\n'.join(lines)

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
        self._wal.begin_txn('main')
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
        with self.state._lock:
            self._wal.write_checkpoint(dict(self.state.records))
        self._wal.commit_txn('main')
        self.log('Finalized successfully')
