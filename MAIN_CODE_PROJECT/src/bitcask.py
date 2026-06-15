"""Bitcask append-only key-value storage with in-memory hash index, hint files, and compaction."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
import hashlib
import json
import os
import struct
import threading
import time
from pathlib import Path


_CRC_SIZE = 4
_TS_SIZE = 8
_KEYLEN_SIZE = 4
_VALLEN_SIZE = 4
_HEADER_SIZE = _CRC_SIZE + _TS_SIZE + _KEYLEN_SIZE + _VALLEN_SIZE
_TOMBSTONE_VALUE = b''
_MAX_ACTIVE_SIZE = 64 * 1024 * 1024


def _crc32(data: bytes) -> int:
    return hashlib.sha256(data).digest()[:4]


def _pack_value(value: Any) -> bytes:
    return json.dumps(value, default=str).encode('utf-8')


def _unpack_value(data: bytes) -> Any:
    return json.loads(data.decode('utf-8'))


class BitcaskRecord:
    def __init__(self, file_id: str, offset: int, size: int, timestamp: float) -> None:
        self.file_id = file_id
        self.offset = offset
        self.size = size
        self.timestamp = timestamp


class Bitcask:
    """Append-only key-value store with in-memory hash index and compaction."""

    def __init__(self, base_dir: str | Path = 'bitcask_data',
                 max_active_size: int = _MAX_ACTIVE_SIZE) -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.max_active_size = max_active_size
        self._index: Dict[str, BitcaskRecord] = {}
        self._active_file_id: str = self._next_file_id()
        self._active_file: Optional[Any] = None
        self._active_offset: int = 0
        self._data_files: Dict[str, Any] = {}
        self._lock = threading.Lock()
        self._stats: Dict[str, Any] = {
            'puts': 0, 'gets': 0, 'deletes': 0, 'merges': 0,
            'data_files': 0, 'stale_bytes': 0,
        }
        self._recover()

    def _next_file_id(self) -> str:
        ts = int(time.time() * 1000)
        return f'{ts:x}'

    def _data_path(self, file_id: str) -> Path:
        return self.base_dir / f'{file_id}.data'

    def _hint_path(self, file_id: str) -> Path:
        return self.base_dir / f'{file_id}.hint'

    def _open_active(self) -> Any:
        path = self._data_path(self._active_file_id)
        return open(path, 'ab')

    def put(self, key: str, value: Any) -> None:
        with self._lock:
            self._put_internal(key, value)
            self._stats['puts'] += 1

    def _put_internal(self, key: str, value: Any) -> None:
        if self._active_file is None:
            self._active_file = self._open_active()
        ts = time.time()
        val_bytes = _pack_value(value)
        key_bytes = key.encode('utf-8')
        crc = _crc32(key_bytes + val_bytes)
        header = struct.pack('!I d I I', crc, ts, len(key_bytes), len(val_bytes))
        record = header + key_bytes + val_bytes
        self._active_file.write(record)
        self._active_offset += len(record)
        if self._active_offset >= self.max_active_size:
            self._active_file.close()
            self._active_file = None
            hint_path = self._hint_path(self._active_file_id)
            self._write_hint_file(self._active_file_id, hint_path)
            self._active_file_id = self._next_file_id()
            self._active_offset = 0
        self._index[key] = BitcaskRecord(
            self._active_file_id, self._active_offset - len(record), len(record), ts)

    def get(self, key: str) -> Any:
        with self._lock:
            self._stats['gets'] += 1
            rec = self._index.get(key)
            if rec is None:
                return None
            path = self._data_path(rec.file_id)
            if not path.exists():
                return None
            with open(path, 'rb') as f:
                f.seek(rec.offset)
                raw = f.read(rec.size)
            if len(raw) < _HEADER_SIZE:
                return None
            crc_stored, ts, klen, vlen = struct.unpack('!I d I I', raw[:_HEADER_SIZE])
            payload = raw[_HEADER_SIZE:]
            key_bytes = payload[:klen]
            val_bytes = payload[klen:klen + vlen]
            if _crc32(key_bytes + val_bytes) != crc_stored:
                return None
            if val_bytes == _TOMBSTONE_VALUE:
                return None
            return _unpack_value(val_bytes)

    def delete(self, key: str) -> bool:
        with self._lock:
            if key not in self._index:
                return False
            self._put_internal(key, None)
            del self._index[key]
            self._stats['deletes'] += 1
            return True

    def merge(self) -> None:
        with self._lock:
            file_ids = sorted(set(
                rec.file_id for rec in self._index.values()
                if rec.file_id != self._active_file_id))
            if not file_ids:
                return
            merge_file_id = self._next_file_id() + '_merged'
            merge_path = self._data_path(merge_file_id)
            merge_hint = self._hint_path(merge_file_id)
            merged_index: Dict[str, BitcaskRecord] = {}
            offset = 0
            with open(merge_path, 'wb') as mf:
                for key, rec in self._index.items():
                    if rec.file_id == self._active_file_id:
                        merged_index[key] = rec
                        continue
                    src_path = self._data_path(rec.file_id)
                    if not src_path.exists():
                        continue
                    with open(src_path, 'rb') as sf:
                        sf.seek(rec.offset)
                        raw = sf.read(rec.size)
                    ts = time.time()
                    key_bytes = key.encode('utf-8')
                    val_bytes = raw[_HEADER_SIZE + len(key_bytes):]
                    crc = _crc32(key_bytes + val_bytes)
                    header = struct.pack('!I d I I', crc, ts, len(key_bytes), len(val_bytes))
                    record = header + key_bytes + val_bytes
                    mf.write(record)
                    merged_index[key] = BitcaskRecord(merge_file_id, offset, len(record), ts)
                    offset += len(record)
            self._write_hint_file(merge_file_id, merge_hint)
            for fid in file_ids:
                dp = self._data_path(fid)
                hp = self._hint_path(fid)
                if dp.exists():
                    dp.unlink()
                if hp.exists():
                    hp.unlink()
            self._index.update(merged_index)
            self._stats['merges'] += 1

    def _write_hint_file(self, file_id: str, path: Path) -> None:
        entries = [(key, rec) for key, rec in self._index.items() if rec.file_id == file_id]
        with open(path, 'wb') as f:
            for key, rec in entries:
                key_bytes = key.encode('utf-8')
                hint = struct.pack('!I d I', _crc32(key_bytes), rec.timestamp, len(key_bytes))
                f.write(hint + key_bytes + struct.pack('!Q I', rec.offset, rec.size))

    def _recover(self) -> None:
        files = sorted(self.base_dir.glob('*.data'))
        for data_path in files:
            fid = data_path.stem
            hint_path = self._hint_path(fid)
            if hint_path.exists():
                self._load_hint_file(fid, hint_path)
            else:
                self._scan_data_file(fid, data_path)
            self._data_files[fid] = data_path
        self._stats['data_files'] = len(self._data_files)
        if not self._active_file_id:
            self._active_file_id = self._next_file_id()

    def _load_hint_file(self, file_id: str, path: Path) -> None:
        with open(path, 'rb') as f:
            while True:
                raw = f.read(_CRC_SIZE + _TS_SIZE + _KEYLEN_SIZE)
                if len(raw) < _CRC_SIZE + _TS_SIZE + _KEYLEN_SIZE:
                    break
                hint_crc, ts, klen = struct.unpack('!I d I', raw)
                key_bytes = f.read(klen)
                if len(key_bytes) < klen:
                    break
                loc_raw = f.read(12)
                if len(loc_raw) < 12:
                    break
                offset, size = struct.unpack('!Q I', loc_raw)
                if _crc32(key_bytes) == hint_crc:
                    key = key_bytes.decode('utf-8')
                    self._index[key] = BitcaskRecord(file_id, offset, size, ts)

    def _scan_data_file(self, file_id: str, path: Path) -> None:
        with open(path, 'rb') as f:
            offset = 0
            while True:
                raw = f.read(_HEADER_SIZE)
                if len(raw) < _HEADER_SIZE:
                    break
                crc_stored, ts, klen, vlen = struct.unpack('!I d I I', raw)
                payload = f.read(klen + vlen)
                if len(payload) < klen + vlen:
                    break
                key_bytes = payload[:klen]
                val_bytes = payload[klen:klen + vlen]
                if _crc32(key_bytes + val_bytes) == crc_stored:
                    key = key_bytes.decode('utf-8')
                    total = _HEADER_SIZE + klen + vlen
                    if val_bytes == _TOMBSTONE_VALUE:
                        self._index.pop(key, None)
                    else:
                        self._index[key] = BitcaskRecord(file_id, offset, total, ts)
                offset += _HEADER_SIZE + klen + vlen

    def sync(self) -> None:
        with self._lock:
            if self._active_file:
                self._active_file.flush()
                os.fsync(self._active_file.fileno())

    def metrics(self) -> Dict[str, Any]:
        with self._lock:
            return {
                'puts': self._stats['puts'],
                'gets': self._stats['gets'],
                'deletes': self._stats['deletes'],
                'merges': self._stats['merges'],
                'data_files': len(self._data_files),
                'index_size': len(self._index),
                'active_file_id': self._active_file_id,
            }

    def close(self) -> None:
        with self._lock:
            if self._active_file:
                self._active_file.close()
                self._active_file = None


class BitcaskEngine:
    """Top-level engine managing multiple Bitcask instances."""

    def __init__(self) -> None:
        self._stores: Dict[str, Bitcask] = {}
        self._default_store: Optional[Bitcask] = None
        self._lock = threading.Lock()

    def create(self, name: str = 'default', base_dir: str = 'bitcask_data',
               max_active_size: int = _MAX_ACTIVE_SIZE) -> Bitcask:
        store = Bitcask(str(Path(base_dir) / name), max_active_size)
        with self._lock:
            self._stores[name] = store
            if name == 'default':
                self._default_store = store
        return store

    def get(self, name: str = 'default') -> Bitcask:
        with self._lock:
            if name in self._stores:
                return self._stores[name]
            if self._default_store is None:
                self._default_store = self.create()
            return self._default_store

    def remove(self, name: str) -> bool:
        with self._lock:
            if name in self._stores:
                self._stores[name].close()
                del self._stores[name]
                if name == 'default':
                    self._default_store = None
                return True
            return False

    def list(self) -> List[str]:
        with self._lock:
            return list(self._stores.keys())

    def put(self, key: str, value: Any, name: str = 'default') -> None:
        self.get(name).put(key, value)

    def get_value(self, key: str, name: str = 'default') -> Any:
        return self.get(name).get(key)

    def delete(self, key: str, name: str = 'default') -> bool:
        return self.get(name).delete(key)

    def merge(self, name: str = 'default') -> None:
        self.get(name).merge()

    def sync(self, name: str = 'default') -> None:
        self.get(name).sync()

    def metrics(self, name: str = 'default') -> Dict[str, Any]:
        return self.get(name).metrics()

    def close(self, name: str = 'default') -> None:
        self.get(name).close()

    def summary(self) -> Dict[str, Any]:
        with self._lock:
            return {
                'store_count': len(self._stores),
                'store_names': list(self._stores.keys()),
            }
