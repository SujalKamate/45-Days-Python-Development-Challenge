"""Statistical sample-size validation.

Ensures that descriptive statistics are never computed on datasets
too small to produce mathematically meaningful results.
"""

from typing import Any, Dict, List


MIN_FOR_STDEV = 2  # population stdev requires at least 2 elements
MIN_FOR_MEDIAN = 1
MIN_FOR_MODE = 1


def validate_sample_size(values: List[Any], min_samples: int, name: str = "dataset") -> None:
    """Raise ``ValueError`` if *values* has fewer than *min_samples* items.

    The empty-list check is explicit (not truthiness-based) so that
    callers can distinguish "empty" from "insufficient".
    """
    if len(values) == 0:
        raise ValueError(f"{name} is empty — at least {min_samples} element(s) required")
    if len(values) < min_samples:
        raise ValueError(
            f"{name} has {len(values)} element(s); "
            f"at least {min_samples} required"
        )


def safe_stdev(values: List[float]) -> float:
    """Population standard deviation (validated minimum 2 elements)."""
    validate_sample_size(values, MIN_FOR_STDEV, "values")
    import statistics
    return statistics.pstdev(values)


def safe_mean(values: List[float]) -> float:
    """Arithmetic mean (validated non-empty)."""
    validate_sample_size(values, 1, "values")
    import statistics
    return statistics.mean(values)
