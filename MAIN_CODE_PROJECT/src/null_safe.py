"""Explicit null-safe numeric conversion — missing values stay missing.

``safe_int(None)`` returns ``None`` (not ``0``), preserving the semantic
distinction between "no value" and "value is zero".
"""

from typing import Optional


def null_safe_int(value: object) -> Optional[int]:
    """Return ``None`` for missing/empty/invalid input, else ``int``.

    ``None``, empty strings, and whitespace-only strings produce ``None``
    rather than a fallback zero.
    """
    if value is None:
        return None
    try:
        stripped = str(value).strip()
    except Exception:
        return None
    if not stripped:
        return None
    try:
        return int(stripped)
    except (ValueError, TypeError):
        return None


def null_safe_float(value: object) -> Optional[float]:
    """Return ``None`` for missing/empty/invalid input, else ``float``."""
    if value is None:
        return None
    try:
        stripped = str(value).strip()
    except Exception:
        return None
    if not stripped:
        return None
    try:
        return float(stripped)
    except (ValueError, TypeError):
        return None
