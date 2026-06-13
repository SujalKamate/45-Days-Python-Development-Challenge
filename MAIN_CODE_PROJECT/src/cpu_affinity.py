"""CPU affinity management and NUMA-aware scheduling for multi-core optimization."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Set, Tuple
import datetime
import json
import os
import platform
import random
import struct
import threading
import time


_NUMA_NODE_PATH = '/sys/devices/system/node'
_CPU_INFO_PATH = '/proc/cpuinfo'


class TopologyDetector:
    """Detects CPU topology: cores, sockets, NUMA nodes."""

    def __init__(self) -> None:
        self._cores: List[int] = []
        self._numa_nodes: Dict[int, List[int]] = {}
        self._sockets: Dict[int, List[int]] = {}
        self._detected = False

    def detect(self) -> None:
        if platform.system() == 'Windows':
            self._detect_windows()
        elif platform.system() == 'Linux':
            self._detect_linux()
        else:
            self._detect_fallback()
        self._detected = True

    def _detect_windows(self) -> None:
        try:
            import subprocess
            result = subprocess.run(
                ['powershell', '-Command',
                 'Get-CimInstance Win32_Processor | Select-Object NumberOfCores, NumberOfLogicalProcessors'],
                capture_output=True, text=True, timeout=10,
            )
        except Exception:
            pass
        count = os.cpu_count() or 4
        self._cores = list(range(count))
        self._numa_nodes = {0: self._cores}

    def _detect_linux(self) -> None:
        if os.path.isdir(_NUMA_NODE_PATH):
            for entry in os.listdir(_NUMA_NODE_PATH):
                if entry.startswith('node'):
                    node_id = int(entry[4:])
                    cpulist_path = os.path.join(_NUMA_NODE_PATH, entry, 'cpulist')
                    if os.path.exists(cpulist_path):
                        with open(cpulist_path) as f:
                            self._numa_nodes[node_id] = self._parse_cpulist(f.read().strip())
        if not self._numa_nodes:
            count = os.cpu_count() or 4
            self._numa_nodes = {0: list(range(count))}
        all_cores = set()
        for cores in self._numa_nodes.values():
            all_cores.update(cores)
        self._cores = sorted(all_cores)

    def _parse_cpulist(self, cpulist: str) -> List[int]:
        cores = []
        for part in cpulist.split(','):
            if '-' in part:
                start, end = part.split('-')
                cores.extend(range(int(start), int(end) + 1))
            elif part:
                cores.append(int(part))
        return cores

    def _detect_fallback(self) -> None:
        count = os.cpu_count() or 4
        self._cores = list(range(count))
        self._numa_nodes = {0: self._cores}

    @property
    def core_count(self) -> int:
        if not self._detected:
            self.detect()
        return len(self._cores)

    @property
    def numa_node_count(self) -> int:
        if not self._detected:
            self.detect()
        return len(self._numa_nodes)

    def cores_for_node(self, node: int) -> List[int]:
        if not self._detected:
            self.detect()
        return self._numa_nodes.get(node, [])

    def node_for_core(self, core: int) -> Optional[int]:
        if not self._detected:
            self.detect()
        for node, cores in self._numa_nodes.items():
            if core in cores:
                return node
        return None

    def summary(self) -> Dict[str, Any]:
        if not self._detected:
            self.detect()
        return {
            'total_cores': self.core_count,
            'numa_nodes': self.numa_node_count,
            'cores_per_node': {n: len(c) for n, c in self._numa_nodes.items()},
        }


class CPUAffinityManager:
    """Manages thread/process CPU affinity for cache locality."""

    def __init__(self, topology: TopologyDetector) -> None:
        self._topology = topology
        self._assignments: Dict[int, int] = {}
        self._lock = threading.Lock()

    def pin_current(self, core: int) -> bool:
        try:
            if platform.system() == 'Windows':
                import ctypes
                mask = 1 << core
                result = ctypes.windll.kernel32.SetThreadAffinityMask(
                    ctypes.windll.kernel32.GetCurrentThread(), mask
                )
                return result != 0
            elif platform.system() == 'Linux':
                import os as _os
                affinity = {core}
                _os.sched_setaffinity(0, affinity)
                return True
            else:
                return False
        except Exception:
            return False

    def pin_thread(self, thread: threading.Thread, core: int) -> bool:
        try:
            thread_id = thread.native_id
            if thread_id is None:
                return False
            if platform.system() == 'Windows':
                import ctypes
                mask = 1 << core
                result = ctypes.windll.kernel32.SetThreadAffinityMask(
                    ctypes.windll.kernel32.OpenThread(0x0200, False, thread_id), mask
                )
                return result != 0
            elif platform.system() == 'Linux':
                import os as _os
                _os.sched_setaffinity(thread_id, {core})
                return True
            else:
                return False
        except Exception:
            return False

    def assign(self, task_id: int, policy: str = 'round_robin') -> int:
        with self._lock:
            cores = self._topology._cores
            if not cores:
                cores = list(range(os.cpu_count() or 4))
            if policy == 'round_robin':
                core = cores[self._assignments.get(None, 0) % len(cores)]
                self._assignments[task_id] = core
            elif policy == 'first_available':
                assigned = set(self._assignments.values())
                for c in cores:
                    if c not in assigned:
                        core = c
                        break
                else:
                    core = cores[0]
                self._assignments[task_id] = core
            else:
                core = cores[hash(str(task_id)) % len(cores)]
                self._assignments[task_id] = core
            return core

    def release(self, task_id: int) -> None:
        with self._lock:
            self._assignments.pop(task_id, None)

    def current_assignments(self) -> Dict[int, int]:
        with self._lock:
            return dict(self._assignments)


class NUMAScheduler:
    """NUMA-aware task scheduler that minimizes cross-node traffic."""

    def __init__(self, topology: TopologyDetector) -> None:
        self._topology = topology
        self._node_load: Dict[int, int] = {}
        self._lock = threading.Lock()

    def suggest_node(self, data_hint: Optional[int] = None) -> int:
        with self._lock:
            nodes = list(self._topology._numa_nodes.keys())
            if not nodes:
                return 0
            if data_hint is not None and data_hint in nodes:
                return data_hint
            loads = [(n, self._node_load.get(n, 0)) for n in nodes]
            loads.sort(key=lambda x: x[1])
            node = loads[0][0]
            self._node_load[node] = self._node_load.get(node, 0) + 1
            return node

    def suggest_cores(self, count: int, preferred_node: Optional[int] = None) -> List[int]:
        if preferred_node is not None:
            cores = self._topology.cores_for_node(preferred_node)
            if len(cores) >= count:
                return cores[:count]
        all_cores = []
        nodes = sorted(self._topology._numa_nodes.keys())
        if preferred_node is not None and preferred_node in nodes:
            nodes = [preferred_node] + [n for n in nodes if n != preferred_node]
        for node in nodes:
            all_cores.extend(self._topology.cores_for_node(node))
        return all_cores[:count]

    def balance(self) -> Dict[int, int]:
        with self._lock:
            loads = dict(self._node_load)
        return loads

    def reset_load(self) -> None:
        with self._lock:
            self._node_load.clear()


class AffinityWorkerPool:
    """Thread pool with core affinity and NUMA-aware assignment."""

    def __init__(self, max_workers: int = 0, numa_aware: bool = True) -> None:
        self._topology = TopologyDetector()
        self._topology.detect()
        self._affinity = CPUAffinityManager(self._topology)
        self._numa = NUMAScheduler(self._topology)
        self._numa_aware = numa_aware
        self._workers: Dict[int, threading.Thread] = {}
        self._lock = threading.Lock()
        core_count = self._topology.core_count
        self._max_workers = max_workers or core_count

    def submit(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        task_id = id(fn)
        node = self._numa.suggest_node() if self._numa_aware else 0
        core = self._affinity.assign(task_id)
        result_holder = []

        def wrapper() -> None:
            self._affinity.pin_current(core)
            try:
                result = fn(*args, **kwargs)
                result_holder.append(result)
            except Exception as e:
                result_holder.append(e)

        t = threading.Thread(target=wrapper, daemon=True)
        with self._lock:
            self._workers[task_id] = t
        t.start()
        return result_holder

    def join_all(self, timeout_s: float = 30.0) -> None:
        with self._lock:
            workers = list(self._workers.values())
        for t in workers:
            t.join(timeout=timeout_s)
        with self._lock:
            self._workers.clear()

    @property
    def topology(self) -> TopologyDetector:
        return self._topology

    def summary(self) -> Dict[str, Any]:
        return {
            'topology': self._topology.summary(),
            'numa_aware': self._numa_aware,
            'max_workers': self._max_workers,
            'active_workers': len(self._workers),
        }


class AffinityOrchestrator:
    """Top-level orchestrator for affinity and NUMA management."""

    def __init__(self) -> None:
        self._topology = TopologyDetector()
        self._topology.detect()
        self._affinity = CPUAffinityManager(self._topology)
        self._numa = NUMAScheduler(self._topology)

    @property
    def topology(self) -> TopologyDetector:
        return self._topology

    def pin_current(self, core: int) -> bool:
        return self._affinity.pin_current(core)

    def create_pool(self, max_workers: int = 0, numa_aware: bool = True) -> AffinityWorkerPool:
        return AffinityWorkerPool(max_workers, numa_aware)

    def suggest_node(self, data_hint: Optional[int] = None) -> int:
        return self._numa.suggest_node(data_hint)

    def suggest_cores(self, count: int, preferred_node: Optional[int] = None) -> List[int]:
        return self._numa.suggest_cores(count, preferred_node)

    def topology_summary(self) -> Dict[str, Any]:
        return self._topology.summary()

    def export_artifacts(self, dir: str) -> List[str]:
        os.makedirs(dir, exist_ok=True)
        paths = []
        rp = os.path.join(dir, 'topology.json')
        with open(rp, 'w') as f:
            json.dump(self._topology.summary(), f, indent=2)
        paths.append(rp)
        return paths
