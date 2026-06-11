"""Guards against unreasonably large numeric inputs.

Prevents memory exhaustion from astronomical integers, float overflow,
and runaway exponentiation in calculator-style operations.
"""

from typing import Union
import math

# Maximum absolute value allowed for practical numeric operations.
# 1e12 is large enough for any realistic financial/scientific computation
# while staying well within float64's exact-representation range.
MAX_MAGNITUDE = 10_000_000_000_000  # 1e13 — 14 digits
MAX_DIGITS = 15                     # characters allowed before a numeric conversion


def guard_numeric(value: str, max_digits: int = MAX_DIGITS) -> str:
    """Raise ``ValueError`` if *value* is unreasonably large.

    Checks both the string length and (for decimal/floating inputs) the
    magnitude of the number.
    """
    stripped = value.strip()
    if not stripped:
        raise ValueError("empty numeric input")
    # Strip leading sign for length check
    body = stripped.lstrip("-+")
    if len(body) > max_digits:
        raise ValueError(
            f"numeric input too long ({len(body)} digits, limit {max_digits})"
        )
    return stripped


def safe_int(value: str, max_digits: int = MAX_DIGITS) -> int:
    """Parse *value* as ``int``, rejecting inputs that exceed *max_digits*."""
    cleaned = guard_numeric(value, max_digits)
    result = int(cleaned)
    if abs(result) > MAX_MAGNITUDE:
        raise ValueError(f"integer {result} exceeds magnitude limit {MAX_MAGNITUDE}")
    return result


def safe_float(value: str, max_digits: int = MAX_DIGITS) -> float:
    """Parse *value* as ``float``, rejecting overflow/underflow risks."""
    cleaned = guard_numeric(value, max_digits)
    result = float(cleaned)
    if math.isinf(result) or math.isnan(result):
        raise ValueError(f"float overflow from input {cleaned!r}")
    if abs(result) > MAX_MAGNITUDE:
        raise ValueError(f"float {result} exceeds magnitude limit {MAX_MAGNITUDE}")
    return result


def guard_power(base: float, exponent: float) -> None:
    """Raise ``ValueError`` if ``base ** exponent`` would be excessive."""
    if exponent > 100:
        raise ValueError(f"exponent {exponent} exceeds limit of 100")
    if abs(base) > 1_000_000 and exponent > 10:
        raise ValueError(
            f"large base ({base}) with exponent {exponent} is not allowed"
        )
