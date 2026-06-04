"""
Fibonacci Sequence Generator with Memoization and Performance Benchmarking
Compares recursive, iterative, and memoized approaches with timing.
"""

import time
import sys
from functools import lru_cache

sys.setrecursionlimit(10000)

# ── Recursive (naive) ─────────────────────────────────────────────────────────
def fib_recursive(n):
    if n <= 1:
        return n
    return fib_recursive(n - 1) + fib_recursive(n - 2)


# ── Memoized (manual dict cache) ──────────────────────────────────────────────
_memo = {}

def fib_memoized(n):
    if n in _memo:
        return _memo[n]
    if n <= 1:
        return n
    result = fib_memoized(n - 1) + fib_memoized(n - 2)
    _memo[n] = result
    return result


# ── lru_cache version ─────────────────────────────────────────────────────────
@lru_cache(maxsize=None)
def fib_lru(n):
    if n <= 1:
        return n
    return fib_lru(n - 1) + fib_lru(n - 2)


# ── Iterative ─────────────────────────────────────────────────────────────────
def fib_iterative(n):
    if n <= 1:
        return n
    a, b = 0, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    return b


def fib_sequence_iterative(count):
    seq = []
    a, b = 0, 1
    for _ in range(count):
        seq.append(a)
        a, b = b, a + b
    return seq


# ── Benchmarking ──────────────────────────────────────────────────────────────
def benchmark(func, n, label):
    start = time.perf_counter()
    result = func(n)
    elapsed = time.perf_counter() - start
    return label, result, elapsed


def print_table(headers, rows, col_widths):
    fmt = "  ".join(f"{{:<{w}}}" for w in col_widths)
    separator = "-+-".join("-" * w for w in col_widths)
    print("  " + fmt.format(*headers))
    print("  " + separator)
    for row in rows:
        print("  " + fmt.format(*row))


def run_benchmark(n):
    print(f"\n📊 Benchmarking Fibonacci({n})")
    print("=" * 60)

    results = []

    # Iterative
    label, val, t = benchmark(fib_iterative, n, "Iterative")
    results.append((label, str(val)[:30] + ("..." if len(str(val)) > 30 else ""), f"{t*1000:.4f} ms"))

    # Memoized
    _memo.clear()
    label, val, t = benchmark(fib_memoized, n, "Memoized")
    results.append((label, str(val)[:30] + ("..." if len(str(val)) > 30 else ""), f"{t*1000:.4f} ms"))

    # LRU Cache
    fib_lru.cache_clear()
    label, val, t = benchmark(fib_lru, n, "LRU Cache")
    results.append((label, str(val)[:30] + ("..." if len(str(val)) > 30 else ""), f"{t*1000:.4f} ms"))

    # Recursive (only for small n)
    if n <= 30:
        label, val, t = benchmark(fib_recursive, n, "Recursive")
        results.append((label, str(val)[:30], f"{t*1000:.4f} ms"))
    else:
        results.append(("Recursive", "Skipped (n > 30)", "N/A"))

    print_table(
        ["Method", "Result (truncated)", "Time"],
        results,
        [12, 35, 14]
    )


def print_sequence_table(count):
    print(f"\n📋 First {count} Fibonacci Numbers")
    print("=" * 60)
    seq = fib_sequence_iterative(count)
    rows = []
    for i, val in enumerate(seq):
        rows.append((str(i), str(val), f"{len(str(val))} digit(s)"))
    print_table(["Index", "Value", "Digits"], rows, [8, 30, 12])


def main():
    print("╔══════════════════════════════════════════╗")
    print("║   Fibonacci Generator & Benchmarker      ║")
    print("╚══════════════════════════════════════════╝")

    while True:
        try:
            count = int(input("\nHow many Fibonacci terms to display? (1-50): "))
            if 1 <= count <= 50:
                break
            print("Please enter a value between 1 and 50.")
        except ValueError:
            print("Invalid input.")

    print_sequence_table(count)

    for n in [10, 20, 30, 40]:
        run_benchmark(n)


if __name__ == "__main__":
    main()
