"""Hardware performance counter telemetry for low-level runtime observability."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple
import collections
import datetime
import json
import math
import os
import platform
import struct
import threading
import time


_EVENT_BUFFER_SIZE = 10000
_CACHE_LINE_SIZE = 64


def _estimate_clock_speed_mhz() -> float:
    t0 = time.perf_counter()
    t1 = time.perf_counter()
    elapsed = t1 - t0
    if elapsed > 0:
        return round(1.0 / elapsed / 1e6, 1)
    return 0.0


class SoftwarePMUEstimator:
    """Estimates hardware-level metrics using software probes."""

    @staticmethod
    def estimate_cache_miss_rate(iterations: int = 10000) -> float:
        data = [0] * (1024 * 1024)
        misses = 0
        stride = _CACHE_LINE_SIZE // 4
        for i in range(0, min(len(data), iterations), stride):
            t0 = time.perf_counter_ns()
            _ = data[i]
            t1 = time.perf_counter_ns()
            if (t1 - t0) > 100:
                misses += 1
        return misses / max(iterations // stride, 1)

    @staticmethod
    def estimate_ipc() -> float:
        import sys
        ops = 100000
        t0 = time.perf_counter_ns()
        total = 0
        for i in range(ops):
            total += i * i - i
        t1 = time.perf_counter_ns()
        elapsed_ns = t1 - t0
        if elapsed_ns <= 0:
            return 0.0
        return ops / elapsed_ns * 1e9 / 1e9

    @staticmethod
    def estimate_branch_mispredict_rate(iterations: int = 100000) -> float:
        import random as _r
        _r.seed(0)
        data = [_r.randint(0, 1) for _ in range(1024)]
        correct = 0
        total_check = 0
        t0 = time.perf_counter_ns()
        for i in range(iterations):
            idx = i % len(data)
            predicted = 1 if i % 2 == 0 else 0
            actual = data[idx]
            if predicted == actual:
                correct += 1
            total_check += 1
        t1 = time.perf_counter_ns()
        return 1.0 - (correct / max(total_check, 1))

    @staticmethod
    def estimate_tlb_miss_rate(iterations: int = 5000) -> float:
        size = 2 * 1024 * 1024
        data = bytearray(size)
        misses = 0
        page_size = 4096
        for i in range(0, min(size, iterations * page_size), page_size):
            t0 = time.perf_counter_ns()
            _ = data[i]
            t1 = time.perf_counter_ns()
            if (t1 - t0) > 200:
                misses += 1
        return misses / max(iterations, 1)


class HWPerfCounter:
    """A single hardware performance counter with metadata."""

    def __init__(self, name: str, value: float, unit: str, category: str = '') -> None:
        self.name = name
        self.value = value
        self.unit = unit
        self.category = category
        self.timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'value': self.value,
            'unit': self.unit,
            'category': self.category,
            'timestamp': self.timestamp,
        }


class HWPerfCollector:
    """Collects a snapshot of hardware performance counters."""

    def __init__(self) -> None:
        self._estimator = SoftwarePMUEstimator()

    def collect(self) -> Dict[str, HWPerfCounter]:
        counters: Dict[str, HWPerfCounter] = {}

        cmr = self._estimator.estimate_cache_miss_rate()
        counters['cache_miss_rate'] = HWPerfCounter('cache_miss_rate', round(cmr, 4), 'ratio', 'memory')

        ipc = self._estimator.estimate_ipc()
        counters['estimated_ipc'] = HWPerfCounter('estimated_ipc', round(ipc, 4), 'insns/cycle', 'pipeline')

        bmr = self._estimator.estimate_branch_mispredict_rate()
        counters['branch_mispredict_rate'] = HWPerfCounter('branch_mispredict_rate', round(bmr, 4), 'ratio', 'pipeline')

        tlb = self._estimator.estimate_tlb_miss_rate()
        counters['tlb_miss_rate'] = HWPerfCounter('tlb_miss_rate', round(tlb, 4), 'ratio', 'memory')

        speed = _estimate_clock_speed_mhz()
        counters['clock_speed_mhz'] = HWPerfCounter('clock_speed_mhz', speed, 'MHz', 'cpu')

        import sys
        counters['thread_count'] = HWPerfCounter('thread_count', threading.active_count(), 'count', 'system')
        counters['cpu_count'] = HWPerfCounter('cpu_count', os.cpu_count() or 0, 'count', 'system')

        return counters

    def collect_dict(self) -> Dict[str, float]:
        return {k: v.value for k, v in self.collect().items()}


class HWPerfTelemetryEvent:
    """A structured telemetry event with HW counter data."""

    def __init__(self, module: str, counters: Dict[str, float], metadata: Optional[Dict[str, Any]] = None) -> None:
        self.module = module
        self.counters = counters
        self.metadata = metadata or {}
        self.timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            'module': self.module,
            'counters': self.counters,
            'metadata': self.metadata,
            'timestamp': self.timestamp,
        }


class TelemetryBuffer:
    """Bounded buffer for telemetry events."""

    def __init__(self, max_size: int = _EVENT_BUFFER_SIZE) -> None:
        self._events: List[HWPerfTelemetryEvent] = []
        self._max = max_size
        self._lock = threading.Lock()

    def append(self, event: HWPerfTelemetryEvent) -> None:
        with self._lock:
            self._events.append(event)
            if len(self._events) > self._max:
                self._events.pop(0)

    def extend(self, events: List[HWPerfTelemetryEvent]) -> None:
        with self._lock:
            self._events.extend(events)
            while len(self._events) > self._max:
                self._events.pop(0)

    def get_all(self) -> List[HWPerfTelemetryEvent]:
        with self._lock:
            return list(self._events)

    def clear(self) -> None:
        with self._lock:
            self._events.clear()

    @property
    def count(self) -> int:
        with self._lock:
            return len(self._events)


class TrendDetector:
    """Detects performance degradation trends in counter data."""

    def __init__(self, window: int = 10) -> None:
        self._history: Dict[str, List[float]] = {}
        self._window = window
        self._lock = threading.Lock()

    def record(self, counters: Dict[str, float]) -> None:
        with self._lock:
            for k, v in counters.items():
                if k not in self._history:
                    self._history[k] = []
                self._history[k].append(v)
                if len(self._history[k]) > self._window:
                    self._history[k].pop(0)

    def trend(self, counter_name: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            values = self._history.get(counter_name)
            if not values or len(values) < 3:
                return None
            first = values[0]
            last = values[-1]
            slope = (last - first) / max(len(values) - 1, 1)
            direction = 'improving' if slope < 0 else 'degrading'
            pct_change = ((last - first) / abs(first) * 100) if first != 0 else 0.0
            return {
                'counter': counter_name,
                'first': round(first, 4),
                'last': round(last, 4),
                'slope': round(slope, 6),
                'direction': direction,
                'pct_change': round(pct_change, 2),
            }

    def all_trends(self) -> Dict[str, Any]:
        with self._lock:
            return {k: self.trend(k) for k in self._history}

    def degradation_warnings(self, threshold_pct: float = 10.0) -> List[Dict[str, Any]]:
        warnings = []
        for k in list(self._history.keys()):
            t = self.trend(k)
            if t and t['direction'] == 'degrading' and abs(t['pct_change']) > threshold_pct:
                warnings.append(t)
        return warnings


class HWPerfTelemetryEngine:
    """Top-level telemetry engine collecting HW counters and exporting events."""

    def __init__(self) -> None:
        self._collector = HWPerfCollector()
        self._buffer = TelemetryBuffer()
        self._trends = TrendDetector()
        self._module_mapping: Dict[str, str] = {}

    def map_module(self, module_name: str, tag: str) -> None:
        self._module_mapping[module_name] = tag

    def snapshot(self, module: str = 'application', metadata: Optional[Dict[str, Any]] = None) -> HWPerfTelemetryEvent:
        counters = self._collector.collect_dict()
        self._trends.record(counters)
        event = HWPerfTelemetryEvent(module, counters, metadata)
        self._buffer.append(event)
        return event

    def event_stream(self, module: str = 'application', count: int = 1) -> List[HWPerfTelemetryEvent]:
        events = []
        for _ in range(count):
            events.append(self.snapshot(module))
        return events

    def latest(self) -> Optional[HWPerfTelemetryEvent]:
        all_events = self._buffer.get_all()
        return all_events[-1] if all_events else None

    def history(self) -> List[HWPerfTelemetryEvent]:
        return self._buffer.get_all()

    def trends(self) -> Dict[str, Any]:
        return self._trends.all_trends()

    def degradation_warnings(self, threshold_pct: float = 10.0) -> List[Dict[str, Any]]:
        return self._trends.degradation_warnings(threshold_pct)

    def report_text(self) -> str:
        latest = self.latest()
        lines = [
            'Hardware Performance Counter Telemetry',
        ]
        if latest:
            lines.append(f'  Module: {latest.module}')
            lines.append(f'  Timestamp: {latest.timestamp}')
            lines.append('')
            lines.append('  Counters:')
            for name, value in sorted(latest.counters.items()):
                lines.append(f'    {name:30s} {value}')
        warnings = self.degradation_warnings()
        if warnings:
            lines.append('')
            lines.append('  Degradation Warnings:')
            for w in warnings:
                lines.append(f'    {w["counter"]}: {w["direction"]} ({w["pct_change"]}%)')
        return '\n'.join(lines)

    def export_event_log(self, path: str) -> None:
        events = self._buffer.get_all()
        payload = {
            'export_time': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'event_count': len(events),
            'events': [e.to_dict() for e in events],
            'trends': self.trends(),
            'degradation_warnings': self.degradation_warnings(),
        }
        with open(path, 'w') as f:
            json.dump(payload, f, indent=2, default=str)

    def export_artifacts(self, dir: str) -> List[str]:
        os.makedirs(dir, exist_ok=True)
        paths = []
        ep = os.path.join(dir, 'hw_perf_telemetry.json')
        self.export_event_log(ep)
        paths.append(ep)
        return paths
