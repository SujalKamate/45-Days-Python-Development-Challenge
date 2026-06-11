"""
In-Memory Mini Relational Database with Indexing and Multi-Condition Filtering
Implements insert/delete/update/select, column indexing, WHERE-like filtering.
"""

import copy
import time
from typing import Any, Callable, Dict, List, Optional


class Index:
    """Simple hash-based index on a single column."""
    def __init__(self, column: str):
        self.column   = column
        self._data: Dict[Any, List[int]] = {}   # value -> list of row positions

    def rebuild(self, rows: List[dict]):
        self._data.clear()
        for i, row in enumerate(rows):
            val = row.get(self.column)
            self._data.setdefault(val, []).append(i)

    def lookup(self, value) -> List[int]:
        return self._data.get(value, [])

    def __repr__(self):
        return f"Index(column='{self.column}', {len(self._data)} unique values)"


class Table:
    def __init__(self, name: str, schema: Dict[str, type]):
        """
        schema: dict of column_name -> Python type (for type checking)
        e.g. {"id": int, "name": str, "age": int, "salary": float}
        """
        self.name    = name
        self.schema  = schema
        self._rows:  List[dict] = []
        self._indexes: Dict[str, Index] = {}
        self._id_counter = 1
        self._auto_id = "_id"  # internal row ID

    # ── Schema helpers ────────────────────────────────────────────────────────
    def _coerce(self, row: dict) -> dict:
        coerced = {}
        for col, val in row.items():
            expected_type = self.schema.get(col)
            if expected_type and val is not None:
                try:
                    coerced[col] = expected_type(val)
                except (ValueError, TypeError):
                    raise TypeError(f"Column '{col}': cannot coerce {val!r} to {expected_type.__name__}")
            else:
                coerced[col] = val
        return coerced

    def _validate(self, row: dict):
        for col in self.schema:
            if col not in row:
                row[col] = None  # allow missing columns (NULL-like)

    # ── CRUD Operations ───────────────────────────────────────────────────────
    def insert(self, row: dict) -> dict:
        row = copy.copy(row)
        self._validate(row)
        row = self._coerce(row)
        row[self._auto_id] = self._id_counter
        self._id_counter += 1
        self._rows.append(row)
        self._rebuild_indexes()
        return row

    def insert_many(self, rows: List[dict]) -> List[dict]:
        return [self.insert(r) for r in rows]

    def select(
        self,
        where: Optional[Callable[[dict], bool]] = None,
        columns: Optional[List[str]] = None,
        order_by: Optional[str] = None,
        descending: bool = False,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[dict]:
        results = [copy.copy(r) for r in self._rows if where is None or where(r)]
        if order_by:
            results.sort(key=lambda r: (r.get(order_by) is None, r.get(order_by)), reverse=descending)
        results = results[offset:]
        if limit:
            results = results[:limit]
        if columns:
            results = [{c: r.get(c) for c in columns} for r in results]
        return results

    def select_by_index(self, column: str, value) -> List[dict]:
        if column not in self._indexes:
            raise KeyError(f"No index on column '{column}'. Use create_index() first.")
        positions = self._indexes[column].lookup(value)
        return [copy.copy(self._rows[i]) for i in positions if i < len(self._rows)]

    def update(self, where: Callable[[dict], bool], updates: dict) -> int:
        count = 0
        for row in self._rows:
            if where(row):
                for k, v in updates.items():
                    if k in self.schema:
                        row[k] = self.schema[k](v) if v is not None else None
                    else:
                        row[k] = v
                count += 1
        if count:
            self._rebuild_indexes()
        return count

    def delete(self, where: Callable[[dict], bool]) -> int:
        before = len(self._rows)
        self._rows = [r for r in self._rows if not where(r)]
        removed = before - len(self._rows)
        if removed:
            self._rebuild_indexes()
        return removed

    # ── Indexing ──────────────────────────────────────────────────────────────
    def create_index(self, column: str):
        if column not in self.schema:
            raise KeyError(f"Column '{column}' not in schema.")
        idx = Index(column)
        idx.rebuild(self._rows)
        self._indexes[column] = idx
        print(f"  ✓ Index created on '{self.name}'.{column}")

    def _rebuild_indexes(self):
        for idx in self._indexes.values():
            idx.rebuild(self._rows)

    # ── Aggregation ───────────────────────────────────────────────────────────
    def count(self, where=None) -> int:
        return len(self.select(where))

    def aggregate(self, column: str, where=None) -> dict:
        rows   = self.select(where)
        values = [r[column] for r in rows if r.get(column) is not None]
        if not values:
            return {"count": 0, "sum": None, "min": None, "max": None, "avg": None}
        return {
            "count": len(values),
            "sum":   sum(values),
            "min":   min(values),
            "max":   max(values),
            "avg":   round(sum(values) / len(values), 4),
        }

    # ── Display ───────────────────────────────────────────────────────────────
    def print_table(self, rows: Optional[List[dict]] = None, title: str = ""):
        rows = rows if rows is not None else self._rows
        if not rows:
            print(f"  [{self.name}] — empty"); return

        exclude = {self._auto_id}
        cols    = [c for c in self.schema if c not in exclude]
        widths  = {c: max(len(c), max((len(str(r.get(c, ""))) for r in rows), default=0)) for c in cols}

        label = title or f"Table: {self.name} ({len(rows)} rows)"
        print(f"\n  {'═'*sum(widths.values())+len(cols)*3}")
        print(f"  {label}")
        print(f"  {'─'*(sum(widths.values())+len(cols)*3)}")
        header = "  " + "  ".join(c.upper().ljust(widths[c]) for c in cols)
        print(header)
        print(f"  {'─'*(sum(widths.values())+len(cols)*3)}")
        for row in rows:
            line = "  " + "  ".join(str(row.get(c, "NULL")).ljust(widths[c]) for c in cols)
            print(line)
        print(f"  {'═'*sum(widths.values())+len(cols)*3}\n")

    def __len__(self):
        return len(self._rows)

    def __repr__(self):
        return f"Table('{self.name}', rows={len(self._rows)}, indexes={list(self._indexes.keys())})"


# ── Demo ──────────────────────────────────────────────────────────────────────
def benchmark_index(table, column, value, iterations=500):
    start = time.perf_counter()
    for _ in range(iterations):
        table.select(where=lambda r: r.get(column) == value)
    t_scan = (time.perf_counter() - start) * 1000

    start = time.perf_counter()
    for _ in range(iterations):
        table.select_by_index(column, value)
    t_index = (time.perf_counter() - start) * 1000

    print(f"  Benchmark ({iterations} lookups, column='{column}', value={value!r}):")
    print(f"    Full scan  : {t_scan:.2f}ms")
    print(f"    Index scan : {t_index:.2f}ms")
    if t_index > 0:
        print(f"    Speedup    : {t_scan/t_index:.1f}×")


def main():
    print("╔══════════════════════════════════════════╗")
    print("║   In-Memory Mini Database v1.0          ║")
    print("╚══════════════════════════════════════════╝")

    # Create employees table
    employees = Table("employees", {
        "id":         int,
        "name":       str,
        "department": str,
        "salary":     float,
        "age":        int,
        "active":     bool,
    })

    # Insert records
    employees.insert_many([
        {"id": 1, "name": "Alice Sharma",  "department": "Engineering", "salary": 95000, "age": 29, "active": True},
        {"id": 2, "name": "Bob Verma",     "department": "Marketing",   "salary": 72000, "age": 34, "active": True},
        {"id": 3, "name": "Carol Singh",   "department": "Engineering", "salary": 88000, "age": 27, "active": True},
        {"id": 4, "name": "David Kumar",   "department": "HR",          "salary": 65000, "age": 42, "active": False},
        {"id": 5, "name": "Eve Patel",     "department": "Engineering", "salary": 102000,"age": 31, "active": True},
        {"id": 6, "name": "Frank Nair",    "department": "Marketing",   "salary": 78000, "age": 38, "active": True},
        {"id": 7, "name": "Grace Iyer",    "department": "Finance",     "salary": 91000, "age": 35, "active": True},
        {"id": 8, "name": "Henry Thomas",  "department": "Engineering", "salary": 85000, "age": 26, "active": True},
    ])

    employees.print_table(title="All Employees")

    # SELECT with WHERE
    print("  Engineering employees earning > 85k:")
    eng_high = employees.select(
        where=lambda r: r["department"] == "Engineering" and r["salary"] > 85000,
        order_by="salary", descending=True
    )
    employees.print_table(eng_high, "Engineering > 85k")

    # Create index and benchmark
    employees.create_index("department")

    print("\n  Index lookup — department='Engineering':")
    eng = employees.select_by_index("department", "Engineering")
    employees.print_table(eng, "Via Index: Engineering")

    benchmark_index(employees, "department", "Engineering")

    # Aggregation
    print("\n  Salary Aggregation by Department:")
    depts = set(r["department"] for r in employees._rows)
    print(f"  {'Dept':<15} {'Count':>6} {'Avg Salary':>12} {'Min':>10} {'Max':>10}")
    print(f"  {'─'*55}")
    for dept in sorted(depts):
        agg = employees.aggregate("salary", where=lambda r, d=dept: r["department"] == d)
        print(f"  {dept:<15} {agg['count']:>6} {agg['avg']:>12,.0f} {agg['min']:>10,.0f} {agg['max']:>10,.0f}")

    # UPDATE
    n = employees.update(
        where=lambda r: r["department"] == "HR",
        updates={"salary": 70000}
    )
    print(f"\n  Updated {n} HR record(s) salary to 70000.")

    # DELETE
    n = employees.delete(where=lambda r: r["active"] == False)
    print(f"  Deleted {n} inactive employee(s).")
    print(f"  Remaining rows: {len(employees)}")

    # Multi-condition filter
    print("\n  Active engineers aged < 30:")
    young_eng = employees.select(
        where=lambda r: r["department"] == "Engineering" and r["age"] < 30 and r["active"],
        columns=["id", "name", "age", "salary"]
    )
    employees.print_table(young_eng, "Young Engineers")

    # Limit/offset (pagination)
    print("  Page 1 (limit=3, offset=0):")
    page1 = employees.select(order_by="name", limit=3, offset=0)
    employees.print_table(page1, "Page 1")

    print("  Page 2 (limit=3, offset=3):")
    page2 = employees.select(order_by="name", limit=3, offset=3)
    employees.print_table(page2, "Page 2")

    print(f"  Final table repr: {employees}")


if __name__ == "__main__":
    main()
