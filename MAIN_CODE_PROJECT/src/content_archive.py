"""Content-addressable state archival with deduplication and delta compression."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Set
import hashlib
import json
import os
import threading
import zlib


def _hash_content(data: Dict[str, Any]) -> str:
    canonical = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def _compress(data: Dict[str, Any]) -> bytes:
    raw = json.dumps(data, sort_keys=True, default=str).encode('utf-8')
    return zlib.compress(raw, level=6)


def _decompress(raw: bytes) -> Dict[str, Any]:
    return json.loads(zlib.decompress(raw).decode('utf-8'))


class ArchiveIndex:
    """Tracks snapshot hashes and their relationships for dedup and GC."""

    def __init__(self, index_path: Path) -> None:
        self._path = index_path
        self._lock = threading.Lock()
        self._snapshots: Dict[str, str] = {}  # label -> content_hash
        self._refcounts: Dict[str, int] = {}   # content_hash -> ref count
        self._deltas: Dict[str, str] = {}      # label -> delta_hash
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            try:
                data = json.loads(self._path.read_text(encoding='utf-8'))
                self._snapshots = data.get('snapshots', {})
                self._refcounts = data.get('refcounts', {})
                self._deltas = data.get('deltas', {})
            except (json.JSONDecodeError, OSError):
                pass

    def _save(self) -> None:
        data = {
            'snapshots': self._snapshots,
            'refcounts': self._refcounts,
            'deltas': self._deltas,
        }
        self._path.write_text(json.dumps(data, indent=2), encoding='utf-8')

    def register(self, label: str, content_hash: str) -> bool:
        with self._lock:
            old_hash = self._snapshots.get(label)
            if old_hash == content_hash:
                return False
            if old_hash:
                self._refcounts[old_hash] = max(0, self._refcounts.get(old_hash, 1) - 1)
            self._snapshots[label] = content_hash
            self._refcounts[content_hash] = self._refcounts.get(content_hash, 0) + 1
            self._save()
            return True

    def register_delta(self, label: str, delta_hash: str) -> None:
        with self._lock:
            self._deltas[label] = delta_hash
            self._save()

    def get_hash(self, label: str) -> Optional[str]:
        return self._snapshots.get(label)

    def get_delta_hash(self, label: str) -> Optional[str]:
        return self._deltas.get(label)

    def unreferenced_hashes(self) -> Set[str]:
        with self._lock:
            all_hashes = set(self._refcounts.keys())
            referenced = {h for h, c in self._refcounts.items() if c > 0}
            return all_hashes - referenced

    def snapshot_labels(self) -> List[str]:
        return list(self._snapshots.keys())


class ContentArchive:
    """Deduplicated, content-addressable snapshot storage with delta compression."""

    def __init__(self, archive_dir: Path) -> None:
        self._dir = archive_dir
        self._dir.mkdir(parents=True, exist_ok=True)
        self._blobs_dir = self._dir / 'blobs'
        self._blobs_dir.mkdir(exist_ok=True)
        self._deltas_dir = self._dir / 'deltas'
        self._deltas_dir.mkdir(exist_ok=True)
        self._index = ArchiveIndex(self._dir / 'index.json')
        self._lock = threading.Lock()

    def _blob_path(self, content_hash: str) -> Path:
        return self._blobs_dir / f'{content_hash}.zlib'

    def _delta_path(self, delta_hash: str) -> Path:
        return self._deltas_dir / f'{delta_hash}.zlib'

    def store(self, label: str, data: Dict[str, Any]) -> str:
        content_hash = _hash_content(data)
        changed = self._index.register(label, content_hash)
        if changed:
            blob_path = self._blob_path(content_hash)
            if not blob_path.exists():
                blob_path.write_bytes(_compress(data))
        return content_hash

    def load(self, label: str) -> Dict[str, Any]:
        content_hash = self._index.get_hash(label)
        if not content_hash:
            return {}
        blob_path = self._blob_path(content_hash)
        if not blob_path.exists():
            return {}
        return _decompress(blob_path.read_bytes())

    def store_delta(self, label: str, base_label: str, data: Dict[str, Any]) -> str:
        base = self.load(base_label)
        delta = self._compute_delta(base, data)
        delta_hash = _hash_content(delta)
        delta_path = self._delta_path(delta_hash)
        if not delta_path.exists():
            delta_path.write_bytes(_compress(delta))
        self._index.register_delta(label, delta_hash)
        full_hash = self.store(label, data)
        return delta_hash

    def load_delta(self, label: str, base_label: str) -> Dict[str, Any]:
        delta_hash = self._index.get_delta_hash(label)
        base = self.load(base_label)
        if not delta_hash:
            return base
        delta_path = self._delta_path(delta_hash)
        if not delta_path.exists():
            return base
        delta = _decompress(delta_path.read_bytes())
        return self._apply_delta(base, delta)

    @staticmethod
    def _compute_delta(base: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
        delta: Dict[str, Any] = {}
        all_keys = set(base.keys()) | set(new.keys())
        for k in sorted(all_keys):
            if k not in new:
                delta[k] = {'__type__': 'delete'}
            elif k not in base:
                delta[k] = {'__type__': 'add', 'value': new[k]}
            elif base[k] != new[k]:
                delta[k] = {'__type__': 'modify', 'old': base[k], 'new': new[k]}
        return delta

    @staticmethod
    def _apply_delta(base: Dict[str, Any], delta: Dict[str, Any]) -> Dict[str, Any]:
        result = dict(base)
        for k, v in delta.items():
            if not isinstance(v, dict) or '__type__' not in v:
                result[k] = v
                continue
            t = v['__type__']
            if t == 'delete':
                result.pop(k, None)
            elif t == 'add':
                result[k] = v['value']
            elif t == 'modify':
                result[k] = v['new']
        return result

    def gc(self) -> int:
        unreferenced = self._index.unreferenced_hashes()
        count = 0
        for h in unreferenced:
            bp = self._blob_path(h)
            if bp.exists():
                bp.unlink()
                count += 1
        all_deltas = list(self._deltas_dir.glob('*.zlib'))
        known_delta_hashes = set()
        for label in self._index.snapshot_labels():
            dh = self._index.get_delta_hash(label)
            if dh:
                known_delta_hashes.add(dh)
        for dp in all_deltas:
            dh = dp.stem
            if dh not in known_delta_hashes:
                dp.unlink()
                count += 1
        return count

    def list_snapshots(self) -> List[str]:
        return self._index.snapshot_labels()
