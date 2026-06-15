# 🐍 Python Best Practices Cookbook

This cookbook establishes clean, readable, and production-ready programming standards for the **45-Days-Python-Development-Challenge** repository. Following these patterns ensures consistency, reduces bugs, and facilitates seamless code reviews.

---

## 📖 Table of Contents

1. [PEP 8 Style & Conventions](#1-pep-8-style--conventions)
2. [Clean Architecture & Decoupling](#2-clean-architecture--decoupling)
3. [Defensive Programming & Security](#3-defensive-programming--security)
4. [Memory & Performance Optimization](#4-memory--performance-optimization)
5. [Robust Exception Handling](#5-robust-exception-handling)
6. [Logging & Telemetry](#6-logging--telemetry)
7. [Unit Testing Guidelines](#7-unit-testing-guidelines)

---

## 1. PEP 8 Style & Conventions

Code readability is a primary goal. Write clean, readable code rather than complex shortcuts.

### Naming Conventions
*   **Modules / Packages**: Lowercase snake_case (e.g. `wal_logger.py`, `aead_store.py`).
*   **Classes**: PascalCase (e.g. `BaseApp`, `DependencyRegistry`).
*   **Functions / Variables**: Lowercase snake_case (e.g. `process_dataset()`, `user_id`).
*   **Constants**: All-caps with underscores (e.g. `MAX_RETRIES = 5`, `SEED_VALUE = 42`).
*   **Private Members**: Single leading underscore for internal helper functions or attributes (e.g. `_next_id`).

### Type Hinting (PEP 484)
Always annotate parameters and return types. This makes code self-documenting and enables static analysis tools (like mypy) to catch errors early.

```python
# Bad
def calculate_average(values):
    return sum(values) / len(values)

# Good
from typing import List

def calculate_average(values: List[float]) -> float:
    """Calculate and return the mean of a list of floats."""
    if not values:
        raise ValueError("Cannot compute average of an empty list.")
    return sum(values) / len(values)
```

### Docstrings (PEP 257)
Write triple-quoted docstrings for all modules, classes, and public functions.
```python
def retrieve_user(user_id: int) -> dict:
    """Retrieve user record from database.

    Args:
        user_id: The unique integer identifier of the user.

    Returns:
        A dictionary containing the parsed user record values.

    Raises:
        KeyError: If the user_id does not exist in store.
    """
    # implementation ...
```

---

## 2. Clean Architecture & Decoupling

Avoid tight coupling between components. Programming against abstract interfaces (Protocols) keeps code modular and testable.

### Programming to Contracts
Use structural typing via `typing.Protocol` to establish contracts. Subclasses implement the protocols, allowing you to swap out concrete implementations without changing client code.

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class Serializer(Protocol):
    """Abstract contract for serializing state records."""
    def serialize(self, data: dict) -> bytes:
        ...

class JSONSerializer:
    def serialize(self, data: dict) -> bytes:
        import json
        return json.dumps(data).encode("utf-8")
```

### Eliminating Circular Imports
Do not import sibling module components directly. Instead, register module instances at import time using the central `DependencyRegistry` and resolve them dynamically.

```python
# In module_a.py
from dependency_registry import registry

class DatabaseApp:
    def query(self, sql: str) -> list:
         return []

registry.register("db", DatabaseApp())

# In module_b.py
from dependency_registry import registry

class UserProcessor:
    def load_users(self) -> list:
        # Resolve DB instance without importing module_a
        db = registry.resolve("db")
        return db.query("SELECT * FROM users") if db else []
```

---

## 3. Defensive Programming & Security

Write code that assumes input is untrusted and filesystems are volatile.

### Safe File Path Access
Never trust user-supplied paths directly. Avoid directory traversal vulnerability risks (`../../file.txt`) by qualifying paths using a validator like `ResourceGuard`.

```python
from pathlib import Path
from resource_guard import ResourceGuard

allowed_directory = Path("outputs")
guard = ResourceGuard("AppGuard", allowed_directory)

def save_report(user_filename: str, payload: str) -> None:
    # guard.qualify throws ValueError if input tries to escape outputs/
    safe_name = guard.qualify(user_filename)
    target_path = allowed_directory / safe_name
    target_path.write_text(payload)
```

### Exact Decimal Math for Financial Operations
Never use binary floats (`float`) for calculating financial numbers, values, or currencies. Floats introduce rounding approximations. Use `decimal.Decimal` to ensure exact arithmetic.

```python
# Bad: float approximations
print(0.1 + 0.2)  # Output: 0.30000000000000004

# Good: exact decimals
from decimal import Decimal
total = Decimal("0.1") + Decimal("0.2")
print(total)  # Output: 0.3
```

---

## 4. Memory & Performance Optimization

Optimize resources by choosing the right data structures and execution controls.

### Generators vs. Lists
Use lists only if you need to index, slice, or retain elements in memory. Use generators (`yield` or generator expressions) to process elements one-at-a-time, minimizing memory usage.

```python
# Bad: Loads entire file lines into memory
def read_large_file(path: str) -> list[str]:
    with open(path, "r") as f:
        return f.readlines()

# Good: Yields lines one by one, retaining minimal RAM
from typing import Generator

def stream_large_file(path: str) -> Generator[str, None, None]:
    with open(path, "r") as f:
        for line in f:
            yield line
```

### Constant Lookup Optimizations
For fast membership checks (`if item in collection`), convert your list collections to a `set`. Sets have an average O(1) lookup speed, while lists require O(N) linear scans.

```python
# Bad (O(N) check per item)
forbidden_words = ["bad", "unsafe", "malicious"]
def validate_content(word: str) -> bool:
    return word in forbidden_words

# Good (O(1) lookups)
FORBIDDEN_SET = {"bad", "unsafe", "malicious"}
def validate_content_fast(word: str) -> bool:
    return word in FORBIDDEN_SET
```

---

## 5. Robust Exception Handling

Proper exception handling keeps applications running stably and records debug details for troubleshooting.

### Avoid Bare Exception Catching
Never capture a bare `except:`. This catches keyboard interrupts (Ctrl+C) and system exits, preventing them from stopping the script. Catch `Exception` instead.

```python
# Bad
try:
    process_data()
except:
    print("An error occurred.")

# Good
try:
    process_data()
except Exception as err:
    print(f"Failed to process data: {err}")
```

### Graceful Resource Releases
Always use context managers (`with`) or `try...finally` blocks to ensure files, sockets, locks, and DB connections are closed even if an exception is raised.

```python
# Resource release guaranteed
import threading
lock = threading.Lock()

with lock:
    # Critical section execution
    do_something_vulnerable()
```

---

## 6. Logging & Telemetry

Avoid using `print()` for persistent state tracking or debug loops inside reusable library modules. Instead, write audit logs or event alerts to files.

*   Use structured events (`event_publish` in `BaseApp`) to log system mutations.
*   Log timestamps and execution stages into transaction records so logs can be checked easily.
*   Enforce logging limits (e.g. `rotate_logs`) so files do not fill the disk.

---

## 7. Unit Testing Guidelines

Tests prevent future breaks and document expected behavior.

### Principles of Good Tests
1.  **Isolation**: Tests must not rely on variables mutated by other tests. Use setup/teardown hooks (fixtures) to reset state.
2.  **Mocking**: Mock slow network requests, database connections, and filesystem writes to keep tests running quickly.
3.  **Assertions**: Use precise assert matches (e.g. use `pytest.approx` for floats).

```python
import pytest

def test_division():
    # Bad
    assert 10 / 3 == 3.3333333333333335
    
    # Good
    assert 10 / 3 == pytest.approx(3.3333, rel=1e-4)
```
