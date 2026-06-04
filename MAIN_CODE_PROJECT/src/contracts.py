"""Isolated shared contracts preventing circular import dependencies.

Modules depend on these abstract contracts rather than on concrete
module implementations, eliminating circular import risk.
"""

from typing import Any, Dict, List, Protocol, runtime_checkable


@runtime_checkable
class DataProvider(Protocol):
    """Contract for modules that can provide sample data."""

    def demo_data(self) -> List[Dict[str, Any]]:
        ...


@runtime_checkable
class DataProcessor(Protocol):
    """Contract for modules that can process datasets."""

    def process_dataset(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        ...


@runtime_checkable
class AppRunner(Protocol):
    """Contract for modules with an executable workflow."""

    def run(self) -> None:
        ...


@runtime_checkable
class Stateful(Protocol):
    """Contract for modules that track execution state."""

    @property
    def state(self) -> Any:
        ...
