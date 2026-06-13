"""Cache-aware data layout optimization for high-frequency processing workloads."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Set, Tuple, TypeVar
import collections
import datetime
import json
import math
import os
import random
import sys
import threading
import time


_CACHE_LINE_SIZE = 64
_PAGE_SIZE = 4096


class AccessPatternTracker:
    """Tracks field-level access frequency and temporal locality."""

    def __init__(self) -> None:
        self._field_accesses: Dict[str, int] = {}
        self._co_access: Dict[str, Dict[str, int]] = {}
        self._access_order: List[str] = []
        self._lock = threading.Lock()
        self._max_order = 10000

    def record_access(self, field: str) -> None:
        with self._lock:
            self._field_accesses[field] = self._field_accesses.get(field, 0) + 1
            self._access_order.append(field)
            if len(self._access_order) > self._max_order:
                self._access_order = self._access_order[-self._max_order // 2:]

    def record_co_access(self, fields: List[str]) -> None:
        with self._lock:
            for i, a in enumerate(fields):
                for b in fields[i + 1:]:
                    if a not in self._co_access:
                        self._co_access[a] = {}
                    self._co_access[a][b] = self._co_access[a].get(b, 0) + 1
                    if b not in self._co_access:
                        self._co_access[b] = {}
                    self._co_access[b][a] = self._co_access[b].get(a, 0) + 1

    def hot_fields(self, top_n: int = 10) -> List[Tuple[str, int]]:
        with self._lock:
            sorted_fields = sorted(self._field_accesses.items(), key=lambda x: -x[1])
            return sorted_fields[:top_n]

    def access_frequency(self, field: str) -> int:
        with self._lock:
            return self._field_accesses.get(field, 0)

    def co_access_score(self, field_a: str, field_b: str) -> int:
        with self._lock:
            return self._co_access.get(field_a, {}).get(field_b, 0)

    def temporal_locality_score(self) -> float:
        with self._lock:
            if len(self._access_order) < 10:
                return 0.0
            recent = set(self._access_order[-50:])
            total = len(self._access_order[-50:])
            unique = len(recent)
            return 1.0 - (unique / max(total, 1))

    def reset(self) -> None:
        with self._lock:
            self._field_accesses.clear()
            self._co_access.clear()
            self._access_order.clear()


class FieldReorganizer:
    """Recommends field reordering for cache-friendly data layout."""

    def __init__(self, tracker: AccessPatternTracker) -> None:
        self._tracker = tracker

    def recommended_layout(self, all_fields: List[str]) -> List[str]:
        hot = {f for f, _ in self._tracker.hot_fields(len(all_fields))}
        hot_list = [f for f in all_fields if f in hot]
        cold_list = [f for f in all_fields if f not in hot]

        ranked = self._rank_by_co_access(hot_list)
        return ranked + cold_list

    def _rank_by_co_access(self, fields: List[str]) -> List[str]:
        if not fields:
            return []
        field_set = set(fields)
        clusters: List[set] = []
        for f in fields:
            best_cluster = None
            best_score = 0
            for c in clusters:
                score = sum(self._tracker.co_access_score(f, g) for g in c if g in field_set)
                if score > best_score:
                    best_score = score
                    best_cluster = c
            if best_cluster is not None and best_score > 0:
                best_cluster.add(f)
            else:
                clusters.append({f})
        result = []
        for c in sorted(clusters, key=lambda x: -sum(self._tracker.access_frequency(f) for f in x)):
            for f in sorted(c, key=lambda f: -self._tracker.access_frequency(f)):
                result.append(f)
        return result

    def estimate_cache_lines(self, fields: List[str], field_sizes: Dict[str, int], current: bool = True) -> int:
        if current:
            layout = fields
        else:
            layout = self.recommended_layout(fields)
        lines = 1
        accum = 0
        for f in layout:
            size = field_sizes.get(f, 8)
            if accum + size > _CACHE_LINE_SIZE:
                lines += 1
                accum = size
            else:
                accum += size
        return lines

    def savings_estimate(self, fields: List[str], field_sizes: Dict[str, int]) -> Dict[str, Any]:
        current_lines = self.estimate_cache_lines(fields, field_sizes, current=True)
        optimized_lines = self.estimate_cache_lines(fields, field_sizes, current=False)
        return {
            'current_cache_lines': current_lines,
            'optimized_cache_lines': optimized_lines,
            'reduction': current_lines - optimized_lines,
            'reduction_pct': round((1 - optimized_lines / max(current_lines, 1)) * 100, 1),
        }


class StructOfArrays:
    """SoA layout — fields stored in parallel arrays for cache-friendly iteration."""

    def __init__(self, fields: Dict[str, type]) -> None:
        self._fields = fields
        self._data: Dict[str, list] = {k: [] for k in fields}

    def append(self, values: Dict[str, Any]) -> None:
        for k in self._fields:
            self._data[k].append(values.get(k))

    def __len__(self) -> int:
        for v in self._data.values():
            return len(v)
        return 0

    def get_column(self, field: str) -> list:
        return self._data.get(field, [])

    def get_row(self, idx: int) -> Dict[str, Any]:
        return {k: v[idx] if idx < len(v) else None for k, v in self._data.items()}

    def to_dict(self) -> Dict[str, list]:
        return dict(self._data)

    @staticmethod
    def from_dict(data: Dict[str, list]) -> StructOfArrays:
        fields = {k: type(v[0]) if v else object for k, v in data.items()}
        soa = StructOfArrays(fields)
        soa._data = {k: list(v) for k, v in data.items()}
        return soa


class ArrayOfStructures:
    """AoS layout — list of dicts for object-at-a-time access."""

    def __init__(self) -> None:
        self._data: List[Dict[str, Any]] = []

    def append(self, record: Dict[str, Any]) -> None:
        self._data.append(dict(record))

    def __len__(self) -> int:
        return len(self._data)

    def get(self, idx: int) -> Dict[str, Any]:
        return dict(self._data[idx])

    def to_list(self) -> List[Dict[str, Any]]:
        return list(self._data)

    @staticmethod
    def from_list(data: List[Dict[str, Any]]) -> ArrayOfStructures:
        aos = ArrayOfStructures()
        aos._data = [dict(r) for r in data]
        return aos


class LayoutConverter:
    """Converts between AoS and SoA layouts."""

    @staticmethod
    def aos_to_soa(aos: ArrayOfStructures) -> StructOfArrays:
        if len(aos) == 0:
            return StructOfArrays({})
        first = aos.get(0)
        fields = {k: type(v) for k, v in first.items()}
        soa = StructOfArrays(fields)
        for i in range(len(aos)):
            soa.append(aos.get(i))
        return soa

    @staticmethod
    def soa_to_aos(soa: StructOfArrays) -> ArrayOfStructures:
        aos = ArrayOfStructures()
        n = len(soa)
        for i in range(n):
            aos.append(soa.get_row(i))
        return aos


class HotColdSplitter:
    """Splits data into hot and cold regions for cache-efficient storage."""

    def __init__(self, tracker: AccessPatternTracker) -> None:
        self._tracker = tracker

    def split_fields(self, all_fields: List[str], threshold_pct: float = 20.0) -> Dict[str, List[str]]:
        total = sum(self._tracker.access_frequency(f) for f in all_fields) or 1
        hot: List[str] = []
        cold: List[str] = []
        for f in all_fields:
            pct = self._tracker.access_frequency(f) / total * 100
            if pct >= threshold_pct:
                hot.append(f)
            else:
                cold.append(f)
        hot.sort(key=lambda f: -self._tracker.access_frequency(f))
        return {'hot': hot, 'cold': cold}

    def split_record(self, record: Dict[str, Any], threshold_pct: float = 20.0) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        fields = list(record.keys())
        parts = self.split_fields(fields, threshold_pct)
        hot_rec = {k: record[k] for k in parts['hot'] if k in record}
        cold_rec = {k: record[k] for k in parts['cold'] if k in record}
        return hot_rec, cold_rec


class PrefetchScheduler:
    """Schedules prefetch hints for anticipated field accesses."""

    def __init__(self, tracker: AccessPatternTracker) -> None:
        self._tracker = tracker

    def predict_next_accesses(self, current_field: str, n: int = 3) -> List[str]:
        co_scores = []
        with self._tracker._lock:
            related = self._tracker._co_access.get(current_field, {})
        for field, score in related.items():
            co_scores.append((field, score))
        co_scores.sort(key=lambda x: -x[1])
        return [f for f, _ in co_scores[:n]]

    def prefetch_plan(self, hot_fields: List[str]) -> Dict[str, List[str]]:
        plan = {}
        for f in hot_fields:
            plan[f] = self.predict_next_accesses(f)
        return plan


class CacheOptimizationAdvisor:
    """High-level advisor: tracks access, analyzes layout, recommends optimizations."""

    def __init__(self) -> None:
        self._tracker = AccessPatternTracker()
        self._reorganizer = FieldReorganizer(self._tracker)
        self._splitter = HotColdSplitter(self._tracker)
        self._prefetcher = PrefetchScheduler(self._tracker)

    def record(self, fields: List[str]) -> None:
        for f in fields:
            self._tracker.record_access(f)
        self._tracker.record_co_access(fields)

    @property
    def tracker(self) -> AccessPatternTracker:
        return self._tracker

    def analyze(self, all_fields: List[str], field_sizes: Optional[Dict[str, int]] = None) -> Dict[str, Any]:
        sizes = field_sizes or {f: 8 for f in all_fields}
        hot = self._tracker.hot_fields(10)
        layout = self._reorganizer.recommended_layout(all_fields)
        savings = self._reorganizer.savings_estimate(all_fields, sizes)
        hot_cold = self._splitter.split_fields(all_fields)
        temporal = self._tracker.temporal_locality_score()

        return {
            'hot_fields': [(f, c) for f, c in hot],
            'recommended_layout': layout,
            'cache_savings': savings,
            'hot_cold_split': hot_cold,
            'temporal_locality_score': round(temporal, 3),
            'cache_line_size': _CACHE_LINE_SIZE,
        }

    def report_text(self, all_fields: List[str], field_sizes: Optional[Dict[str, int]] = None) -> str:
        a = self.analyze(all_fields, field_sizes)
        lines = [
            'Cache Optimization Report',
            f'  Cache line size: {a["cache_line_size"]} bytes',
            f'  Temporal locality score: {a["temporal_locality_score"]}',
            '',
            '  Hot fields (top 10):',
        ]
        for name, count in a['hot_fields'][:10]:
            lines.append(f'    {name:20s} {count} accesses')
        lines.append('')
        lines.append(f'  Cache line savings: {a["cache_savings"]["reduction"]} lines '
                     f'({a["cache_savings"]["reduction_pct"]}%)')
        lines.append('')
        lines.append('  Recommended field layout:')
        for i, f in enumerate(a['recommended_layout']):
            lines.append(f'    [{i:3d}] {f}')
        lines.append('')
        lines.append('  Hot/cold split:')
        lines.append(f'    Hot:  {a["hot_cold_split"]["hot"]}')
        lines.append(f'    Cold: {a["hot_cold_split"]["cold"]}')
        return '\n'.join(lines)


class CacheOptimizationOrchestrator:
    """Manages cache optimization analysis across multiple data structures."""

    def __init__(self) -> None:
        self._advisors: Dict[str, CacheOptimizationAdvisor] = {}
        self._lock = threading.Lock()

    def register(self, name: str) -> CacheOptimizationAdvisor:
        advisor = CacheOptimizationAdvisor()
        with self._lock:
            self._advisors[name] = advisor
        return advisor

    def analyze_all(self) -> Dict[str, Any]:
        with self._lock:
            return {n: a.analyze([]) for n, a in self._advisors.items()}

    def export_artifacts(self, dir: str) -> List[str]:
        os.makedirs(dir, exist_ok=True)
        paths = []
        for name, advisor in self._advisors.items():
            rp = os.path.join(dir, f'{name}_cache_report.json')
            with open(rp, 'w') as f:
                json.dump(advisor.analyze([]), f, indent=2, default=str)
            paths.append(rp)
        return paths
