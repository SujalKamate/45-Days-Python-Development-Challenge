"""Checkpointed pipeline — intermediate state snapshots with resume from last successful stage."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, TypeVar
import json
import threading
import time


T = TypeVar('T')


class StageCheckpoint:
    """Captures the output of a pipeline stage for later recovery."""

    def __init__(self, stage_name: str, stage_index: int, data: Any) -> None:
        self.stage_name = stage_name
        self.stage_index = stage_index
        self.data = data
        self.timestamp = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            'stage_name': self.stage_name,
            'stage_index': self.stage_index,
            'data': self.data,
            'timestamp': self.timestamp,
        }

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> StageCheckpoint:
        return StageCheckpoint(
            stage_name=d['stage_name'],
            stage_index=d['stage_index'],
            data=d.get('data'),
        )


class CheckpointStore:
    """Persists pipeline stage outputs to disk for resume capability."""

    def __init__(self, checkpoint_dir: Path) -> None:
        self._dir = checkpoint_dir
        self._dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _path(self, run_id: str, stage_index: int, stage_name: str) -> Path:
        return self._dir / f'{run_id}_{stage_index:04d}_{stage_name}.ckpt'

    def save(self, run_id: str, checkpoint: StageCheckpoint) -> Path:
        path = self._path(run_id, checkpoint.stage_index, checkpoint.stage_name)
        with self._lock:
            path.write_text(json.dumps(checkpoint.to_dict(), default=str), encoding='utf-8')
        return path

    def load(self, run_id: str, stage_index: int, stage_name: str) -> Optional[StageCheckpoint]:
        path = self._path(run_id, stage_index, stage_name)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            return StageCheckpoint.from_dict(data)
        except (json.JSONDecodeError, OSError):
            return None

    def last_checkpoint(self, run_id: str) -> Optional[StageCheckpoint]:
        pattern = f'{run_id}_'
        if not self._dir.exists():
            return None
        candidates: List[Tuple[int, str, Path]] = []
        for f in self._dir.iterdir():
            if f.is_file() and f.stem.startswith(pattern):
                parts = f.stem[len(pattern):].split('_', 1)
                if len(parts) == 2:
                    try:
                        idx = int(parts[0])
                        candidates.append((idx, parts[1], f))
                    except ValueError:
                        continue
        if not candidates:
            return None
        candidates.sort(key=lambda x: -x[0])
        idx, name, path = candidates[0]
        return self.load(run_id, idx, name)

    def clear_run(self, run_id: str) -> None:
        if not self._dir.exists():
            return
        for f in self._dir.iterdir():
            if f.is_file() and f.stem.startswith(run_id):
                f.unlink()

    def clear_all(self) -> None:
        if self._dir.exists():
            for f in self._dir.iterdir():
                if f.is_file():
                    f.unlink()


class CheckpointedPipeline:
    """Multi-stage pipeline that checkpoints between stages for resume.

    On failure, calling ``run()`` again resumes from the last successful
    checkpoint instead of restarting from the beginning.
    """

    def __init__(self, checkpoint_dir: Path, run_id: str = 'default') -> None:
        self._store = CheckpointStore(checkpoint_dir)
        self._run_id = run_id
        self._stages: List[Tuple[str, Callable[[Any], Any]]] = []
        self._lock = threading.Lock()

    def add_stage(self, name: str, fn: Callable[[Any], Any]) -> None:
        self._stages.append((name, fn))

    def run(self, initial_input: Any = None) -> Any:
        resume_from = self._store.last_checkpoint(self._run_id)
        start_index = 0
        current_data = initial_input

        if resume_from is not None:
            start_index = resume_from.stage_index + 1
            current_data = resume_from.data

        for idx in range(start_index, len(self._stages)):
            name, fn = self._stages[idx]
            try:
                current_data = fn(current_data)
                ckpt = StageCheckpoint(name, idx, current_data)
                self._store.save(self._run_id, ckpt)
            except Exception as e:
                raise RuntimeError(f'Stage {name} failed at index {idx}') from e

        self._store.clear_run(self._run_id)
        return current_data

    def reset(self) -> None:
        self._store.clear_run(self._run_id)

    @property
    def last_stage(self) -> Optional[str]:
        ckpt = self._store.last_checkpoint(self._run_id)
        return ckpt.stage_name if ckpt else None


class Stage:
    """A single pipeline stage with a name and transform function."""

    def __init__(self, name: str, fn: Callable[[Any], Any]) -> None:
        self.name = name
        self.fn = fn
