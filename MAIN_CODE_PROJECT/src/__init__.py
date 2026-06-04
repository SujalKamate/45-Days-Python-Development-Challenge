# src package initialization for the 45-Day Python Development Challenge
# Exposes the dependency registry and shared contracts so modules can
# resolve dependencies by contract name instead of importing directly.

from .dependency_registry import registry
from . import contracts
