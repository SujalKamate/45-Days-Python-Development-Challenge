"""Entropy-based random seed generation with continuous health monitoring."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
import datetime
import os
import random
import struct
import threading
import time


_HEALTH_CHECK_INTERVAL = 5.0
_LOW_ENTROPY_THRESHOLD = 32


def _estimate_entropy() -> int:
    sample = os.urandom(64)
    byte_counts = [0] * 256
    for b in sample:
        byte_counts[b] += 1
    entropy = 0.0
    for c in byte_counts:
        if c > 0:
            p = c / len(sample)
            entropy -= p * (p and __import__('math').log2(p) or 0)
    return int(entropy * 8)


class EntropySource:
    """Provides entropy from multiple sources with fallback."""

    @staticmethod
    def urandom(n: int = 32) -> bytes:
        return os.urandom(n)

    @staticmethod
    def time_jitter(n: int = 8) -> bytes:
        parts: List[float] = []
        for _ in range(4):
            t0 = time.perf_counter_ns()
            _ = [i**2 for i in range(100)]
            t1 = time.perf_counter_ns()
            parts.append(float(t1 - t0))
        import struct as _st
        return b''.join(_st.pack('d', p) for p in parts)[:n]

    @staticmethod
    def mixed(n: int = 32) -> bytes:
        return EntropySource.urandom(n // 2) + EntropySource.time_jitter(n - n // 2)


class SeedGenerator:
    """Generates cryptographic-quality seeds from entropy sources."""

    def __init__(self, source: str = 'mixed') -> None:
        self._source = source

    def generate(self, nbytes: int = 32) -> bytes:
        if self._source == 'urandom':
            return EntropySource.urandom(nbytes)
        if self._source == 'jitter':
            return EntropySource.time_jitter(nbytes)
        return EntropySource.mixed(nbytes)

    def generate_int(self, max_val: int = (1 << 128)) -> int:
        nbytes = (max_val.bit_length() + 7) // 8
        seed = self.generate(nbytes)
        return int.from_bytes(seed, 'big') % max_val

    def seed_random(self) -> None:
        seed = self.generate(32)
        random.seed(seed)


class EntropyHealthMonitor:
    """Monitors entropy availability and quality continuously."""

    def __init__(self, low_threshold: int = _LOW_ENTROPY_THRESHOLD) -> None:
        self._threshold = low_threshold
        self._readings: List[Dict[str, Any]] = []
        self._running = False
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False

    def _monitor_loop(self) -> None:
        while self._running:
            est = _estimate_entropy()
            status = 'ok' if est >= self._threshold else 'low'
            now = datetime.datetime.now(datetime.timezone.utc).isoformat()
            with self._lock:
                self._readings.append({'timestamp': now, 'estimate': est, 'status': status})
                if len(self._readings) > 1000:
                    self._readings.pop(0)
            if status == 'low':
                self._fallback()
            time.sleep(_HEALTH_CHECK_INTERVAL)

    def _fallback(self) -> None:
        _ = os.urandom(128)

    @property
    def healthy(self) -> bool:
        with self._lock:
            if not self._readings:
                return True
            return self._readings[-1]['status'] == 'ok'

    @property
    def last_estimate(self) -> int:
        with self._lock:
            if not self._readings:
                return _estimate_entropy()
            return self._readings[-1]['estimate']

    def readings(self, n: int = 10) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._readings[-n:])


class EntropyManager:
    """Top-level manager combining seed generation with health monitoring."""

    def __init__(self, low_threshold: int = _LOW_ENTROPY_THRESHOLD) -> None:
        self._generator = SeedGenerator()
        self._monitor = EntropyHealthMonitor(low_threshold)
        self._deterministic_mode = False
        self._fixed_seed: Optional[bytes] = None

    def start_monitoring(self) -> None:
        self._monitor.start()

    def stop_monitoring(self) -> None:
        self._monitor.stop()

    @property
    def healthy(self) -> bool:
        return self._monitor.healthy

    @property
    def entropy_estimate(self) -> int:
        return self._monitor.last_estimate

    def seed(self, nbytes: int = 32) -> bytes:
        if self._deterministic_mode and self._fixed_seed is not None:
            return self._fixed_seed[:nbytes]
        if not self.healthy:
            return EntropySource.urandom(nbytes)
        return self._generator.generate(nbytes)

    def seed_int(self, max_val: int = (1 << 128)) -> int:
        nbytes = (max_val.bit_length() + 7) // 8
        return int.from_bytes(self.seed(nbytes), 'big') % max_val

    def enable_deterministic(self, seed: Optional[bytes] = None) -> None:
        self._deterministic_mode = True
        self._fixed_seed = seed or b'\x01' * 32

    def disable_deterministic(self) -> None:
        self._deterministic_mode = False
        self._fixed_seed = None

    def health_readings(self, n: int = 10) -> List[Dict[str, Any]]:
        return self._monitor.readings(n)

    def reseed_random(self) -> None:
        self._generator.seed_random()
