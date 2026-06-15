"""Hot module reloading with automated state migration and rollback support."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple
import datetime
import hashlib
import importlib
import inspect
import json
import os
import sys
import threading
import time
import uuid


class FileWatchEvent:
    """Event recording a detected source file change."""

    def __init__(self, path: str, old_hash: str, new_hash: str) -> None:
        self.path = path
        self.old_hash = old_hash
        self.new_hash = new_hash
        self.timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            'path': self.path,
            'old_hash': self.old_hash[:16],
            'new_hash': self.new_hash[:16],
            'timestamp': self.timestamp,
        }


class ModuleWatcher:
    """Poll source files for changes via SHA-256 hash."""

    def __init__(self, poll_interval_s: float = 2.0) -> None:
        self._poll_interval = poll_interval_s
        self._file_hashes: Dict[str, str] = {}
        self._watch_paths: Dict[str, str] = {}
        self._events: List[FileWatchEvent] = []

    def watch(self, module_name: str, path: str) -> None:
        self._watch_paths[module_name] = path
        self._file_hashes[path] = self._hash_file(path)

    def unwatch(self, module_name: str) -> None:
        path = self._watch_paths.pop(module_name, '')
        self._file_hashes.pop(path, None)

    def poll(self) -> List[FileWatchEvent]:
        events: List[FileWatchEvent] = []
        for path, old_hash in list(self._file_hashes.items()):
            new_hash = self._hash_file(path)
            if new_hash and new_hash != old_hash:
                ev = FileWatchEvent(path, old_hash, new_hash)
                events.append(ev)
                self._file_hashes[path] = new_hash
                self._events.append(ev)
        return events

    def changed_modules(self) -> List[str]:
        changed = []
        for module_name, path in self._watch_paths.items():
            h = self._hash_file(path)
            if h and h != self._file_hashes.get(path):
                changed.append(module_name)
        return changed

    def history(self, limit: int = 100) -> List[Dict[str, Any]]:
        return [e.to_dict() for e in self._events[-limit:]]

    @staticmethod
    def _hash_file(path: str) -> str:
        try:
            with open(path, 'rb') as f:
                return hashlib.sha256(f.read()).hexdigest()
        except IOError:
            return ''


class StateSnapshot:
    """Serialized state capture for migration and rollback."""

    def __init__(self, module_name: str, version: int,
                 data: Dict[str, Any]) -> None:
        self.id = uuid.uuid4().hex[:12]
        self.module_name = module_name
        self.version = version
        self.data = data
        self.timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'module': self.module_name,
            'version': self.version,
            'data': self.data,
            'timestamp': self.timestamp,
        }


class Migration:
    """A state migration between two versions."""

    def __init__(self, from_version: int, to_version: int,
                 migrate_fn: Callable[[Dict[str, Any]], Dict[str, Any]],
                 description: str = '') -> None:
        self.from_version = from_version
        self.to_version = to_version
        self.migrate_fn = migrate_fn
        self.description = description

    def apply(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return self.migrate_fn(data)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'from': self.from_version,
            'to': self.to_version,
            'description': self.description,
        }


class MigrationRegistry:
    """Registry of version-to-version state migrations."""

    def __init__(self) -> None:
        self._migrations: List[Migration] = []

    def register(self, migration: Migration) -> None:
        self._migrations.append(migration)

    def chain(self, from_version: int, to_version: int) -> List[Migration]:
        chained: List[Migration] = []
        current = from_version
        while current < to_version:
            found = [m for m in self._migrations if m.from_version == current]
            if not found:
                break
            mig = found[0]
            chained.append(mig)
            current = mig.to_version
        return chained

    def list_migrations(self) -> List[Dict[str, Any]]:
        return [m.to_dict() for m in self._migrations]


class StateStore:
    """Persistent state storage with snapshot versioning."""

    def __init__(self, base_dir: str = '') -> None:
        self._base_dir = base_dir or os.path.join(os.getcwd(), '.hot_reload')
        os.makedirs(self._base_dir, exist_ok=True)

    def save_snapshot(self, snapshot: StateSnapshot) -> str:
        path = os.path.join(self._base_dir, f'{snapshot.module_name}_v{snapshot.version}.json')
        with open(path, 'w') as f:
            json.dump(snapshot.to_dict(), f, indent=2)
        return path

    def load_snapshot(self, module_name: str, version: int) -> Optional[StateSnapshot]:
        path = os.path.join(self._base_dir, f'{module_name}_v{version}.json')
        try:
            with open(path, 'r') as f:
                data = json.load(f)
            snap = StateSnapshot(data['module'], data['version'], data['data'])
            snap.id = data['id']
            snap.timestamp = data['timestamp']
            return snap
        except (IOError, json.JSONDecodeError, KeyError):
            return None

    def list_snapshots(self, module_name: str) -> List[int]:
        versions = []
        for fname in os.listdir(self._base_dir):
            if fname.startswith(f'{module_name}_v') and fname.endswith('.json'):
                try:
                    v = int(fname.split('_v')[1].split('.')[0])
                    versions.append(v)
                except (IndexError, ValueError):
                    pass
        return sorted(versions)


class HotReloader:
    """Reload a Python module at runtime preserving references."""

    def __init__(self) -> None:
        self._reload_history: List[Dict[str, Any]] = []

    def reload(self, module_name: str) -> bool:
        if module_name not in sys.modules:
            return False
        try:
            old_module = sys.modules[module_name]
            old_file = getattr(old_module, '__file__', '')

            new_module = importlib.reload(sys.modules[module_name])
            self._reload_history.append({
                'module': module_name,
                'file': old_file,
                'status': 'reloaded',
                'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            })
            return True
        except Exception as e:
            self._reload_history.append({
                'module': module_name,
                'status': 'error',
                'error': str(e),
                'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            })
            return False

    def history(self, limit: int = 100) -> List[Dict[str, Any]]:
        return self._reload_history[-limit:]

    def last_reload(self) -> Optional[Dict[str, Any]]:
        return self._reload_history[-1] if self._reload_history else None


class RollbackManager:
    """Roll back modules to previous versions using stored snapshots."""

    def __init__(self, state_store: StateStore) -> None:
        self._state_store = state_store
        self._rollbacks: List[Dict[str, Any]] = []

    def snapshot_state(self, module_name: str, version: int,
                       data: Dict[str, Any]) -> StateSnapshot:
        snap = StateSnapshot(module_name, version, data)
        self._state_store.save_snapshot(snap)
        return snap

    def rollback(self, module_name: str, target_version: int,
                 reload_fn: Optional[Callable[[], bool]] = None) -> bool:
        snap = self._state_store.load_snapshot(module_name, target_version)
        if snap is None:
            self._rollbacks.append({
                'module': module_name,
                'target_version': target_version,
                'status': 'failed',
                'error': 'Snapshot not found',
                'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            })
            return False

        if reload_fn and not reload_fn():
            self._rollbacks.append({
                'module': module_name,
                'target_version': target_version,
                'status': 'failed',
                'error': 'Reload after rollback failed',
                'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            })
            return False

        self._rollbacks.append({
            'module': module_name,
            'target_version': target_version,
            'status': 'rolled_back',
            'snapshot_id': snap.id,
            'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        })
        return True

    def history(self, limit: int = 100) -> List[Dict[str, Any]]:
        return self._rollbacks[-limit:]

    def can_rollback(self, module_name: str, version: int) -> bool:
        return self._state_store.load_snapshot(module_name, version) is not None


class HotReloadEngine:
    """Top-level hot module reloading engine."""

    def __init__(self, poll_interval_s: float = 2.0) -> None:
        self._watcher = ModuleWatcher(poll_interval_s)
        self._reloader = HotReloader()
        self._state_store = StateStore()
        self._migration_registry = MigrationRegistry()
        self._rollback_mgr = RollbackManager(self._state_store)
        self._current_versions: Dict[str, int] = {}
        self._state_snapshots: Dict[str, Dict[str, Any]] = {}
        self._auto_reload_thread: Optional[threading.Thread] = None
        self._auto_reload_active = False

    @property
    def watcher(self) -> ModuleWatcher:
        return self._watcher

    @property
    def reloader(self) -> HotReloader:
        return self._reloader

    @property
    def migrations(self) -> MigrationRegistry:
        return self._migration_registry

    def watch_module(self, module_name: str, path: str) -> None:
        self._watcher.watch(module_name, path)

    def unwatch_module(self, module_name: str) -> None:
        self._watcher.unwatch(module_name)

    def register_migration(self, from_version: int, to_version: int,
                           migrate_fn: Callable[[Dict[str, Any]], Dict[str, Any]],
                           description: str = '') -> None:
        self._migration_registry.register(
            Migration(from_version, to_version, migrate_fn, description)
        )

    def set_current_version(self, module_name: str, version: int) -> None:
        self._current_versions[module_name] = version

    def save_state(self, module_name: str, data: Dict[str, Any]) -> StateSnapshot:
        version = self._current_versions.get(module_name, 1)
        self._state_snapshots[module_name] = dict(data)
        return self._rollback_mgr.snapshot_state(module_name, version, data)

    def reload_module(self, module_name: str,
                      migrate_state: bool = True) -> bool:
        old_version = self._current_versions.get(module_name, 1)
        old_state = self._state_snapshots.get(module_name, {})

        success = self._reloader.reload(module_name)
        if not success:
            return False

        if migrate_state and old_state:
            new_version = old_version + 1
            chain = self._migration_registry.chain(old_version, new_version)
            migrated = dict(old_state)
            for mig in chain:
                try:
                    migrated = mig.apply(migrated)
                except Exception:
                    self.rollback_module(module_name, old_version)
                    return False
            self._state_snapshots[module_name] = migrated
            self._current_versions[module_name] = new_version
            self._rollback_mgr.snapshot_state(module_name, new_version, migrated)
        else:
            self._current_versions[module_name] = old_version + 1

        return True

    def rollback_module(self, module_name: str, target_version: int) -> bool:
        def _reload() -> bool:
            return self._reloader.reload(module_name)
        return self._rollback_mgr.rollback(module_name, target_version, _reload)

    def detect_and_reload(self) -> List[str]:
        changed = self._watcher.changed_modules()
        for mod in changed:
            self.reload_module(mod)
        return changed

    def start_auto_reload(self) -> None:
        if self._auto_reload_thread and self._auto_reload_thread.is_alive():
            return
        self._auto_reload_active = True

        def _loop() -> None:
            while self._auto_reload_active:
                try:
                    self.detect_and_reload()
                except Exception:
                    pass
                time.sleep(self._watcher._poll_interval)

        self._auto_reload_thread = threading.Thread(target=_loop, daemon=True)
        self._auto_reload_thread.start()

    def stop_auto_reload(self) -> None:
        self._auto_reload_active = False

    def module_version(self, module_name: str) -> int:
        return self._current_versions.get(module_name, 1)

    def state_summary(self) -> Dict[str, Any]:
        return {
            'watched_modules': list(self._watcher._watch_paths.keys()),
            'current_versions': dict(self._current_versions),
            'auto_reload_active': self._auto_reload_active,
            'reload_count': len(self._reloader.history(9999)),
            'rollback_count': len(self._rollback_mgr.history(9999)),
        }

    def report_text(self) -> str:
        s = self.state_summary()
        return (
            f'Hot Reload Engine\n'
            f'  Watched modules: {s["watched_modules"]}\n'
            f'  Auto-reload: {"active" if s["auto_reload_active"] else "stopped"}\n'
            f'  Reloads: {s["reload_count"]}, Rollbacks: {s["rollback_count"]}'
        )

    def export_artifacts(self, dir: str) -> List[str]:
        os.makedirs(dir, exist_ok=True)
        paths = []
        sp = os.path.join(dir, 'hot_reload.json')
        with open(sp, 'w') as f:
            json.dump(self.state_summary(), f, indent=2)
        paths.append(sp)
        hp = os.path.join(dir, 'hot_reload_history.json')
        with open(hp, 'w') as f:
            json.dump({
                'reloads': self._reloader.history(500),
                'rollbacks': self._rollback_mgr.history(500),
                'watch_events': self._watcher.history(500),
            }, f, indent=2)
        paths.append(hp)
        return paths
