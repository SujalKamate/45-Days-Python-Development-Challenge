"""
Comprehensive Recursive Problem Solver with Permutations and Flatten
Solves Tower of Hanoi, factorial, power, GCD, flatten nested lists, permutations.
"""

import sys
sys.setrecursionlimit(10000)


# ── Tower of Hanoi ────────────────────────────────────────────────────────────
hanoi_moves = []

def hanoi(n, source, target, auxiliary, verbose=True):
    """Solve Tower of Hanoi recursively."""
    if n == 1:
        move = f"  Move disk 1 from {source} → {target}"
        hanoi_moves.append((1, source, target))
        if verbose:
            print(move)
        return
    hanoi(n - 1, source, auxiliary, target, verbose)
    move = f"  Move disk {n} from {source} → {target}"
    hanoi_moves.append((n, source, target))
    if verbose:
        print(move)
    hanoi(n - 1, auxiliary, target, source, verbose)


def hanoi_demo(n=3):
    global hanoi_moves
    hanoi_moves = []
    print(f"\n  Tower of Hanoi — {n} disk(s)")
    print(f"  {'─'*40}")
    if n <= 4:
        hanoi(n, 'A', 'C', 'B', verbose=True)
    else:
        hanoi(n, 'A', 'C', 'B', verbose=False)
    print(f"  Total moves: {len(hanoi_moves)}  (= 2^{n} - 1 = {2**n - 1})")


# ── Factorial ─────────────────────────────────────────────────────────────────
def factorial(n):
    if n < 0:
        raise ValueError("Factorial undefined for negative numbers.")
    if n in (0, 1):
        return 1
    return n * factorial(n - 1)


def factorial_steps(n):
    if n <= 0:
        return [f"0! = 1"]
    steps = []
    for i in range(n, 0, -1):
        steps.append(f"  {i}! = {i} × {i-1}!" if i > 1 else f"  1! = 1")
    steps.append(f"  {n}! = {factorial(n)}")
    return steps


# ── Power ─────────────────────────────────────────────────────────────────────
def power(base, exp):
    """Recursive exponentiation (handles negative exponents)."""
    if exp == 0:
        return 1
    if exp < 0:
        return 1 / power(base, -exp)
    if exp % 2 == 0:
        half = power(base, exp // 2)
        return half * half
    return base * power(base, exp - 1)


# ── GCD ───────────────────────────────────────────────────────────────────────
def gcd(a, b):
    """Euclidean algorithm recursively."""
    return a if b == 0 else gcd(b, a % b)


def gcd_steps(a, b):
    steps = []
    while b:
        steps.append(f"  gcd({a}, {b}) → gcd({b}, {a % b})  [{a} = {a//b}×{b} + {a%b}]")
        a, b = b, a % b
    steps.append(f"  gcd({a}, 0) = {a}")
    return steps


def lcm(a, b):
    return abs(a * b) // gcd(a, b)


# ── Flatten Nested List ───────────────────────────────────────────────────────
def flatten(nested, depth=None, _current_depth=0):
    """Flatten a deeply nested list. depth=None means fully flatten."""
    result = []
    for item in nested:
        if isinstance(item, (list, tuple)) and (depth is None or _current_depth < depth):
            result.extend(flatten(item, depth, _current_depth + 1))
        else:
            result.append(item)
    return result


# ── Permutations ─────────────────────────────────────────────────────────────
def permutations(s):
    """Generate all permutations of string s."""
    if len(s) <= 1:
        return [s]
    result = []
    for i, ch in enumerate(s):
        rest = s[:i] + s[i+1:]
        for perm in permutations(rest):
            result.append(ch + perm)
    return result


def unique_permutations(s):
    return sorted(set(permutations(s)))


# ── Combinations ─────────────────────────────────────────────────────────────
def combinations(lst, r):
    """Generate all r-length combinations from lst."""
    if r == 0:
        return [[]]
    if not lst:
        return []
    first, rest = lst[0], lst[1:]
    with_first    = [[first] + c for c in combinations(rest, r - 1)]
    without_first = combinations(rest, r)
    return with_first + without_first


# ── Sum of Digits Recursively ─────────────────────────────────────────────────
def digit_sum(n):
    n = abs(n)
    if n < 10:
        return n
    return n % 10 + digit_sum(n // 10)


# ── Binary Search Recursively ─────────────────────────────────────────────────
def binary_search(arr, target, lo=0, hi=None, depth=0):
    if hi is None:
        hi = len(arr) - 1
    if lo > hi:
        return -1, depth
    mid = (lo + hi) // 2
    if arr[mid] == target:
        return mid, depth + 1
    elif arr[mid] < target:
        return binary_search(arr, target, mid + 1, hi, depth + 1)
    else:
        return binary_search(arr, target, lo, mid - 1, depth + 1)


def print_section(title):
    print(f"\n  {'═'*55}")
    print(f"  {title}")
    print(f"  {'─'*55}")


def main():
    print("╔══════════════════════════════════════════╗")
    print("║   Recursive Problem Solver v1.0         ║")
    print("╚══════════════════════════════════════════╝")

    # Tower of Hanoi
    for n in [2, 3, 4]:
        hanoi_demo(n)

    # Factorial
    print_section("Factorial")
    for n in [0, 1, 5, 10, 15]:
        print(f"  {n}! = {factorial(n):,}")
    print("\n  Step-by-step for 5!:")
    for step in factorial_steps(5):
        print(step)

    # Power
    print_section("Recursive Power")
    cases = [(2, 10), (3, 5), (2, -3), (5, 0), (7, 3)]
    for base, exp in cases:
        print(f"  {base}^{exp} = {power(base, exp)}")

    # GCD / LCM
    print_section("GCD & LCM")
    pairs = [(48, 18), (100, 75), (17, 13), (1071, 462)]
    for a, b in pairs:
        g = gcd(a, b)
        l = lcm(a, b)
        print(f"  gcd({a}, {b}) = {g}   lcm = {l}")
    print("\n  GCD steps for gcd(1071, 462):")
    for step in gcd_steps(1071, 462):
        print(step)

    # Flatten
    print_section("Flatten Nested Lists")
    nested_tests = [
        [1, [2, 3], [4, [5, 6]]],
        [[1, [2]], [3, [4, [5, [6]]]]],
        [1, 2, 3],
        [[[[[42]]]]],
    ]
    for lst in nested_tests:
        flat = flatten(lst)
        flat1 = flatten(lst, depth=1)
        print(f"  {str(lst):<40} → {flat}")
        print(f"  {'(depth=1)':<40} → {flat1}")

    # Permutations
    print_section("Permutations")
    for s in ['AB', 'ABC', 'AAB']:
        perms = unique_permutations(s)
        print(f"  permutations('{s}') = {perms}  ({len(perms)} unique)")

    # Combinations
    print_section("Combinations")
    lst = [1, 2, 3, 4]
    for r in [2, 3]:
        combos = combinations(lst, r)
        print(f"  C({lst}, r={r}) = {combos}  ({len(combos)} total)")

    # Digit sum
    print_section("Recursive Digit Sum")
    for n in [0, 12345, 99999, 123456789]:
        print(f"  digit_sum({n}) = {digit_sum(n)}")

    # Binary search
    print_section("Recursive Binary Search")
    arr = list(range(0, 50, 3))
    print(f"  Array: {arr}")
    for target in [15, 27, 7, 99]:
        idx, steps = binary_search(arr, target)
        found = f"Found at index {idx}" if idx >= 0 else "Not found"
        print(f"  Search {target:>3}: {found}  ({steps} recursive calls)")


if __name__ == "__main__":
    main()
