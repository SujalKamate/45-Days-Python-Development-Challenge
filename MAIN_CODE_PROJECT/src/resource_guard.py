"""Resource access guard enforcing module-level least privilege.

Each application module is assigned a unique *namespace* derived from its
class name.  The :class:`ResourceGuard` ensures that a module can only
read/write files whose names are scoped to its namespace, preventing one
module from accessing another module's state or data files.

Usage::

    from .resource_guard import ResourceGuard

    guard = ResourceGuard("WeatherInformationApp", Path("outputs"))
    guard.qualify("state.json")          # "WeatherInformationApp_state.json"
    guard.check_path(Path("outputs"))  # raises PermissionError if wrong namespace
"""

from pathlib import Path


class ResourceGuard:
    """Ensures a module can only access files in its own namespace."""

    def __init__(self, namespace: str, output_dir: Path) -> None:
        self._namespace = namespace
        self._output_dir = output_dir.resolve()

    # ── public API ──────────────────────────────────────────────────────

    def qualify(self, name: str) -> str:
        """Prefix *name* with the module namespace."""
        return f"{self._namespace}_{name}"

    def check_path(self, path: Path) -> None:
        """Raise ``PermissionError`` if *path* is outside this module's scope."""
        resolved = path.resolve()
        if not str(resolved).startswith(str(self._output_dir)):
            raise PermissionError(
                f"Access denied: {path} is outside output directory "
                f"({self._output_dir})"
            )
        if not resolved.name.startswith(self._namespace):
            raise PermissionError(
                f"Access denied: {resolved.name} does not belong to "
                f"namespace '{self._namespace}'"
            )
