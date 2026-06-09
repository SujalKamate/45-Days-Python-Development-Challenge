"""JSON-depth guard that rejects excessively nested documents before parsing.

Python's ``json.loads`` performs recursive descent — arbitrarily deep
input can trigger stack exhaustion or excessive CPU/memory usage.  This
module pre-scans the raw text to enforce a configurable nesting limit.
"""

import json
from typing import Any, Dict

DEFAULT_MAX_DEPTH = 50


def _scan_depth(text: str) -> int:
    """Return the maximum nesting depth of *text* by scanning braces/brackets.

    Characters inside JSON strings (including escaped quotes) are skipped.
    """
    max_depth = 0
    depth = 0
    in_string = False
    escape = False
    for ch in text:
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch in ("{", "["):
            depth += 1
            if depth > max_depth:
                max_depth = depth
        elif ch in ("}", "]"):
            depth -= 1
            if depth < 0:
                depth = 0  # malformed but don't crash the scanner
    return max_depth


def safe_json_loads(
    text: str,
    max_depth: int = DEFAULT_MAX_DEPTH,
) -> Dict[str, Any]:
    """Parse *text* as JSON, rejecting documents deeper than *max_depth*.

    Raises ``ValueError`` when the nesting limit is exceeded; otherwise
    delegates to ``json.loads``.
    """
    actual_depth = _scan_depth(text)
    if actual_depth > max_depth:
        raise ValueError(
            f"JSON nesting depth {actual_depth} exceeds limit of {max_depth}"
        )
    return json.loads(text)
