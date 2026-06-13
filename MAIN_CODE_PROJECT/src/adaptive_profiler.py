"""Adaptive profiling with dynamic sampling rates based on execution phase characteristics."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple
import datetime
import json
import math
import os
import sys
import threading
import time


_MIN_INTERVAL_S = 0.0005
_MAX_INTERVAL_S = 0.05
_ADAPT_WINDOW = 10
_CPU_BURST_THRESHOLD = 0.3
_PHASE_HISTORY = 5


class WorkloadDetector:
    """Detects execution phases by measuring CPU intensity and transition rates."""

    def __init__(self) -> None:
        self._samples: List[float] = []
        self._lock = threading.Lock()
        self._phase: str = 'idle'
        self._phase_changes: int = 0

    def record_sample(self, elapsed_s: float) -> None:
        with self._lock:
            self._samples.append(elapsed_s)
            if len(self._samples) > _ADAPT_WINDOW:
                self._samples.pop(0)

    @property
    def cpu_intensity(self) -> float:
        with self._lock:
            if len(self._samples) < 2:
                return 0.0
            recent = self._samples[-min(len(self._samples), 5):]
            return 1.0 - (min(recent) / max(recent)) if max(recent) > 0 else 0.0

    @property
    def stability(self) -> float:
        with self._lock:
            if len(self._samples) < 3:
                return 1.0
            recent = self._samples[-5:]
            mean = sum(recent) / len(recent)
            variance = sum((x - mean) ** 2 for x in recent) / len(recent)
            return 1.0 / (1.0 + math.sqrt(variance))

    @property
    def phase(self) -> str:
        intensity = self.cpu_intensity
        if intensity > 0.7:
            return 'cpu_intensive'
        if intensity > 0.3:
            return 'moderate'
        return 'idle'

    @property
    def phase_transition_rate(self) -> float:
        with self._lock:
            if len(self._samples) < _PHASE_HISTORY * 2:
                return 0.0
            mid = len(self._samples) // 2
            before = self._samples[:mid]
            after = self._samples[mid:]
            if not before or not after:
                return 0.0
            b_mean = sum(before) / len(before)
            a_mean = sum(after) / len(after)
            return abs(a_mean - b_mean) / max(b_mean, 1e-9)


class AdaptiveRateController:
    """Adjusts sampling interval based on workload characteristics."""

    def __init__(self, min_interval: float = _MIN_INTERVAL_S, max_interval: float = _MAX_INTERVAL_S) -> None:
        self._min = min_interval
        self._max = max_interval
        self._current_interval = max_interval
        self._detector = WorkloadDetector()

    def update(self, elapsed_s: float) -> float:
        self._detector.record_sample(elapsed_s)
        intensity = self._detector.cpu_intensity
        stability = self._detector.stability
        transition = self._detector.phase_transition_rate

        target = self._max - (self._max - self._min) * intensity
        if intensity > _CPU_BURST_THRESHOLD:
            target *= (1.0 - transition * 0.5)
        if stability < 0.3:
            target = target * 0.8
        target = max(self._min, min(self._max, target))
        self._current_interval = target
        return self._current_interval

    @property
    def current_interval(self) -> float:
        return self._current_interval

    @property
    def phase(self) -> str:
        return self._detector.phase

    @property
    def intensity(self) -> float:
        return self._detector.cpu_intensity

    def summary(self) -> Dict[str, Any]:
        return {
            'interval_s': round(self._current_interval, 6),
            'phase': self.phase,
            'cpu_intensity': round(self.intensity, 3),
            'stability': round(self._detector.stability, 3),
        }


class AdaptiveStackSampler:
    """Samples stack traces at dynamically adjusted rates."""

    def __init__(self, min_interval: float = _MIN_INTERVAL_S, max_interval: float = _MAX_INTERVAL_S) -> None:
        self._controller = AdaptiveRateController(min_interval, max_interval)
        self._samples: List[Tuple[str, float]] = []
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._target_tid: Optional[int] = None
        self._interval_history: List[float] = []
        self._lock = threading.Lock()

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._target_tid = threading.get_ident()
        self._thread = threading.Thread(target=self._sample_loop, daemon=True)
        self._thread.start()

    def stop(self) -> List[Tuple[str, float]]:
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        with self._lock:
            return list(self._samples)

    def _sample_loop(self) -> None:
        while self._running:
            t0 = time.perf_counter()
            try:
                frames = []
                f = sys._current_frames().get(self._target_tid or 0, None)
                while f:
                    name = f.f_code.co_name
                    filename = f.f_code.co_filename
                    lineno = f.f_lineno
                    frames.append(f'{filename}:{lineno}:{name}')
                    f = f.f_back
                if frames:
                    stack = ';'.join(reversed(frames))
                    with self._lock:
                        self._samples.append((stack, self._controller.current_interval))
            except Exception:
                pass
            elapsed = time.perf_counter() - t0
            interval = self._controller.update(elapsed)
            with self._lock:
                self._interval_history.append(interval)
            sleep_s = max(0, interval - elapsed)
            time.sleep(sleep_s)

    @property
    def sample_count(self) -> int:
        with self._lock:
            return len(self._samples)

    @property
    def controller(self) -> AdaptiveRateController:
        return self._controller

    def clear(self) -> None:
        with self._lock:
            self._samples.clear()
            self._interval_history.clear()


class PhaseAwareCollector:
    """Collects folded stacks with phase labels for phase-aware analysis."""

    def __init__(self) -> None:
        self._phase_stacks: Dict[str, Dict[str, int]] = {}
        self._lock = threading.Lock()

    def add(self, stack: str, phase: str) -> None:
        with self._lock:
            if phase not in self._phase_stacks:
                self._phase_stacks[phase] = {}
            self._phase_stacks[phase][stack] = self._phase_stacks[phase].get(stack, 0) + 1

    def add_samples(self, samples: List[Tuple[str, str]]) -> None:
        for stack, phase in samples:
            self.add(stack, phase)

    def phase_data(self, phase: str) -> Dict[str, int]:
        with self._lock:
            return dict(self._phase_stacks.get(phase, {}))

    def all_data(self) -> Dict[str, Dict[str, int]]:
        with self._lock:
            return {k: dict(v) for k, v in self._phase_stacks.items()}

    def total_per_phase(self) -> Dict[str, int]:
        with self._lock:
            return {p: sum(v.values()) for p, v in self._phase_stacks.items()}

    def clear(self) -> None:
        with self._lock:
            self._phase_stacks.clear()


class AdaptiveProfiler:
    """Profiler with adaptive sampling rates and phase-aware collection."""

    def __init__(self, min_interval: float = _MIN_INTERVAL_S, max_interval: float = _MAX_INTERVAL_S) -> None:
        self._sampler = AdaptiveStackSampler(min_interval, max_interval)
        self._collector = PhaseAwareCollector()
        self._start_time: Optional[float] = None

    def start(self) -> None:
        self._start_time = time.time()
        self._sampler.start()

    def stop(self) -> PhaseAwareCollector:
        samples = self._sampler.stop()
        for stack, interval in samples:
            phase = self._sampler.controller.phase
            self._collector.add(stack, phase)
        return self._collector

    @property
    def running(self) -> bool:
        return self._sampler._running

    @property
    def controller(self) -> AdaptiveRateController:
        return self._sampler.controller

    def profile(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        self.start()
        try:
            result = fn(*args, **kwargs)
        finally:
            self.stop()
        return result

    def phase_summary(self) -> Dict[str, Any]:
        per_phase = self._collector.total_per_phase()
        total = sum(per_phase.values()) or 1
        return {
            'total_samples': total,
            'phases': {
                p: {
                    'samples': c,
                    'pct': round(c / total * 100, 1),
                }
                for p, c in sorted(per_phase.items(), key=lambda x: -x[1])
            },
            'interval_range': {
                'min': _MIN_INTERVAL_S,
                'max': _MAX_INTERVAL_S,
            },
        }

    def adaptive_summary(self) -> Dict[str, Any]:
        return self._sampler.controller.summary()

    def report_text(self) -> str:
        s = self.phase_summary()
        a = self.adaptive_summary()
        lines = [
            'Adaptive Profiling Report',
            f'  Total samples: {s["total_samples"]}',
            f'  Current interval: {a["interval_s"]}s',
            f'  Current phase: {a["phase"]}',
            f'  CPU intensity: {a["cpu_intensity"]}',
            '',
            '  Samples per phase:',
        ]
        for phase, info in s.get('phases', {}).items():
            bar = '█' * int(info['pct'] / 5)
            lines.append(f'    {phase:20s} {info["samples"]:6d} ({info["pct"]:5.1f}%) {bar}')
        return '\n'.join(lines)


class AdaptiveProfilingOrchestrator:
    """Manages multiple adaptive profiling runs with comparison."""

    def __init__(self) -> None:
        self._runs: List[Tuple[str, AdaptiveProfiler]] = []
        self._lock = threading.Lock()

    def create_run(self, name: str) -> AdaptiveProfiler:
        profiler = AdaptiveProfiler()
        with self._lock:
            self._runs.append((name, profiler))
        return profiler

    def export_artifacts(self, dir: str) -> List[str]:
        os.makedirs(dir, exist_ok=True)
        paths = []
        for name, profiler in self._runs:
            data_path = os.path.join(dir, f'{name}_adaptive.json')
            report = {
                'name': name,
                'phase_summary': profiler.phase_summary(),
                'adaptive_summary': profiler.adaptive_summary(),
                'phase_data': profiler._collector.all_data(),
            }
            with open(data_path, 'w') as f:
                json.dump(report, f, indent=2, default=str)
            paths.append(data_path)
        return paths
