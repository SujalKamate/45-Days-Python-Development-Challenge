"""Exact decimal arithmetic for financial values.

Replaces IEEE 754 ``float`` with ``decimal.Decimal`` (configurable
precision, default 2 decimal places) to prevent rounding drift in
monetary calculations.
"""

from decimal import Decimal, ROUND_HALF_EVEN
from typing import Union

PRECISION = Decimal("0.01")  # two decimal places


def safe_decimal(value: Union[str, int, float, Decimal], rounding: bool = True) -> Decimal:
    """Convert *value* to a :class:`Decimal` with two-place precision.

    ``float`` inputs are converted via string to avoid float → Decimal
    representation artefacts (e.g. ``Decimal(0.1)`` → ``0.10000000000000000555``).
    """
    if isinstance(value, float):
        d = Decimal(str(value))
    elif isinstance(value, Decimal):
        d = value
    else:
        d = Decimal(value)
    if rounding:
        d = d.quantize(PRECISION, rounding=ROUND_HALF_EVEN)
    return d


class Money:
    """Immutable monetary amount with exact decimal arithmetic.

    All arithmetic operators return new ``Money`` instances, preserving
    two-decimal-place precision.
    """

    __slots__ = ("_amount",)

    def __init__(self, value: Union[str, int, float, Decimal]) -> None:
        self._amount = safe_decimal(value)

    @property
    def amount(self) -> Decimal:
        return self._amount

    def __add__(self, other: "Money") -> "Money":
        if not isinstance(other, Money):
            return NotImplemented
        return Money(self._amount + other._amount)

    def __sub__(self, other: "Money") -> "Money":
        if not isinstance(other, Money):
            return NotImplemented
        return Money(self._amount - other._amount)

    def __mul__(self, factor: Union[int, float, Decimal]) -> "Money":
        if isinstance(factor, Money):
            return NotImplemented
        return Money(self._amount * safe_decimal(factor, rounding=False))

    def __truediv__(self, factor: Union[int, float, Decimal]) -> "Money":
        if isinstance(factor, Money):
            return NotImplemented
        return Money(self._amount / safe_decimal(factor, rounding=False))

    def __repr__(self) -> str:
        return f"${self._amount:.2f}"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        return self._amount == other._amount
