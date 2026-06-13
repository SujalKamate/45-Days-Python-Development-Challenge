"""Snapshot testing framework with automated approval and update workflows."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Set, Tuple
import datetime
import difflib
import hashlib
import json
import os
import threading
import time


_SNAPSHOT_DIR = '.snapshots'


def _normalize(data: Any) -> str:
    return json.dumps(data, sort_keys=True, indent=2, default=str)


def _hash(data: Any) -> str:
    return hashlib.sha256(_normalize(data).encode()).hexdigest()[:16]


class Snapshot:
    """A single named snapshot with approved and current values."""

    def __init__(self, name: str, data: Any = None, metadata: Optional[Dict[str, Any]] = None) -> None:
        self.name = name
        self.approved: Any = data
        self.current: Any = None
        self.metadata = metadata or {}
        self._created_at = datetime.datetime.now(datetime.timezone.utc).isoformat()

    def update(self, data: Any) -> None:
        self.current = data

    def approve(self) -> None:
        if self.current is not None:
            self.approved = self.current

    @property
    def approved_hash(self) -> str:
        if self.approved is None:
            return ''
        return _hash(self.approved)

    @property
    def current_hash(self) -> str:
        if self.current is None:
            return ''
        return _hash(self.current)

    @property
    def matched(self) -> Optional[bool]:
        if self.approved is None or self.current is None:
            return None
        return self.approved_hash == self.current_hash

    def diff(self) -> str:
        approved_str = _normalize(self.approved) if self.approved is not None else ''
        current_str = _normalize(self.current) if self.current is not None else ''
        if approved_str == current_str:
            return ''
        lines = difflib.unified_diff(
            approved_str.splitlines(keepends=True),
            current_str.splitlines(keepends=True),
            fromfile=f'{self.name} (approved)',
            tofile=f'{self.name} (current)',
        )
        return ''.join(lines)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'approved': self.approved,
            'current': self.current,
            'metadata': self.metadata,
            'created_at': self._created_at,
            'approved_hash': self.approved_hash,
            'current_hash': self.current_hash,
            'matched': self.matched,
        }


class SnapshotStore:
    """Persists snapshots to disk."""

    def __init__(self, directory: str = _SNAPSHOT_DIR) -> None:
        self._dir = directory
        os.makedirs(self._dir, exist_ok=True)

    def save(self, snapshot: Snapshot) -> str:
        path = self._path_for(snapshot.name)
        payload = snapshot.to_dict()
        payload.pop('current', None)
        payload.pop('matched', None)
        payload.pop('current_hash', None)
        with open(path, 'w') as f:
            json.dump(payload, f, indent=2, default=str)
        return path

    def load(self, name: str) -> Optional[Snapshot]:
        path = self._path_for(name)
        if not os.path.exists(path):
            return None
        try:
            with open(path) as f:
                data = json.load(f)
            snap = Snapshot(data['name'], data.get('approved'), data.get('metadata', {}))
            snap._created_at = data.get('created_at', snap._created_at)
            return snap
        except (json.JSONDecodeError, KeyError):
            return None

    def list_snapshots(self) -> List[str]:
        if not os.path.isdir(self._dir):
            return []
        files = [f for f in os.listdir(self._dir) if f.endswith('.snap.json')]
        return sorted(f[:-len('.snap.json')] for f in files)

    def delete(self, name: str) -> bool:
        path = self._path_for(name)
        if os.path.exists(path):
            os.remove(path)
            return True
        return False

    def _path_for(self, name: str) -> str:
        safe = name.replace('/', '_').replace('\\', '_').replace(' ', '_')
        return os.path.join(self._dir, f'{safe}.snap.json')


class SnapshotMatcher:
    """Compares current output against approved snapshots."""

    def __init__(self, store: SnapshotStore) -> None:
        self._store = store
        self._results: Dict[str, bool] = {}
        self._lock = threading.Lock()

    def match(self, name: str, data: Any) -> bool:
        approved = self._store.load(name)
        if approved is None:
            with self._lock:
                self._results[name] = False
            return False
        current_hash = _hash(data)
        approved_hash = approved.approved_hash
        matched = current_hash == approved_hash
        with self._lock:
            self._results[name] = matched
        return matched

    def match_all(self, snapshots: Dict[str, Any]) -> Dict[str, bool]:
        for name, data in snapshots.items():
            self.match(name, data)
        with self._lock:
            return dict(self._results)

    @property
    def results(self) -> Dict[str, bool]:
        with self._lock:
            return dict(self._results)

    @property
    def passed(self) -> int:
        return sum(1 for v in self.results.values() if v)

    @property
    def failed(self) -> int:
        return sum(1 for v in self.results.values() if not v)

    def clear(self) -> None:
        with self._lock:
            self._results.clear()


class SnapshotTestRunner:
    """Orchestrates snapshot testing with approval workflow."""

    def __init__(self, store: Optional[SnapshotStore] = None) -> None:
        self._store = store or SnapshotStore()
        self._matcher = SnapshotMatcher(self._store)
        self._pending: List[Snapshot] = []

    def assert_matches(self, name: str, data: Any) -> bool:
        snap = self._store.load(name)
        if snap is None:
            self._pending.append(Snapshot(name, data))
            return True
        snap.update(data)
        if snap.matched:
            return True
        self._pending.append(snap)
        return False

    def record(self, name: str, data: Any) -> Snapshot:
        snap = Snapshot(name, data)
        self._store.save(snap)
        return snap

    def approve_pending(self) -> int:
        count = 0
        for snap in self._pending:
            if snap.current is not None:
                snap.approve()
                self._store.save(snap)
                count += 1
        self._pending.clear()
        return count

    def reject_pending(self) -> int:
        count = len(self._pending)
        self._pending.clear()
        return count

    def diff(self, name: str, data: Any) -> str:
        approved = self._store.load(name)
        if approved is None:
            return '(no approved snapshot)'
        approved.update(data)
        return approved.diff()

    def list_snapshots(self) -> List[str]:
        return self._store.list_snapshots()

    @property
    def pending_count(self) -> int:
        return len(self._pending)

    @property
    def pending_names(self) -> List[str]:
        return [s.name for s in self._pending]


class SnapshotUpdateController:
    """Controls batch snapshot updates with review."""

    def __init__(self, runner: SnapshotTestRunner) -> None:
        self._runner = runner
        self._updated: List[str] = []

    def update_snapshot(self, name: str, data: Any) -> Snapshot:
        snap = self._runner.record(name, data)
        self._updated.append(name)
        return snap

    def update_batch(self, snapshots: Dict[str, Any]) -> List[Snapshot]:
        results = []
        for name, data in snapshots.items():
            results.append(self.update_snapshot(name, data))
        return results

    def rollback(self, names: Optional[List[str]] = None) -> int:
        store = self._runner._store
        targets = names if names is not None else self._updated
        count = 0
        for name in targets:
            stored = store.load(name)
            if stored and stored.current is not None:
                stored.approved = stored.current
                store.save(stored)
                count += 1
        return count

    @property
    def updated_snapshots(self) -> List[str]:
        return list(self._updated)


class SnapshotTestFramework:
    """Top-level snapshot testing interface."""

    def __init__(self, snapshot_dir: str = _SNAPSHOT_DIR) -> None:
        self._store = SnapshotStore(snapshot_dir)
        self._runner = SnapshotTestRunner(self._store)
        self._updater = SnapshotUpdateController(self._runner)
        self._results: List[Dict[str, Any]] = []
        self._lock = threading.Lock()

    def test(self, name: str, data: Any) -> bool:
        t0 = time.perf_counter()
        snap = self._store.load(name)

        if snap is None:
            self._runner.record(name, data)
            elapsed = (time.perf_counter() - t0) * 1000
            with self._lock:
                self._results.append({
                    'name': name,
                    'status': 'created',
                    'matched': True,
                    'elapsed_ms': round(elapsed, 3),
                })
            return True

        snap.update(data)
        matched = snap.matched if snap.matched is not None else False
        elapsed = (time.perf_counter() - t0) * 1000

        with self._lock:
            self._results.append({
                'name': name,
                'status': 'matched' if matched else 'mismatch',
                'matched': matched,
                'diff': '' if matched else snap.diff()[:500],
                'elapsed_ms': round(elapsed, 3),
            })
        return matched

    def test_batch(self, snapshots: Dict[str, Any]) -> Dict[str, bool]:
        results = {}
        for name, data in snapshots.items():
            results[name] = self.test(name, data)
        return results

    def approve_all(self) -> int:
        return self._runner.approve_pending()

    def approve(self, name: str, data: Any) -> None:
        self._updater.update_snapshot(name, data)

    def diff(self, name: str, data: Any) -> str:
        return self._runner.diff(name, data)

    def list_snapshots(self) -> List[str]:
        return self._runner.list_snapshots()

    def delete_snapshot(self, name: str) -> bool:
        return self._store.delete(name)

    def summary(self) -> Dict[str, Any]:
        with self._lock:
            matched = sum(1 for r in self._results if r.get('matched'))
            total = len(self._results)
            created = sum(1 for r in self._results if r.get('status') == 'created')
        return {
            'total': total,
            'matched': matched,
            'mismatch': total - matched,
            'created': created,
            'pass_rate': round(matched / max(total, 1) * 100, 1),
        }

    def report_text(self) -> str:
        s = self.summary()
        lines = [
            'Snapshot Testing Report',
            f'  Total: {s["total"]}',
            f'  Matched: {s["matched"]}',
            f'  Mismatch: {s["mismatch"]}',
            f'  Created: {s["created"]}',
            f'  Pass rate: {s["pass_rate"]}%',
        ]
        with self._lock:
            for r in self._results:
                if not r.get('matched'):
                    lines.append(f'  MISMATCH {r["name"]}:')
                    if r.get('diff'):
                        for dline in r['diff'].split('\n')[:10]:
                            lines.append(f'    {dline}')
        return '\n'.join(lines)

    def export_report(self, path: str) -> None:
        report = {
            'summary': self.summary(),
            'results': list(self._results),
        }
        with open(path, 'w') as f:
            json.dump(report, f, indent=2, default=str)

    def export_artifacts(self, dir: str) -> List[str]:
        os.makedirs(dir, exist_ok=True)
        paths = []
        rp = os.path.join(dir, 'snapshot_report.json')
        self.export_report(rp)
        paths.append(rp)
        return paths
