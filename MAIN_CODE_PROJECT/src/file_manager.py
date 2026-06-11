"""Explicit file resource lifecycle management.

Provides context-manager-guaranteed file I/O to prevent descriptor
leaks during repeated batch operations.
"""

from pathlib import Path
from typing import Any, Dict
import json


class FileManager:
    """File I/O with explicit resource lifecycle via context managers.

    All methods use ``with open(...) as f:`` internally so file descriptors
    are released immediately after each operation, even if an exception is
    raised.
    """

    # ── JSON ────────────────────────────────────────────────────────────

    @staticmethod
    def write_json(path: Path, payload: Dict[str, Any]) -> None:
        with path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, default=str)

    @staticmethod
    def read_json(path: Path) -> Dict[str, Any]:
        if not path.exists():
            return {}
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)

    # ── Plain text ──────────────────────────────────────────────────────

    @staticmethod
    def write_text(path: Path, content: str) -> None:
        with path.open("w", encoding="utf-8") as f:
            f.write(content)

    @staticmethod
    def read_text(path: Path) -> str:
        if not path.exists():
            return ""
        with path.open("r", encoding="utf-8") as f:
            return f.read()
