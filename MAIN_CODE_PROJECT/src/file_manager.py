"""Transactional file persistence with cross-platform atomic writes.

Write operations stage content to a ``.tmp`` sibling file, then
atomically replace the target via :func:`os.replace`.  This prevents
partial/corrupt state files if the process is interrupted mid-write.
"""

from pathlib import Path
from typing import Any, Dict
import json
import os


class FileManager:
    """File I/O with transactional (atomic) write semantics."""

    # ── JSON ────────────────────────────────────────────────────────────

    @staticmethod
    def write_json(path: Path, payload: Dict[str, Any]) -> None:
        tmp = path.with_suffix(path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, default=str)
        os.replace(tmp, path)

    @staticmethod
    def read_json(path: Path) -> Dict[str, Any]:
        if not path.exists():
            return {}
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)

    # ── Plain text ──────────────────────────────────────────────────────

    @staticmethod
    def write_text(path: Path, content: str) -> None:
        tmp = path.with_suffix(path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp, path)

    @staticmethod
    def read_text(path: Path) -> str:
        if not path.exists():
            return ""
        with path.open("r", encoding="utf-8") as f:
            return f.read()
