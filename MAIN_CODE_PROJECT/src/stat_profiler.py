"""Statistical profiling and flame graph visualization for runtime performance analysis."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Set, Tuple
import datetime
import json
import os
import sys
import threading
import time
import traceback


class StackSampler:
    """Periodically samples stack traces of a target thread."""

    def __init__(self, interval_s: float = 0.001) -> None:
        self._interval = interval_s
        self._samples: List[str] = []
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._target_tid: Optional[int] = None

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._target_tid = threading.get_ident()
        self._thread = threading.Thread(target=self._sample_loop, daemon=True)
        self._thread.start()

    def stop(self) -> List[str]:
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        return self._samples

    def _sample_loop(self) -> None:
        import sys as _sys
        while self._running:
            try:
                frames = []
                f = _sys._current_frames().get(self._target_tid or 0, None)
                while f:
                    name = f.f_code.co_name
                    filename = f.f_code.co_filename
                    lineno = f.f_lineno
                    frames.append(f'{filename}:{lineno}:{name}')
                    f = f.f_back
                if frames:
                    self._samples.append(';'.join(reversed(frames)))
            except Exception:
                pass
            time.sleep(self._interval)

    @property
    def sample_count(self) -> int:
        return len(self._samples)

    def clear(self) -> None:
        self._samples.clear()


class FoldedStackCollector:
    """Collects and aggregates folded stack traces for flame graph generation."""

    def __init__(self) -> None:
        self._stacks: Dict[str, int] = {}
        self._lock = threading.Lock()

    def add(self, folded: str) -> None:
        with self._lock:
            self._stacks[folded] = self._stacks.get(folded, 0) + 1

    def add_samples(self, samples: List[str]) -> None:
        for s in samples:
            self.add(s)

    def folded_data(self) -> Dict[str, int]:
        with self._lock:
            return dict(self._stacks)

    def total_samples(self) -> int:
        with self._lock:
            return sum(self._stacks.values())

    def clear(self) -> None:
        with self._lock:
            self._stacks.clear()


class FlameGraphBuilder:
    """Builds flame graph SVG from folded stack data."""

    def __init__(self, folded: Dict[str, int]) -> None:
        self._folded = folded
        self._total = sum(folded.values())

    def build_svg(self, title: str = 'Flame Graph') -> str:
        lines = [
            '<?xml version="1.0" standalone="no"?>',
            '<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd">',
            f'<svg version="1.1" width="1200" height="{max(400, self._svg_height())}" xmlns="http://www.w3.org/2000/svg">',
            f'<rect width="100%" height="100%" fill="#1e1e1e"/>',
            f'<text x="10" y="20" font-family="monospace" font-size="14" fill="#fff">{title} — {self._total} samples</text>',
        ]
        frame_h = 16
        x_scale = 1200.0 / max(self._total, 1)
        y_offset = 30

        parsed = [(stack, count) for stack, count in self._folded.items()]
        parsed.sort(key=lambda x: -x[1])

        for stack, count in parsed:
            frames = stack.split(';')
            w = max(count * x_scale, 1)
            for i, frame in enumerate(frames):
                short = frame.split(':')[-1] if ':' in frame else frame
                color = self._color_for(frame, i)
                lines.append(
                    f'<rect x="{0}" y="{y_offset}" width="{w}" height="{frame_h}" '
                    f'fill="{color}" rx="1" ry="1"/>'
                )
                if w > 40:
                    lines.append(
                        f'<text x="{3}" y="{y_offset + 12}" font-family="monospace" '
                        f'font-size="10" fill="#fff">{short}</text>'
                    )
                y_offset += frame_h + 1

        lines.append('</svg>')
        return '\n'.join(lines)

    def _svg_height(self) -> int:
        depth = max((s.count(';') + 1) for s in self._folded) if self._folded else 1
        return 30 + depth * 36 + 50

    def _color_for(self, frame: str, depth: int) -> str:
        import hashlib
        h = hashlib.md5(frame.encode()).hexdigest()[:6]
        r = int(h[:2], 16)
        g = int(h[2:4], 16)
        b = int(h[4:6], 16)
        dark = f'rgb({r // 2 + 80},{g // 2 + 80},{b // 2 + 80})'
        return dark


class ProfileReport:
    """Aggregate profiling data and produce reports."""

    def __init__(self, collector: FoldedStackCollector) -> None:
        self._collector = collector

    def top_frames(self, n: int = 20) -> List[Tuple[str, int, float]]:
        data = self._collector.folded_data()
        total = max(self._collector.total_samples(), 1)
        frame_totals: Dict[str, int] = {}
        for stack, count in data.items():
            for frame in stack.split(';'):
                short = frame.split(':')[-1] if ':' in frame else frame
                frame_totals[short] = frame_totals.get(short, 0) + count
        sorted_frames = sorted(frame_totals.items(), key=lambda x: -x[1])[:n]
        return [(name, cnt, round(cnt / total * 100, 1)) for name, cnt in sorted_frames]

    def summary(self) -> Dict[str, Any]:
        data = self._collector.folded_data()
        total = self._collector.total_samples()
        unique_stacks = len(data)
        return {
            'total_samples': total,
            'unique_stacks': unique_stacks,
            'sampling_duration_s': 0,
            'top_frames': [(n, p) for n, c, p in self.top_frames(10)],
        }

    def text_report(self) -> str:
        s = self.summary()
        lines = [
            'Statistical Profiling Report',
            f'  Total samples: {s["total_samples"]}',
            f'  Unique stack traces: {s["unique_stacks"]}',
            '',
            '  Top frames by sample count:',
        ]
        for name, pct in s.get('top_frames', []):
            bar = '█' * int(pct / 5)
            lines.append(f'    {name:30s} {pct:5.1f}% {bar}')
        return '\n'.join(lines)


class ProfileComparison:
    """Compares two profiling runs to detect performance changes."""

    def __init__(self, baseline: FoldedStackCollector, target: FoldedStackCollector) -> None:
        self._base = baseline
        self._target = target

    def compare(self) -> Dict[str, Any]:
        base_data = self._base.folded_data()
        target_data = self._target.folded_data()
        all_frames: Set[str] = set()
        for stack in base_data:
            for f in stack.split(';'):
                all_frames.add(f)
        for stack in target_data:
            for f in stack.split(';'):
                all_frames.add(f)

        base_total = max(self._base.total_samples(), 1)
        target_total = max(self._target.total_samples(), 1)
        deltas: List[Dict[str, Any]] = []

        for frame in sorted(all_frames):
            base_count = sum(c for s, c in base_data.items() if frame in s)
            target_count = sum(c for s, c in target_data.items() if frame in s)
            base_pct = base_count / base_total * 100
            target_pct = target_count / target_total * 100
            delta = target_pct - base_pct
            if abs(delta) > 1.0:
                deltas.append({
                    'frame': frame.split(':')[-1] if ':' in frame else frame,
                    'baseline_pct': round(base_pct, 1),
                    'target_pct': round(target_pct, 1),
                    'delta_pct': round(delta, 1),
                })

        deltas.sort(key=lambda x: -abs(x['delta_pct']))
        return {
            'baseline_samples': self._base.total_samples(),
            'target_samples': self._target.total_samples(),
            'deltas': deltas[:30],
        }


class StatisticalProfiler:
    """Top-level statistical profiler with flame graph generation."""

    def __init__(self, interval_s: float = 0.001) -> None:
        self._sampler = StackSampler(interval_s)
        self._collector = FoldedStackCollector()
        self._start_time: Optional[float] = None
        self._end_time: Optional[float] = None

    def start(self) -> None:
        self._start_time = time.time()
        self._sampler.start()

    def stop(self) -> FoldedStackCollector:
        samples = self._sampler.stop()
        self._end_time = time.time()
        self._collector.add_samples(samples)
        return self._collector

    @property
    def running(self) -> bool:
        return self._sampler._running

    @property
    def duration_s(self) -> float:
        if self._start_time and self._end_time:
            return self._end_time - self._start_time
        return 0.0

    def profile(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        self.start()
        try:
            result = fn(*args, **kwargs)
        finally:
            self.stop()
        return result

    def profile_context(self) -> '_ProfileContext':
        return _ProfileContext(self)

    def generate_flame_graph(self, title: str = 'Flame Graph') -> str:
        data = self._collector.folded_data()
        builder = FlameGraphBuilder(data)
        return builder.build_svg(title)

    def save_flame_graph(self, path: str, title: str = 'Flame Graph') -> None:
        svg = self.generate_flame_graph(title)
        with open(path, 'w') as f:
            f.write(svg)

    def report(self) -> ProfileReport:
        return ProfileReport(self._collector)

    def compare_to(self, other: StatisticalProfiler) -> Dict[str, Any]:
        comparison = ProfileComparison(self._collector, other._collector)
        return comparison.compare()


class _ProfileContext:
    """Context manager for profiling."""

    def __init__(self, profiler: StatisticalProfiler) -> None:
        self._profiler = profiler

    def __enter__(self) -> StatisticalProfiler:
        self._profiler.start()
        return self._profiler

    def __exit__(self, *args: Any) -> None:
        self._profiler.stop()


class ProfilingOrchestrator:
    """Orchestrates profiling runs with comparison and artifact export."""

    def __init__(self) -> None:
        self._runs: List[Tuple[str, StatisticalProfiler]] = []
        self._lock = threading.Lock()

    def create_run(self, name: str, interval_s: float = 0.001) -> StatisticalProfiler:
        profiler = StatisticalProfiler(interval_s)
        with self._lock:
            self._runs.append((name, profiler))
        return profiler

    def run_names(self) -> List[str]:
        return [n for n, _ in self._runs]

    def get_run(self, name: str) -> Optional[StatisticalProfiler]:
        for n, p in self._runs:
            if n == name:
                return p
        return None

    def compare_runs(self, name_a: str, name_b: str) -> Dict[str, Any]:
        a = self.get_run(name_a)
        b = self.get_run(name_b)
        if a is None or b is None:
            return {'error': 'run not found'}
        comparison = ProfileComparison(a._collector, b._collector)
        return comparison.compare()

    def export_artifacts(self, dir: str) -> List[str]:
        os.makedirs(dir, exist_ok=True)
        paths = []
        for name, profiler in self._runs:
            svg_path = os.path.join(dir, f'{name}_flame.svg')
            profiler.save_flame_graph(svg_path, name)
            paths.append(svg_path)
            data_path = os.path.join(dir, f'{name}_folded.json')
            data = profiler._collector.folded_data()
            with open(data_path, 'w') as f:
                json.dump(data, f, indent=2)
            paths.append(data_path)
        if len(self._runs) >= 2:
            comp = self.compare_runs(self._runs[0][0], self._runs[-1][0])
            cp = os.path.join(dir, 'comparison.json')
            with open(cp, 'w') as f:
                json.dump(comp, f, indent=2)
            paths.append(cp)
        return paths
