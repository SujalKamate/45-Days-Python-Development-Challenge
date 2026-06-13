"""Phase barrier synchronization — coordinated checkpoints across execution stages."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Set
import threading
import time


class PhaseBarrier:
    """A reusable synchronization barrier for a named execution phase.

    All participants must ``arrive()`` before any proceeds past the barrier.
    """

    def __init__(self, phase: str, num_participants: int) -> None:
        self._phase = phase
        self._num = num_participants
        self._arrived: Set[str] = set()
        self._lock = threading.Lock()
        self._cv = threading.Condition(self._lock)
        self._generation = 0

    def arrive(self, name: str) -> None:
        with self._cv:
            self._arrived.add(name)
            if len(self._arrived) >= self._num:
                self._generation += 1
                self._arrived.clear()
                self._cv.notify_all()
                return
            current_gen = self._generation
            while self._generation == current_gen:
                self._cv.wait()

    def arrived_count(self) -> int:
        with self._lock:
            return len(self._arrived)

    @property
    def phase(self) -> str:
        return self._phase


class PhaseCoordinator:
    """Manages multiple phase barriers for a multi-stage execution pipeline.

    Modules register for phases and synchronize at each stage before
    advancing to the next.
    """

    def __init__(self) -> None:
        self._barriers: Dict[str, PhaseBarrier] = {}
        self._participants: Set[str] = set()
        self._phases: List[str] = []
        self._current_phase_idx = 0
        self._lock = threading.Lock()
        self._phase_data: Dict[str, Any] = {}

    def register(self, name: str) -> None:
        with self._lock:
            self._participants.add(name)

    def unregister(self, name: str) -> None:
        with self._lock:
            self._participants.discard(name)

    def define_phases(self, phases: List[str]) -> None:
        with self._lock:
            self._phases = list(phases)
            n = len(self._participants) or 1
            self._barriers = {p: PhaseBarrier(p, n) for p in phases}

    def wait(self, phase: str, name: str) -> None:
        with self._lock:
            barrier = self._barriers.get(phase)
        if barrier is not None:
            barrier.arrive(name)

    def barrier(self, phase: str) -> Optional[PhaseBarrier]:
        return self._barriers.get(phase)

    def set_phase_data(self, key: str, value: Any) -> None:
        with self._lock:
            self._phase_data[key] = value

    def get_phase_data(self, key: str) -> Optional[Any]:
        with self._lock:
            return self._phase_data.get(key)

    @property
    def current_phase(self) -> Optional[str]:
        with self._lock:
            if self._current_phase_idx < len(self._phases):
                return self._phases[self._current_phase_idx]
            return None

    @property
    def phases(self) -> List[str]:
        return list(self._phases)


class BarrierGroup:
    """A context manager that synchronizes N participants at a single barrier."""

    def __init__(self, name: str, num_participants: int) -> None:
        self._barrier = PhaseBarrier(name, num_participants)
        self._name = name

    def __enter__(self) -> PhaseBarrier:
        return self._barrier

    def __exit__(self, *args) -> None:
        pass


def phased_execution(phases: List[str], workers: Dict[str, Callable[[str], None]]) -> None:
    """Run multiple workers through synchronized phases.

    Each worker callable receives the current phase name.
    All workers complete the current phase before any advances.
    """
    names = list(workers.keys())
    coordinator = PhaseCoordinator()
    for n in names:
        coordinator.register(n)
    coordinator.define_phases(phases)

    def _worker(name: str, fn: Callable[[str], None]) -> None:
        for phase in phases:
            fn(phase)
            coordinator.wait(phase, name)

    threads = [threading.Thread(target=_worker, args=(n, f), daemon=True)
               for n, f in workers.items()]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
