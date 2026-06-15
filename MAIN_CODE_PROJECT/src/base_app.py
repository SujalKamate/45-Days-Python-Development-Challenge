from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy as _deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Generator, Hashable, List, Optional, Tuple
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

from nat_traversal import NATTraversalManager

from gossip_protocol import GossipNode

from lua_sandbox import ScriptStore

from openapi_spec import OpenAPIOrchestrator

from graphql_sub import GraphQLSubscriptionEngine

from webhook_delivery import WebhookDeliveryEngine

from py_preprocessor import PreprocessorEngine

from algebraic_effects import AlgebraicEffectsEngine


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

from count_min_sketch import CountMinSketchEngine, HeavyHitter, FrequencyEstimator
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
        self._freq_est = CountMinSketchEngine()
        self._replicator = IncrementalStateReplicator()
        self._guard = ResourceGuard('BaseApp', self.output_dir)
        self._effects = AlgebraicEffectsEngine()
    main

    # ── Logging / state mutation helpers ───────────────────────────────

    def log(self, message: str) -> None:
        stamp = datetime.now().strftime('%H:%M:%S')
        entry = f'[{stamp}] {message}'
        self.state.history.append(entry)
        print(entry)

    def event_publish(self, event_type: str, message: str, data: Any = None) -> bool:
        return self._event_bus.publish(event_type, type(self).__name__, message, data)

    def event_subscribe(self, event_type: str, handler) -> None:
        self._event_bus.subscribe(event_type, handler)

    def event_dispatch(self) -> int:
        return self._event_bus.dispatch()

    def flush_events(self) -> None:
        self._event_log.flush()

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
        encrypted = self._aead.encrypt_state(payload)
        path.write_bytes(encrypted)
        return path

    def load_json(self, path: Path) -> Dict[str, Any]:
        self._guard.check_path(path)
        if not path.exists():
            return {}
        try:
            return self._aead.decrypt_state(path.read_bytes())
        except Exception:
            return {}

    def aead_export_key(self, path: str) -> None:
        self._aead.export_key(path)

    def aead_rotate_key(self, payload_path: str, new_key_path: str) -> bytes:
        new_key = AEADStore.load_key(new_key_path)
        data = Path(payload_path).read_bytes()
        return self._aead.rotate_key(data, new_key)

    @staticmethod
    def aead_load_key(path: str) -> bytes:
        return AEADStore.load_key(path)

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

    def pipe_map(self, fn, name: str = 'map') -> LazyPipeline:
        return LazyPipeline().map(fn, name)

    def pipe_filter(self, predicate, name: str = 'filter') -> LazyPipeline:
        return LazyPipeline().filter(predicate, name)

    def pipe_run(self, name: str, data: List[Any]) -> List[Any]:
        return self._pipeline.run(name, data)

    def pipe_register(self, name: str, pipeline: LazyPipeline) -> None:
        self._pipeline.register(name, pipeline)

    def pipe_transform(self, data: List[Any], transforms) -> List[Any]:
        pipeline = LazyPipeline(iter(data))
        for name, fn in transforms:
            pipeline.map(fn, name)
        return pipeline.collect()

    def ckpt_pipeline(self, run_id: str = 'default') -> CheckpointedPipeline:
        pipeline = CheckpointedPipeline(self.output_dir / '.checkpoints', run_id)
        return pipeline

    def ckpt_run(self, stages: List[Tuple[str, Callable]], initial: Any = None,
                 run_id: str = 'default') -> Any:
        pipeline = self.ckpt_pipeline(run_id)
        for name, fn in stages:
            pipeline.add_stage(name, fn)
        return pipeline.run(initial)

    def ckpt_resume(self, run_id: str = 'default') -> Optional[str]:
        store = CheckpointStore(self.output_dir / '.checkpoints')
        ckpt = store.last_checkpoint(run_id)
        return ckpt.stage_name if ckpt else None

    def ckpt_clear(self, run_id: str = 'default') -> None:
        store = CheckpointStore(self.output_dir / '.checkpoints')
        store.clear_run(run_id)

    def batch_process(self, items: List[Any], processor_fn) -> List[Any]:
        adapter = AdaptiveBatchProcessor(processor_fn)
        return adapter.process(items)

    def batch_current_size(self) -> int:
        return self._adaptive_batcher.current

    def batch_update(self, batch_size: int, elapsed: float) -> None:
        self._adaptive_batcher.update(batch_size, elapsed)

    def batch_resize(self, min_batch: int = 1, max_batch: int = 1024) -> None:
        self._adaptive_batcher.resize(min_batch, max_batch)

    def prov_entity(self, name: str = '', **attrs) -> str:
        return self._provenance.entity(name=name, **attrs)

    def prov_activity(self, name: str = '', **attrs) -> str:
        return self._provenance.activity(name=name, **attrs)

    def prov_agent(self, name: str = '', **attrs) -> str:
        return self._provenance.agent(name=name, **attrs)

    def prov_derivation(self, derived: str, source: str, activity: str = '') -> None:
        self._provenance.derivation(derived, source, activity)

    def prov_lineage(self, entity_id: str) -> List[Dict[str, Any]]:
        return self._provenance.lineage(entity_id)

    def prov_export(self, path: str) -> None:
        self._provenance.export_json(path)

    def prov_clear(self) -> None:
        self._provenance.clear()

    def secret_split(self, label: str, secret: bytes) -> List[str]:
        return self._key_manager.create(label, secret)

    def secret_recover(self, label: str, share_indices: List[int]) -> bytes:
        return self._key_manager.recover(label, share_indices)

    def secret_rotate(self, label: str, share_indices: List[int]) -> List[str]:
        return self._key_manager.rotate(label, share_indices)

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
        if self._gossip:
            self._gossip.stop()
        with self._time_it('export_state'):
            self.export_state()
        with self.state._lock:
            self._wal.write_checkpoint(dict(self.state.records))
        self._wal.commit_txn('main')
        self.log('Finalized successfully')

    # ── Count-Min Sketch frequency estimation ──────────────────────────

    def freq_create(self, name: str = 'default', epsilon: float = 0.01,
                    delta: float = 0.99, top_k: int = 20) -> FrequencyEstimator:
        return self._freq_est.create_estimator(name, epsilon, delta, top_k)

    def freq_add(self, item: Hashable, count: int = 1, name: str = 'default') -> None:
        self._freq_est.add(item, count, name)

    def freq_add_batch(self, items: List[Hashable], name: str = 'default') -> None:
        self._freq_est.add_batch(items, name)

    def freq_estimate(self, item: Hashable, name: str = 'default') -> int:
        return self._freq_est.estimate(item, name)

    def freq_estimate_confidence(self, item: Hashable, name: str = 'default') -> Dict[str, float]:
        return self._freq_est.estimate_confidence(item, name)

    def freq_top_k(self, name: str = 'default') -> List[HeavyHitter]:
        return self._freq_est.top_k(name)

    def freq_total(self, name: str = 'default') -> int:
        return self._freq_est.total(name)

    def freq_merge(self, dst: str, src: str) -> bool:
        return self._freq_est.merge(dst, src)

    def freq_inner_product(self, name_a: str, name_b: str) -> Optional[int]:
        return self._freq_est.inner_product(name_a, name_b)

    def freq_clear(self, name: str = 'default') -> None:
        self._freq_est.clear(name)

    def freq_clear_all(self) -> None:
        self._freq_est.clear_all()

    def freq_snapshot(self, name: str = 'default') -> int:
        return self._freq_est.snapshot(name)

    def freq_history(self, n: int = 10) -> List[Dict[str, Any]]:
        return self._freq_est.history(n)

    def freq_summary(self) -> Dict[str, Any]:
        return self._freq_est.summary()

    def freq_list(self) -> List[str]:
        return self._freq_est.list_estimators()

    def freq_remove(self, name: str) -> bool:
        return self._freq_est.remove_estimator(name)
    def ae_register(self, effect_type: str,
                    handler_fn: Optional[Callable[[Any], Any]] = None) -> None:
        self._effects.register_handler(effect_type, handler_fn)

    def ae_effect(self, effect_type: str, payload: Any = None) -> Any:
        return self._effects.effect(effect_type, payload)

    def ae_io(self, operation: str, path: str = '', data: Any = None) -> Any:
        return self._effects.io_effect(operation, path, data)

    def ae_timeout(self, duration_s: float, context: str = '') -> Any:
        return self._effects.timeout_effect(duration_s, context)

    def ae_validation(self, field: str, value: Any, reason: str = '') -> Any:
        return self._effects.validation_effect(field, value, reason)

    def ae_process(self, gen_fn: Callable[..., Any],
                   *args: Any, **kwargs: Any) -> Any:
        return self._effects.process(gen_fn, *args, **kwargs)

    def ae_summary(self) -> Dict[str, Any]:
        return self._effects.summary()

    def ae_report(self) -> str:
        return self._effects.report_text()

    def tls_pin_host(self, host: str, fingerprints: List[str]) -> None:
        self._pinner.pin_host(host, fingerprints)

    def bh_execute(self, group: str, fn: Callable[..., Any],
                   *args: Any, **kwargs: Any) -> Any:
        return self._bulkhead.execute(group, fn, *args, **kwargs)
    main

    def bh_io(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        return self._bulkhead.execute_io(fn, *args, **kwargs)

    def bh_cpu(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        return self._bulkhead.execute_cpu(fn, *args, **kwargs)

    def bh_network(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        return self._bulkhead.execute_network(fn, *args, **kwargs)

    def bh_create_group(self, name: str, max_conc: int = 10, queue: int = 20) -> Any:
        return self._bulkhead.create_group(name, max_conc, queue)

    def bh_metrics(self, name: str) -> Optional[Dict[str, Any]]:
        return self._bulkhead.group_metrics(name)

    def bh_summary(self) -> Dict[str, Any]:
        return self._bulkhead.summary()

    def bh_report(self) -> str:
        return self._bulkhead.report_text()

    def tls_pin_host(self, host: str, fingerprints: List[str]) -> None:
        self._pinner.pin_host(host, fingerprints)

    def dbg_register_callable(self, name: str, fn: Callable[..., Any]) -> None:
        self._debug.register_callable(name, fn)

    def dbg_trace(self, fn: Callable[..., Any], *args: Any,
                  label: str = '', **kwargs: Any) -> Dict[str, Any]:
        return self._debug.trace_execution(fn, *args, label=label, **kwargs)

    def dbg_trace_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self._debug.trace_history(limit)

    def dbg_snapshot(self, key: str) -> None:
        self._debug.snapshot_state(key, self._debug.inspector.state_snapshot(self))

    def dbg_start_repl(self) -> None:
        self._debug.register_module('base_app', self)
        self._debug.register_callable('run', self.run)
        self._debug.register_callable('dataset', self.dataset)
        self._debug.register_callable('process_dataset', self.process_dataset)
        self._debug.start_repl()

    def dbg_summary(self) -> Dict[str, Any]:
        return self._debug.summary()

    def dbg_report(self) -> str:
        return self._debug.report_text()
