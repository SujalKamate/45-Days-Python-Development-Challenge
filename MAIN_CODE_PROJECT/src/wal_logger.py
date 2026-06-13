"""Write-Ahead Log (WAL) with ARIES-style crash recovery for durable state management."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import hashlib
import json
import os
import threading


LSN_BEGIN = 'BEGIN'
LSN_UPDATE = 'UPDATE'
LSN_COMMIT = 'COMMIT'
LSN_ROLLBACK = 'ROLLBACK'
LSN_CHECKPOINT = 'CHECKPOINT'


@dataclass
class WALEntry:
    lsn: int
    prev_lsn: int
    txn_id: str
    entry_type: str
    key: str = ''
    old_value: Any = None
    new_value: Any = None
    checksum: str = ''

    def compute_checksum(self) -> str:
        raw = json.dumps({
            'lsn': self.lsn,
            'prev_lsn': self.prev_lsn,
            'txn_id': self.txn_id,
            'entry_type': self.entry_type,
            'key': self.key,
            'old_value': self.old_value,
            'new_value': self.new_value,
        }, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode('utf-8')).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            'lsn': self.lsn,
            'prev_lsn': self.prev_lsn,
            'txn_id': self.txn_id,
            'entry_type': self.entry_type,
            'key': self.key,
            'old_value': self.old_value,
            'new_value': self.new_value,
            'checksum': self.checksum,
        }

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> WALEntry:
        return WALEntry(
            lsn=d['lsn'],
            prev_lsn=d.get('prev_lsn', 0),
            txn_id=d.get('txn_id', ''),
            entry_type=d.get('entry_type', ''),
            key=d.get('key', ''),
            old_value=d.get('old_value'),
            new_value=d.get('new_value'),
            checksum=d.get('checksum', ''),
        )


class WALogger:
    """Write-ahead logger that records mutations before they are applied.

    ARIES-style recovery:
      - REDO: replay all committed transactions forwards
      - UNDO: roll back all incomplete (no COMMIT) transactions backwards
      - CHECKPOINT: snapshot state + earliest active LSN for log truncation
    """

    def __init__(self, log_dir: Path, namespace: str = 'wal') -> None:
        self._log_dir = log_dir
        self._namespace = namespace
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._lsn_counter = 0
        self._active_txns: Dict[str, int] = {}
        self._entries: List[WALEntry] = []
        self._next_flush_lsn = 0
        self._checkpoint_lsn = 0

    @property
    def log_path(self) -> Path:
        return self._log_dir / f'{self._namespace}.wal'

    def _next_lsn(self) -> int:
        self._lsn_counter += 1
        return self._lsn_counter

    def begin_txn(self, txn_id: str) -> int:
        with self._lock:
            lsn = self._next_lsn()
            entry = WALEntry(
                lsn=lsn,
                prev_lsn=self._active_txns.get(txn_id, 0),
                txn_id=txn_id,
                entry_type=LSN_BEGIN,
            )
            entry.checksum = entry.compute_checksum()
            self._entries.append(entry)
            self._active_txns[txn_id] = lsn
            self._flush_entry(entry)
            return lsn

    def log_update(self, txn_id: str, key: str, old_value: Any, new_value: Any) -> int:
        with self._lock:
            lsn = self._next_lsn()
            entry = WALEntry(
                lsn=lsn,
                prev_lsn=self._active_txns.get(txn_id, 0),
                txn_id=txn_id,
                entry_type=LSN_UPDATE,
                key=key,
                old_value=old_value,
                new_value=new_value,
            )
            entry.checksum = entry.compute_checksum()
            self._entries.append(entry)
            self._active_txns[txn_id] = lsn
            self._flush_entry(entry)
            return lsn

    def commit_txn(self, txn_id: str) -> int:
        with self._lock:
            lsn = self._next_lsn()
            entry = WALEntry(
                lsn=lsn,
                prev_lsn=self._active_txns.get(txn_id, 0),
                txn_id=txn_id,
                entry_type=LSN_COMMIT,
            )
            entry.checksum = entry.compute_checksum()
            self._entries.append(entry)
            self._active_txns.pop(txn_id, None)
            self._flush_entry(entry)
            return lsn

    def rollback_txn(self, txn_id: str) -> int:
        with self._lock:
            lsn = self._next_lsn()
            entry = WALEntry(
                lsn=lsn,
                prev_lsn=self._active_txns.get(txn_id, 0),
                txn_id=txn_id,
                entry_type=LSN_ROLLBACK,
            )
            entry.checksum = entry.compute_checksum()
            self._entries.append(entry)
            self._active_txns.pop(txn_id, None)
            self._flush_entry(entry)
            return lsn

    def write_checkpoint(self, state_snapshot: Dict[str, Any]) -> int:
        with self._lock:
            lsn = self._next_lsn()
            entry = WALEntry(
                lsn=lsn,
                prev_lsn=0,
                txn_id='',
                entry_type=LSN_CHECKPOINT,
                new_value=state_snapshot,
            )
            entry.checksum = entry.compute_checksum()
            self._entries.append(entry)
            self._checkpoint_lsn = lsn
            self._flush_entry(entry)
            self._truncate_log()
            return lsn

    def _flush_entry(self, entry: WALEntry) -> None:
        """Append entry to WAL file (write-ahead: flush before state apply)."""
        line = json.dumps(entry.to_dict(), default=str) + '\n'
        with self.log_path.open('a', encoding='utf-8') as f:
            f.write(line)
            f.flush()
            os.fsync(f.fileno())

    @staticmethod
    def _verify_entry(entry: WALEntry) -> bool:
        if entry.entry_type == LSN_CHECKPOINT:
            return True
        return entry.checksum == entry.compute_checksum()

    def _load_entries(self) -> List[WALEntry]:
        if not self.log_path.exists():
            return []
        entries: List[WALEntry] = []
        with self.log_path.open('r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                    entry = WALEntry.from_dict(d)
                    entries.append(entry)
                except (json.JSONDecodeError, KeyError):
                    continue
        return entries

    def recover(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """ARIES recovery: REDO committed, UNDO incomplete, return recovered state."""
        entries = self._load_entries()
        if not entries:
            return state

        committed_txns: set[str] = set()
        incomplete_txns: set[str] = set()
        checkpoint_state: Optional[Dict[str, Any]] = None

        for entry in entries:
            if not self._verify_entry(entry):
                continue
            if entry.entry_type == LSN_CHECKPOINT:
                if isinstance(entry.new_value, dict):
                    checkpoint_state = entry.new_value
                committed_txns.clear()
                incomplete_txns.clear()
            elif entry.entry_type == LSN_BEGIN:
                incomplete_txns.add(entry.txn_id)
            elif entry.entry_type == LSN_COMMIT:
                incomplete_txns.discard(entry.txn_id)
                committed_txns.add(entry.txn_id)
            elif entry.entry_type == LSN_ROLLBACK:
                incomplete_txns.discard(entry.txn_id)

        if checkpoint_state is not None:
            result = dict(checkpoint_state)
        else:
            result = dict(state)

        committed_updates: List[WALEntry] = [
            e for e in entries
            if e.entry_type == LSN_UPDATE
            and e.txn_id in committed_txns
            and self._verify_entry(e)
        ]
        for entry in committed_updates:
            result[entry.key] = entry.new_value

        incomplete_updates: List[WALEntry] = [
            e for e in reversed(entries)
            if e.entry_type == LSN_UPDATE
            and e.txn_id in incomplete_txns
            and self._verify_entry(e)
        ]
        seen_keys: set[str] = set()
        for entry in incomplete_updates:
            if entry.key not in seen_keys:
                seen_keys.add(entry.key)
                if entry.old_value is not None or entry.key in result:
                    result[entry.key] = entry.old_value
                else:
                    result.pop(entry.key, None)

        committed_txns_list = sorted(committed_txns)
        for txn_id in incomplete_txns:
            self._append_rollback(txn_id)

        return result

    def _append_rollback(self, txn_id: str) -> None:
        entry = WALEntry(
            lsn=self._next_lsn(),
            prev_lsn=self._active_txns.get(txn_id, 0),
            txn_id=txn_id,
            entry_type=LSN_ROLLBACK,
        )
        entry.checksum = entry.compute_checksum()
        self._flush_entry(entry)

    def _truncate_log(self) -> None:
        if not self.log_path.exists():
            return
        entries = self._load_entries()
        keep_entries = [
            e for e in entries
            if e.lsn >= self._checkpoint_lsn
        ]
        if len(keep_entries) == len(entries):
            return
        with self.log_path.open('w', encoding='utf-8') as f:
            for entry in keep_entries:
                f.write(json.dumps(entry.to_dict(), default=str) + '\n')
                f.flush()

    def close(self) -> None:
        pass
