"""src package — makes all source modules importable from any working directory.

Ensures that direct imports (``from base_app import ...``) used by the 50
source modules resolve correctly regardless of the current working directory
or ``sys.path`` configuration at interpreter startup.
"""

from __future__ import annotations

import sys
from pathlib import Path

_src_path = str(Path(__file__).parent.resolve())
if _src_path not in sys.path:
    sys.path.insert(0, _src_path)

from .dependency_registry import registry
from . import contracts
