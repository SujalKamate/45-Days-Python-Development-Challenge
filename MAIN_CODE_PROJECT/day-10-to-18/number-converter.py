"""
Number System Converter with Step-by-Step Conversion and Binary Arithmetic
Converts between binary, octal, decimal, hex; shows steps; does binary arithmetic.
"""

import re


def validate_number(s, base):
    valid = {2: '01', 8: '01234567', 10: '0123456789', 16: '0123456789abcdefABCDEF'}
    prefix_map = {2: ('0b', '0B'), 8: ('0o', '0O'), 16: ('0x', '0X')}
    s = s.strip()
    for p in prefix_map.get(base, []):
        if s.startswith(p):
            s = s[2:]
    if not s:
        return False, s
    return all(c in valid.get(base, '') for c in s), s


def to_decimal_steps(s, from_base):
    s = s.strip().lstrip('0') or '0'
    digits = [int(c, from_base) for c in s]
    total = 0
    steps = []
    for i, d in enumerate(digits):
        power = len(digits) - 1 - i
        contribution = d * (from_base ** power)
        steps.append(f"    {d} × {from_base}^{power} = {contribution}")
        total += contribution
    return total, steps


def from_decimal_steps(n, to_base):
    if n == 0:
        return '0', ["    0 → '0'"]
    steps = []
    remainders = []
    orig = n
    base_labels = {2: 'binary', 8: 'octal', 16: 'hex'}
    while n > 0:
        rem = n % to_base
        rem_str = format(rem, 'X') if to_base == 16 else str(rem)
        steps.append(f"    {n} ÷ {to_base} = {n // to_base}  remainder {rem_str}")
        remainders.append(rem_str)
        n //= to_base
    result = ''.join(reversed(remainders))
    steps.append(f"    Read remainders bottom-up: {result}")
    return result, steps


def convert_with_steps(value_str, from_base, to_base):
    base_names = {2: 'Binary', 8: 'Octal', 10: 'Decimal', 16: 'Hexadecimal'}
    base_prefixes = {2: '0b', 8: '0o', 10: '', 16: '0x'}

    valid, clean = validate_number(value_str, from_base)
    if not valid:
        return None, f"Invalid {base_names[from_base]} number: '{value_str}'"

    print(f"\n  Converting {base_names[from_base]} '{clean}' → {base_names[to_base]}")
    print(f"  {'─'*55}")

    if from_base == to_base:
        print(f"  Same base — no conversion needed: {clean}")
        return clean, None

    if from_base != 10:
        print(f"\n  Step 1: {base_names[from_base]} → Decimal")
        decimal_val, steps = to_decimal_steps(clean, from_base)
        for s in steps:
            print(s)
        print(f"  → Decimal value: {decimal_val}")
    else:
        decimal_val = int(clean)

    if to_base != 10:
        print(f"\n  Step 2: Decimal {decimal_val} → {base_names[to_base]}")
        result_str, steps = from_decimal_steps(decimal_val, to_base)
        for s in steps:
            print(s)
        if to_base == 16:
            result_str = result_str.upper()
        print(f"  → {base_names[to_base]} result: {base_prefixes[to_base]}{result_str}")
    else:
        result_str = str(decimal_val)

    return result_str, None


def full_conversion_table(value_str, from_base):
    base_names = {2: 'Binary', 8: 'Octal', 10: 'Decimal', 16: 'Hex'}
    valid, clean = validate_number(value_str, from_base)
    if not valid:
        print(f"  Invalid input."); return

    decimal_val = int(clean, from_base)
    print(f"\n  Full Conversion Table for {value_str} (base {from_base}):")
    print(f"  {'─'*40}")
    for base in [2, 8, 10, 16]:
        if base == 10:
            result = str(decimal_val)
        else:
            fmt = {2: 'b', 8: 'o', 16: 'X'}[base]
            result = format(decimal_val, fmt)
        prefix = {2: '0b', 8: '0o', 10: '', 16: '0x'}[base]
        print(f"  {base_names[base]:<15} ({base:>2}) : {prefix}{result}")
    print(f"  {'─'*40}")


# ── Binary Arithmetic ─────────────────────────────────────────────────────────
def binary_add(a, b):
    result = bin(int(a, 2) + int(b, 2))[2:]
    return result

def binary_subtract(a, b):
    val = int(a, 2) - int(b, 2)
    if val < 0:
        return f"-{bin(-val)[2:]}"
    return bin(val)[2:]

def binary_multiply(a, b):
    return bin(int(a, 2) * int(b, 2))[2:]

def binary_divide(a, b):
    divisor = int(b, 2)
    if divisor == 0:
        return "Error: Division by zero"
    q, r = divmod(int(a, 2), divisor)
    return f"{bin(q)[2:]} remainder {bin(r)[2:]}"

def binary_arithmetic_demo():
    pairs = [('1010', '0110'), ('11001', '1010'), ('1101', '101')]
    ops = [
        ('Addition',       binary_add),
        ('Subtraction',    binary_subtract),
        ('Multiplication', binary_multiply),
        ('Division',       binary_divide),
    ]
    print(f"\n  {'═'*55}")
    print(f"  Binary Arithmetic")
    print(f"  {'═'*55}")
    for a, b in pairs:
        da, db = int(a, 2), int(b, 2)
        print(f"\n  A = 0b{a} ({da})    B = 0b{b} ({db})")
        print(f"  {'─'*40}")
        for name, func in ops:
            result = func(a, b)
            print(f"  {name:<15}: 0b{result}")

def hex_arithmetic_demo():
    pairs = [('1F', '0A'), ('FF', '01'), ('3C', '2B')]
    print(f"\n  {'═'*55}")
    print(f"  Hexadecimal Arithmetic")
    print(f"  {'═'*55}")
    for a, b in pairs:
        da, db = int(a, 16), int(b, 16)
        print(f"\n  A = 0x{a} ({da})  B = 0x{b} ({db})")
        print(f"  Add : 0x{format(da+db,'X')} ({da+db})")
        print(f"  Sub : 0x{format(da-db,'X')} ({da-db})" if da >= db else f"  Sub : -0x{format(db-da,'X')}")
        print(f"  Mul : 0x{format(da*db,'X')} ({da*db})")


def main():
    print("╔══════════════════════════════════════════╗")
    print("║   Number System Converter v1.0           ║")
    print("╚══════════════════════════════════════════╝")

    demos = [
        ('255',  10, 2),
        ('1010', 2,  10),
        ('FF',   16, 10),
        ('77',   8,  16),
        ('42',   10, 16),
        ('11111111', 2, 16),
    ]

    for val, fb, tb in demos:
        convert_with_steps(val, fb, tb)

    full_conversion_table('255', 10)
    full_conversion_table('1A3F', 16)

    binary_arithmetic_demo()
    hex_arithmetic_demo()

    print("\n  ── Interactive Mode ──")
    base_map = {'b': 2, 'o': 8, 'd': 10, 'h': 16}
    while True:
        print("\n  [b]inary [o]ctal [d]ecimal [h]ex  or  [q]uit")
        fb_in = input("  From base: ").strip().lower()
        if fb_in == 'q': break
        if fb_in not in base_map:
            print("  Invalid base."); continue
        tb_in = input("  To   base: ").strip().lower()
        if tb_in not in base_map:
            print("  Invalid base."); continue
        val = input(f"  Value: ").strip()
        result, err = convert_with_steps(val, base_map[fb_in], base_map[tb_in])
        if err:
            print(f"  ✗ {err}")
        elif result:
            full_conversion_table(val, base_map[fb_in])


if __name__ == "__main__":
    main()
