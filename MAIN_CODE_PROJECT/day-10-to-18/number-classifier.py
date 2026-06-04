"""
Smart Number Classifier with Extended Mathematical Properties
Classifies numbers and displays digit sum, digit product, and divisor count.
"""

import math
from functools import reduce


def is_prime(n):
    if n < 2:
        return False
    if n == 2:
        return True
    if n % 2 == 0:
        return False
    for i in range(3, int(math.sqrt(n)) + 1, 2):
        if n % i == 0:
            return False
    return True


def is_composite(n):
    return n > 1 and not is_prime(n)


def get_divisors(n):
    if n <= 0:
        return []
    divisors = []
    for i in range(1, int(math.sqrt(abs(n))) + 1):
        if n % i == 0:
            divisors.append(i)
            if i != n // i:
                divisors.append(n // i)
    return sorted(divisors)


def is_perfect(n):
    if n <= 1:
        return False
    divisors = get_divisors(n)
    return sum(divisors[:-1]) == n


def is_armstrong(n):
    if n < 0:
        return False
    digits = str(n)
    power = len(digits)
    return sum(int(d) ** power for d in digits) == n


def is_palindrome(n):
    s = str(abs(n))
    return s == s[::-1]


def digit_sum(n):
    return sum(int(d) for d in str(abs(n)))


def digit_product(n):
    digits = [int(d) for d in str(abs(n))]
    if 0 in digits:
        return 0
    return reduce(lambda x, y: x * y, digits)


def classify_number(n):
    print(f"\n{'='*50}")
    print(f"  Analysis for: {n}")
    print(f"{'='*50}")

    classifications = []

    if n < 0:
        print("  ⚠  Negative number detected.")
        print(f"  Absolute value used for some checks: {abs(n)}")
    elif n == 0:
        print("  ⚠  Zero: neither prime nor composite.")
    elif n == 1:
        print("  ⚠  One: neither prime nor composite.")
    else:
        if is_prime(n):
            classifications.append("Prime")
        if is_composite(n):
            classifications.append("Composite")
        if is_perfect(n):
            classifications.append("Perfect")

    if is_armstrong(abs(n)):
        classifications.append("Armstrong")
    if is_palindrome(n):
        classifications.append("Palindrome")

    print(f"\n  Classifications: {', '.join(classifications) if classifications else 'None'}")

    divs = get_divisors(abs(n)) if n != 0 else []
    print(f"\n  Digit Sum     : {digit_sum(n)}")
    print(f"  Digit Product : {digit_product(n)}")
    print(f"  Divisors ({len(divs)}) : {divs[:20]}{'...' if len(divs) > 20 else ''}")
    print(f"  Number of Div : {len(divs)}")
    print(f"{'='*50}\n")


def main():
    print("╔══════════════════════════════════════╗")
    print("║   Smart Number Classifier v1.0       ║")
    print("╚══════════════════════════════════════╝")

    while True:
        user_input = input("\nEnter a number (or 'q' to quit): ").strip()
        if user_input.lower() == 'q':
            print("Goodbye!")
            break
        try:
            n = int(user_input)
            classify_number(n)
        except ValueError:
            print("  ✗ Invalid input. Please enter an integer.")


if __name__ == "__main__":
    # Demo runs
    demo_numbers = [0, 1, -7, 6, 28, 153, 370, 9474, 121, 13]
    print("=== DEMO MODE ===")
    for num in demo_numbers:
        classify_number(num)
