"""Separates persistent business data from transient runtime metadata.

Usage:
    mgr = StateManager()
    mgr.persistent.records['key'] = value  # survives export
    mgr.transient.runs += 1                # never exported
    mgr.export()                           # returns only persistent data
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List


@dataclass
class TransientState:
    """Runtime metadata — resets between sessions, never exported."""
    history: List[str] = field(default_factory=list)
    flags: Dict[str, bool] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    runs: int = 0
    errors: int = 0


@dataclass
class PersistentState:
    """Business data that survives export — the meaningful output."""
    records: Dict[str, Any] = field(default_factory=dict)


class StateManager:
    """Owns both transient and persistent state. Export only emits persistent data."""

    def __init__(self) -> None:
        self.transient = TransientState()
        self.persistent = PersistentState()

    def export(self) -> Dict[str, Any]:
        return {'records': dict(self.persistent.records)}
