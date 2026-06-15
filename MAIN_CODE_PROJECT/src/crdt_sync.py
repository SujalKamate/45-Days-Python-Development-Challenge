"""Multi-cluster state synchronization using CRDTs with deterministic merge semantics."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Set, Tuple
import datetime
import json
import os
import threading
import time
import uuid


def _now_ns() -> int:
    return time.time_ns()


def _node_id() -> str:
    return uuid.uuid4().hex[:12]


class LWWRegister:
    """Last-Writer-Wins Register — keeps the most recent value."""

    def __init__(self, value: Any = None, timestamp: int = 0, node: str = '') -> None:
        self._value = value
        self._ts = timestamp
        self._node = node

    def set(self, value: Any, timestamp: Optional[int] = None, node: str = '') -> None:
        ts = timestamp if timestamp is not None else _now_ns()
        node = node or _node_id()
        if (ts, node) > (self._ts, self._node):
            self._value = value
            self._ts = ts
            self._node = node

    def merge(self, other: LWWRegister) -> None:
        if (other._ts, other._node) > (self._ts, self._node):
            self._value = other._value
            self._ts = other._ts
            self._node = other._node

    @property
    def value(self) -> Any:
        return self._value

    def to_dict(self) -> Dict[str, Any]:
        return {'value': self._value, 'timestamp': self._ts, 'node': self._node}

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> LWWRegister:
        return LWWRegister(d['value'], d['timestamp'], d.get('node', ''))


class GCounter:
    """Grow-Only Counter — monotonic increase across nodes."""

    def __init__(self, node_counts: Optional[Dict[str, int]] = None) -> None:
        self._counts: Dict[str, int] = node_counts or {}

    def increment(self, node: str = '', amount: int = 1) -> None:
        n = node or _node_id()
        self._counts[n] = self._counts.get(n, 0) + amount

    def merge(self, other: GCounter) -> None:
        for node, count in other._counts.items():
            self._counts[node] = max(self._counts.get(node, 0), count)

    @property
    def value(self) -> int:
        return sum(self._counts.values())

    def to_dict(self) -> Dict[str, int]:
        return dict(self._counts)

    @staticmethod
    def from_dict(d: Dict[str, int]) -> GCounter:
        return GCounter(d)


class PNCounter:
    """PN-Counter — supports both increment and decrement via paired G-Counters."""

    def __init__(self, pos: Optional[GCounter] = None, neg: Optional[GCounter] = None) -> None:
        self._pos = pos or GCounter()
        self._neg = neg or GCounter()

    def increment(self, node: str = '', amount: int = 1) -> None:
        self._pos.increment(node, amount)

    def decrement(self, node: str = '', amount: int = 1) -> None:
        self._neg.increment(node, amount)

    def merge(self, other: PNCounter) -> None:
        self._pos.merge(other._pos)
        self._neg.merge(other._neg)

    @property
    def value(self) -> int:
        return self._pos.value - self._neg.value

    def to_dict(self) -> Dict[str, Any]:
        return {'pos': self._pos.to_dict(), 'neg': self._neg.to_dict()}

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> PNCounter:
        return PNCounter(GCounter.from_dict(d['pos']), GCounter.from_dict(d['neg']))


class GSet:
    """Grow-Only Set — elements can only be added."""

    def __init__(self, elements: Optional[Set[Any]] = None) -> None:
        self._elements: Set[Any] = set(elements) if elements else set()

    def add(self, element: Any) -> None:
        self._elements.add(element)

    def merge(self, other: GSet) -> None:
        self._elements |= other._elements

    @property
    def elements(self) -> Set[Any]:
        return set(self._elements)

    def contains(self, element: Any) -> bool:
        return element in self._elements

    def to_dict(self) -> List[Any]:
        return list(self._elements)

    @staticmethod
    def from_dict(d: List[Any]) -> GSet:
        return GSet(set(d))


class TwoPhaseSet:
    """2P-Set — supports add and remove (remove wins over add)."""

    def __init__(self, added: Optional[GSet] = None, removed: Optional[GSet] = None) -> None:
        self._added = added or GSet()
        self._removed = removed or GSet()

    def add(self, element: Any) -> None:
        self._added.add(element)

    def remove(self, element: Any) -> None:
        if element in self._added.elements:
            self._removed.add(element)

    def merge(self, other: TwoPhaseSet) -> None:
        self._added.merge(other._added)
        self._removed.merge(other._removed)

    @property
    def elements(self) -> Set[Any]:
        return self._added.elements - self._removed.elements

    def contains(self, element: Any) -> bool:
        return element in self._added.elements and element not in self._removed.elements

    def to_dict(self) -> Dict[str, Any]:
        return {'added': self._added.to_dict(), 'removed': self._removed.to_dict()}

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> TwoPhaseSet:
        return TwoPhaseSet(GSet.from_dict(d['added']), GSet.from_dict(d['removed']))


class LWWMap:
    """Last-Writer-Wins Map — key-value with LWW semantics per key."""

    def __init__(self) -> None:
        self._registers: Dict[str, LWWRegister] = {}
        self._tombstones: Set[str] = set()

    def set(self, key: str, value: Any, timestamp: Optional[int] = None, node: str = '') -> None:
        if key not in self._registers:
            self._registers[key] = LWWRegister()
        self._registers[key].set(value, timestamp, node)
        self._tombstones.discard(key)

    def delete(self, key: str, timestamp: Optional[int] = None, node: str = '') -> None:
        ts = timestamp or _now_ns()
        n = node or _node_id()
        register = LWWRegister(None, ts, n)
        self._registers[key] = register
        self._tombstones.add(key)

    def merge(self, other: LWWMap) -> None:
        for key, reg in other._registers.items():
            if key in self._registers:
                self._registers[key].merge(reg)
            else:
                self._registers[key] = reg
        self._tombstones |= other._tombstones
        for key in list(self._tombstones):
            if key in self._registers:
                reg = self._registers[key]
                if reg.value is not None:
                    self._registers[key] = LWWRegister(None, reg._ts, reg._node)

    def get(self, key: str) -> Any:
        if key in self._tombstones:
            return None
        reg = self._registers.get(key)
        return reg.value if reg else None

    @property
    def keys(self) -> Set[str]:
        return {k for k in self._registers if k not in self._tombstones}

    @property
    def all_data(self) -> Dict[str, Any]:
        return {k: self._registers[k].value for k in self.keys}

    def to_dict(self) -> Dict[str, Any]:
        return {
            'registers': {k: r.to_dict() for k, r in self._registers.items()},
            'tombstones': list(self._tombstones),
        }

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> LWWMap:
        m = LWWMap()
        m._registers = {k: LWWRegister.from_dict(v) for k, v in d.get('registers', {}).items()}
        m._tombstones = set(d.get('tombstones', []))
        return m


class CRDTNode:
    """A node participating in CRDT replication."""

    def __init__(self, node_id: str = '') -> None:
        self.id = node_id or _node_id()
        self._state: Dict[str, Any] = {}
        self._lock = threading.Lock()

    def set_crdt(self, key: str, crdt: Any) -> None:
        with self._lock:
            self._state[key] = crdt

    def get_crdt(self, key: str) -> Any:
        with self._lock:
            return self._state.get(key)

    def merge_from(self, other_node: CRDTNode) -> List[str]:
        merged_keys = []
        with self._lock:
            for key, other_crdt in other_node._state.items():
                if key in self._state:
                    self._state[key].merge(other_crdt)
                else:
                    self._state[key] = other_crdt
                merged_keys.append(key)
        return merged_keys

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {k: v.to_dict() if hasattr(v, 'to_dict') else v for k, v in self._state.items()}

    def restore(self, data: Dict[str, Any]) -> None:
        with self._lock:
            for k, v in data.items():
                if k == 'lww_map':
                    self._state[k] = LWWMap.from_dict(v)
                elif k == 'pn_counter':
                    self._state[k] = PNCounter.from_dict(v)
                elif k == 'g_counter':
                    self._state[k] = GCounter.from_dict(v)
                elif k == 'two_phase_set':
                    self._state[k] = TwoPhaseSet.from_dict(v)
                elif k == 'g_set':
                    self._state[k] = GSet.from_dict(v)
                elif k == 'lww_register':
                    self._state[k] = LWWRegister.from_dict(v)


class ReplicationTopology:
    """Manages peer nodes and replication relationships."""

    def __init__(self) -> None:
        self._peers: Dict[str, CRDTNode] = {}
        self._lock = threading.Lock()

    def add_peer(self, node: CRDTNode) -> None:
        with self._lock:
            self._peers[node.id] = node

    def remove_peer(self, node_id: str) -> None:
        with self._lock:
            self._peers.pop(node_id, None)

    def get_peer(self, node_id: str) -> Optional[CRDTNode]:
        with self._lock:
            return self._peers.get(node_id)

    @property
    def peers(self) -> List[CRDTNode]:
        with self._lock:
            return list(self._peers.values())

    @property
    def peer_ids(self) -> List[str]:
        with self._lock:
            return list(self._peers.keys())

    def broadcast(self, source: CRDTNode) -> Dict[str, List[str]]:
        results = {}
        for peer in self.peers:
            if peer.id != source.id:
                merged = peer.merge_from(source)
                results[peer.id] = merged
        return results


class CRDTReplicator:
    """Orchestrates CRDT replication across nodes with conflict-free merge."""

    def __init__(self, local_node: Optional[CRDTNode] = None) -> None:
        self._local = local_node or CRDTNode()
        self._topology = ReplicationTopology()
        self._topology.add_peer(self._local)
        self._lock = threading.Lock()

    @property
    def local(self) -> CRDTNode:
        return self._local

    def add_peer(self, node: CRDTNode) -> None:
        self._topology.add_peer(node)

    def remove_peer(self, node_id: str) -> None:
        self._topology.remove_peer(node_id)

    @property
    def peers(self) -> List[CRDTNode]:
        return self._topology.peers

    def set(self, key: str, crdt: Any) -> None:
        self._local.set_crdt(key, crdt)

    def get(self, key: str) -> Any:
        return self._local.get_crdt(key)

    def replicate(self) -> Dict[str, List[str]]:
        return self._topology.broadcast(self._local)

    def sync_with(self, peer_id: str) -> List[str]:
        peer = self._topology.get_peer(peer_id)
        if peer:
            return self._local.merge_from(peer)
        return []

    def state_snapshot(self) -> Dict[str, Any]:
        return self._local.snapshot()

    def restore_state(self, data: Dict[str, Any]) -> None:
        self._local.restore(data)

    def summary(self) -> Dict[str, Any]:
        return {
            'local_node': self._local.id,
            'peers': self._topology.peer_ids,
            'crdt_keys': list(self._local._state.keys()),
        }


class CRDTClusterSync:
    """Multi-cluster synchronization manager with periodic replication."""

    def __init__(self, node_id: str = '') -> None:
        self._replicator = CRDTReplicator(CRDTNode(node_id))
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._interval_s = 5.0

    @property
    def replicator(self) -> CRDTReplicator:
        return self._replicator

    def start_periodic_sync(self, interval_s: float = 5.0) -> None:
        self._interval_s = interval_s
        self._running = True
        self._thread = threading.Thread(target=self._sync_loop, daemon=True)
        self._thread.start()

    def stop_periodic_sync(self) -> None:
        self._running = False

    def _sync_loop(self) -> None:
        while self._running:
            self._replicator.replicate()
            time.sleep(self._interval_s)

    def create_lww_map(self, key: str = 'state') -> LWWMap:
        m = LWWMap()
        self._replicator.set(key, m)
        return m

    def create_pn_counter(self, key: str = 'counter') -> PNCounter:
        c = PNCounter()
        self._replicator.set(key, c)
        return c

    def create_two_phase_set(self, key: str = 'set') -> TwoPhaseSet:
        s = TwoPhaseSet()
        self._replicator.set(key, s)
        return s

    def merge_all(self) -> Dict[str, List[str]]:
        return self._replicator.replicate()

    def export_artifacts(self, dir: str) -> List[str]:
        os.makedirs(dir, exist_ok=True)
        paths = []
        sp = os.path.join(dir, 'crdt_state.json')
        with open(sp, 'w') as f:
            json.dump(self._replicator.state_snapshot(), f, indent=2, default=str)
        paths.append(sp)
        return paths
