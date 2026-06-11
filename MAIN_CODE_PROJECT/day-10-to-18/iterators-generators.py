"""
Custom Iterator and Generator Suite with Lazy Evaluation Demonstration
Class-based iterator, generators for Fibonacci/prime/factorial, yield from, lazy eval.
"""

import itertools
import sys
import time


# ── Class-based Iterator ──────────────────────────────────────────────────────
class NumberRange:
    """Custom iterator for a range with step, start, end."""
    def __init__(self, start, stop, step=1):
        if step == 0:
            raise ValueError("Step cannot be zero.")
        self.current = start
        self.stop    = stop
        self.step    = step

    def __iter__(self):
        return self

    def __next__(self):
        if (self.step > 0 and self.current >= self.stop) or \
           (self.step < 0 and self.current <= self.stop):
            raise StopIteration
        val = self.current
        self.current += self.step
        return val

    def __repr__(self):
        return f"NumberRange({self.current}, {self.stop}, step={self.step})"


class Countdown:
    """Iterator that counts down from n to 0."""
    def __init__(self, n):
        self.n = n

    def __iter__(self):
        self.current = self.n
        return self

    def __next__(self):
        if self.current < 0:
            raise StopIteration
        val = self.current
        self.current -= 1
        return val


class Cycle:
    """Cycles through a sequence indefinitely."""
    def __init__(self, sequence):
        self.sequence = list(sequence)
        self.index    = 0

    def __iter__(self):
        return self

    def __next__(self):
        if not self.sequence:
            raise StopIteration
        val = self.sequence[self.index % len(self.sequence)]
        self.index += 1
        return val

    def take(self, n):
        return [next(self) for _ in range(n)]


# ── Generators ────────────────────────────────────────────────────────────────
def fibonacci_gen(limit=None):
    """Infinite (or limited) Fibonacci generator."""
    a, b = 0, 1
    count = 0
    while limit is None or count < limit:
        yield a
        a, b = b, a + b
        count += 1


def prime_gen(limit=None):
    """Generator yielding prime numbers using Sieve of Eratosthenes (segmented)."""
    def is_prime(n):
        if n < 2:  return False
        if n == 2: return True
        if n % 2 == 0: return False
        for i in range(3, int(n**0.5)+1, 2):
            if n % i == 0: return False
        return True

    n = 2
    count = 0
    while limit is None or count < limit:
        if is_prime(n):
            yield n
            count += 1
        n += 1


def factorial_gen(limit=None):
    """Generator for factorial sequence: 0!, 1!, 2!, ..."""
    n     = 0
    fact  = 1
    count = 0
    while limit is None or count < limit:
        yield (n, fact)
        n += 1
        fact *= n
        count += 1


def triangular_gen():
    """Generates triangular numbers: 1, 3, 6, 10, ..."""
    n = 1
    while True:
        yield n * (n + 1) // 2
        n += 1


def collatz_gen(n):
    """Generates the Collatz sequence starting from n."""
    yield n
    while n != 1:
        n = n // 2 if n % 2 == 0 else 3 * n + 1
        yield n


def powers_of_two():
    n = 0
    while True:
        yield 2 ** n
        n += 1


# ── yield from ────────────────────────────────────────────────────────────────
def chain_generators(*iterables):
    """Demonstrates yield from for flattening multiple generators."""
    for it in iterables:
        yield from it


def nested_flatten(nested):
    """Recursively flatten nested iterables using yield from."""
    for item in nested:
        if hasattr(item, '__iter__') and not isinstance(item, str):
            yield from nested_flatten(item)
        else:
            yield item


# ── Lazy evaluation demo ──────────────────────────────────────────────────────
def lazy_large_pipeline():
    """Process a million numbers lazily without building any list."""
    def naturals():
        n = 1
        while True:
            yield n
            n += 1

    result = (
        x * x
        for x in naturals()
        if x % 3 == 0
    )
    first_10 = list(itertools.islice(result, 10))
    return first_10


def memory_compare():
    """Compare memory usage of list vs generator."""
    size = 100_000

    import tracemalloc
    tracemalloc.start()
    big_list = [x * x for x in range(size)]
    _, peak_list = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    tracemalloc.start()
    gen = (x * x for x in range(size))
    _ = sum(1 for _ in gen)  # consume without storing
    _, peak_gen = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    return peak_list, peak_gen


def pipeline_demo():
    """Composable lazy pipeline example."""
    def read_data():
        for i in range(1, 21):
            yield {"id": i, "value": i * 7, "tag": "A" if i % 2 == 0 else "B"}

    def filter_tag(records, tag):
        return (r for r in records if r["tag"] == tag)

    def transform(records):
        return ({"id": r["id"], "doubled": r["value"] * 2} for r in records)

    def take(n, records):
        return itertools.islice(records, n)

    pipeline = take(5, transform(filter_tag(read_data(), "A")))
    return list(pipeline)


def print_section(title):
    print(f"\n  {'═'*55}")
    print(f"  {title}")
    print(f"  {'─'*55}")


def main():
    print("╔══════════════════════════════════════════╗")
    print("║   Iterators & Generators Suite v1.0     ║")
    print("╚══════════════════════════════════════════╝")

    print_section("Class-Based Iterator: NumberRange")
    nr = NumberRange(0, 20, 3)
    print(f"  Range(0, 20, step=3): {list(nr)}")
    nr_neg = NumberRange(10, 0, -2)
    print(f"  Range(10, 0, step=-2): {list(nr_neg)}")

    print_section("Countdown Iterator")
    print(f"  Countdown(5): {list(Countdown(5))}")

    print_section("Cycle Iterator")
    cyc = Cycle([1, 2, 3])
    print(f"  Cycle([1,2,3]) first 12: {cyc.take(12)}")

    print_section("Fibonacci Generator")
    fibs = list(fibonacci_gen(15))
    print(f"  First 15: {fibs}")
    # Find fibs < 1000 lazily
    big_fibs = list(itertools.takewhile(lambda x: x < 1000, fibonacci_gen()))
    print(f"  Fibs < 1000: {big_fibs}")

    print_section("Prime Generator")
    primes = list(prime_gen(20))
    print(f"  First 20 primes: {primes}")

    print_section("Factorial Generator")
    facts = [(n, f) for n, f in factorial_gen(10)]
    for n, f in facts:
        print(f"  {n:>2}! = {f:>15,}")

    print_section("Triangular & Powers of Two")
    tri = list(itertools.islice(triangular_gen(), 10))
    pw2 = list(itertools.islice(powers_of_two(), 12))
    print(f"  Triangular (10): {tri}")
    print(f"  Powers of 2 (12): {pw2}")

    print_section("Collatz Sequence")
    for start in [6, 27]:
        seq = list(collatz_gen(start))
        print(f"  Collatz({start}): length={len(seq)}, max={max(seq)}")
        print(f"    {seq[:15]}{'...' if len(seq)>15 else ''}")

    print_section("yield from — chain_generators")
    chained = list(chain_generators(range(5), range(5, 10), range(10, 15)))
    print(f"  Chained 3 ranges: {chained}")

    print_section("yield from — nested_flatten")
    nested = [1, [2, 3], [4, [5, [6, 7]]], 8, [9, [10]]]
    flat = list(nested_flatten(nested))
    print(f"  Nested : {nested}")
    print(f"  Flat   : {flat}")

    print_section("Lazy Pipeline (squares of multiples of 3)")
    result = lazy_large_pipeline()
    print(f"  First 10 squares of multiples-of-3 (lazy): {result}")

    print_section("Composable Data Pipeline")
    pipeline_result = pipeline_demo()
    for row in pipeline_result:
        print(f"  {row}")

    print_section("Memory: List vs Generator")
    try:
        peak_list, peak_gen = memory_compare()
        print(f"  List  peak memory: {peak_list/1024:.1f} KB")
        print(f"  Gen   peak memory: {peak_gen/1024:.1f} KB")
        print(f"  Generator used {peak_list/peak_gen:.0f}× less memory!")
    except Exception as e:
        print(f"  (tracemalloc comparison skipped: {e})")

    print_section("Timing: Lazy vs Eager")
    n = 500_000
    start = time.perf_counter()
    total_list = sum([x*x for x in range(n) if x % 7 == 0])
    t_list = time.perf_counter() - start

    start = time.perf_counter()
    total_gen = sum(x*x for x in range(n) if x % 7 == 0)
    t_gen = time.perf_counter() - start

    print(f"  n = {n:,}")
    print(f"  List comprehension : {t_list*1000:.2f}ms  sum={total_list}")
    print(f"  Generator expr     : {t_gen*1000:.2f}ms   sum={total_gen}")
    print(f"  {'✓ Same result' if total_list == total_gen else '✗ Different!'}")


if __name__ == "__main__":
    main()
