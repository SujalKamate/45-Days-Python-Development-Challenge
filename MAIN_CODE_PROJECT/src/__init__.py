"""src package — ensures source modules are importable from any working directory."""

from __future__ import annotations

import sys
from pathlib import Path

_src_path = str(Path(__file__).parent.resolve())
if _src_path not in sys.path:
    sys.path.insert(0, _src_path)

from .dependency_registry import registry
from . import contracts
