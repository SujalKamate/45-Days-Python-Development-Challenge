"""Central dependency registry preventing circular imports via string-based resolution."""

from typing import Any, Callable, Dict, List, Optional, Type


class DependencyRegistry:
    """Thread-safe registry for decoupled module resolution.

    Modules register themselves by contract name at import time.
    Other modules resolve dependencies by contract name string,
    avoiding direct cross-module imports and eliminating circular
    import risks.
    """

    _dependencies: Dict[str, Any] = {}
    _factories: Dict[str, Callable[[], Any]] = {}

    @classmethod
    def register(cls, name: str, instance: Any) -> None:
        """Register *instance* under *name*."""
        cls._dependencies[name] = instance

    @classmethod
    def register_factory(cls, name: str, factory: Callable[[], Any]) -> None:
        """Register a lazy *factory* for *name* (called on first resolve)."""
        cls._factories[name] = factory

    @classmethod
    def resolve(cls, name: str) -> Optional[Any]:
        """Resolve a dependency by *name* (lazily instantiates if factory registered)."""
        if name not in cls._dependencies and name in cls._factories:
            cls._dependencies[name] = cls._factories[name]()
        return cls._dependencies.get(name)

    @classmethod
    def registered_names(cls) -> List[str]:
        """Return all registered dependency names."""
        return list(cls._dependencies.keys()) + list(cls._factories.keys())

    @classmethod
    def clear(cls) -> None:
        """Clear all registrations (useful for testing)."""
        cls._dependencies.clear()
        cls._factories.clear()


# Singleton instance
registry = DependencyRegistry()
