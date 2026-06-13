"""Event-sourced state journal with time-travel querying, replay, and branching."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
import json
import threading
import time


class StateEvent:
    __slots__ = ('seq', 'timestamp', 'key', 'value', 'branch')

    def __init__(self, seq: int, key: str, value: Any, branch: str = 'main',
                 timestamp: Optional[float] = None) -> None:
        self.seq = seq
        self.timestamp = timestamp or time.time()
        self.key = key
        self.value = value
        self.branch = branch

    def to_dict(self) -> Dict[str, Any]:
        return {
            'seq': self.seq,
            'timestamp': self.timestamp,
            'key': self.key,
            'value': self.value,
            'branch': self.branch,
        }

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> StateEvent:
        return StateEvent(
            seq=d['seq'],
            key=d['key'],
            value=d.get('value'),
            branch=d.get('branch', 'main'),
            timestamp=d.get('timestamp'),
        )


class StateJournal:
    """Append-only event journal for event-sourced state reconstruction.

    Supports time-travel queries, chronological replay, branching,
    and speculative execution.
    """

    def __init__(self) -> None:
        self._events: List[StateEvent] = []
        self._branches: Dict[str, int] = {'main': 0}
        self._lock = threading.Lock()
        self._seq = 0

    def append(self, key: str, value: Any, branch: str = 'main') -> int:
        with self._lock:
            self._seq += 1
            event = StateEvent(self._seq, key, value, branch)
            self._events.append(event)
            self._branches[branch] = self._seq
            return self._seq

    def state_at(self, timestamp: float, branch: str = 'main') -> Dict[str, Any]:
        return self._reconstruct(
            limit_seq=self._branches.get(branch, 0),
            max_timestamp=timestamp,
            branch=branch,
        )

    def state_at_seq(self, seq: int, branch: str = 'main') -> Dict[str, Any]:
        return self._reconstruct(limit_seq=seq, branch=branch)

    def latest_state(self, branch: str = 'main') -> Dict[str, Any]:
        return self._reconstruct(branch=branch)

    def _reconstruct(self, limit_seq: Optional[int] = None,
                     max_timestamp: Optional[float] = None,
                     branch: Optional[str] = None) -> Dict[str, Any]:
        state: Dict[str, Any] = {}
        with self._lock:
            for event in self._events:
                if branch is not None and event.branch != branch:
                    continue
                if limit_seq is not None and event.seq > limit_seq:
                    continue
                if max_timestamp is not None and event.timestamp > max_timestamp:
                    continue
                state[event.key] = event.value
        return state

    def replay(self, branch: str = 'main') -> List[StateEvent]:
        with self._lock:
            return [e for e in self._events if e.branch == branch]

    def replay_range(self, start_seq: int, end_seq: int,
                     branch: str = 'main') -> List[StateEvent]:
        with self._lock:
            return [
                e for e in self._events
                if start_seq <= e.seq <= end_seq and e.branch == branch
            ]

    def create_branch(self, name: str, source_branch: str = 'main',
                      at_seq: Optional[int] = None) -> None:
        with self._lock:
            if name in self._branches:
                return
            base_seq = at_seq if at_seq is not None else self._branches.get(source_branch, 0)
            self._branches[name] = base_seq

    def branch_names(self) -> List[str]:
        return list(self._branches.keys())

    def branch_seq(self, name: str) -> int:
        return self._branches.get(name, 0)

    def merge_branch(self, source: str, target: str = 'main') -> int:
        source_events = self.replay(source)
        count = 0
        for event in source_events:
            if event.seq > self._branches.get(target, 0):
                with self._lock:
                    self._seq += 1
                    merged = StateEvent(self._seq, event.key, event.value, target,
                                        event.timestamp)
                    self._events.append(merged)
                count += 1
        with self._lock:
            self._branches[target] = self._seq
        return count

    def diff(self, seq_a: int, seq_b: int, branch: str = 'main') -> Dict[str, Tuple[Any, Any]]:
        state_a = self.state_at_seq(seq_a, branch)
        state_b = self.state_at_seq(seq_b, branch)
        result: Dict[str, Tuple[Any, Any]] = {}
        all_keys = set(state_a.keys()) | set(state_b.keys())
        for k in sorted(all_keys):
            va = state_a.get(k)
            vb = state_b.get(k)
            if va != vb:
                result[k] = (va, vb)
        return result

    def audit_log(self, branch: str = 'main') -> List[Dict[str, Any]]:
        return [e.to_dict() for e in self.replay(branch)]

    @property
    def total_events(self) -> int:
        return len(self._events)

    def export(self) -> Dict[str, Any]:
        return {
            'branches': dict(self._branches),
            'events': [e.to_dict() for e in self._events],
        }

    def load(self, data: Dict[str, Any]) -> None:
        self._branches = data.get('branches', {'main': 0})
        self._events = [StateEvent.from_dict(e) for e in data.get('events', [])]
        self._seq = max((e.seq for e in self._events), default=0)
