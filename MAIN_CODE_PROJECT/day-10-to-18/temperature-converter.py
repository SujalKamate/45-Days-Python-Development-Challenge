"""
Multi-Scale Temperature Unit Conversion System with Range Tables
Supports Celsius, Fahrenheit, Kelvin, and Rankine conversions.
"""


UNITS = ['C', 'F', 'K', 'R']
UNIT_NAMES = {'C': 'Celsius', 'F': 'Fahrenheit', 'K': 'Kelvin', 'R': 'Rankine'}

ABSOLUTE_ZERO = {'C': -273.15, 'F': -459.67, 'K': 0.0, 'R': 0.0}


def to_celsius(value, unit):
    unit = unit.upper()
    if unit == 'C':
        return value
    elif unit == 'F':
        return (value - 32) * 5 / 9
    elif unit == 'K':
        return value - 273.15
    elif unit == 'R':
        return (value - 491.67) * 5 / 9
    raise ValueError(f"Unknown unit: {unit}")


def from_celsius(celsius, unit):
    unit = unit.upper()
    if unit == 'C':
        return celsius
    elif unit == 'F':
        return celsius * 9 / 5 + 32
    elif unit == 'K':
        return celsius + 273.15
    elif unit == 'R':
        return (celsius + 273.15) * 9 / 5
    raise ValueError(f"Unknown unit: {unit}")


def convert(value, from_unit, to_unit):
    from_unit = from_unit.upper()
    to_unit = to_unit.upper()
    if from_unit not in UNITS or to_unit not in UNITS:
        raise ValueError(f"Unsupported units. Use: {UNITS}")
    celsius = to_celsius(value, from_unit)
    if celsius < ABSOLUTE_ZERO['C']:
        raise ValueError(f"Temperature {value}°{from_unit} is below absolute zero!")
    return from_celsius(celsius, to_unit)


def validate_temperature(value, unit):
    unit = unit.upper()
    az = ABSOLUTE_ZERO.get(unit, None)
    if az is not None and value < az:
        return False, f"Below absolute zero for {UNIT_NAMES.get(unit, unit)} (min: {az})"
    return True, "OK"


def batch_convert(entries):
    """
    entries: list of (value, from_unit, to_unit)
    Returns list of results or error strings.
    """
    results = []
    for value, from_unit, to_unit in entries:
        try:
            result = convert(value, from_unit, to_unit)
            results.append((value, from_unit.upper(), to_unit.upper(), round(result, 4), None))
        except Exception as e:
            results.append((value, from_unit.upper(), to_unit.upper(), None, str(e)))
    return results


def print_conversion_table(start, end, step, unit):
    """Print a conversion table for a range in given unit."""
    unit = unit.upper()
    if unit not in UNITS:
        print(f"Unknown unit '{unit}'. Valid: {UNITS}")
        return

    print(f"\n  Temperature Conversion Table ({UNIT_NAMES[unit]} {start} to {end}, step {step})")
    print(f"  {'─'*72}")
    header = f"  {'°'+unit:<10}" + "".join(f"  {'°'+u:<14}" for u in UNITS if u != unit)
    print(header)
    print(f"  {'─'*72}")

    v = start
    while v <= end:
        row = f"  {v:<10.2f}"
        for target in UNITS:
            if target == unit:
                continue
            try:
                converted = convert(v, unit, target)
                row += f"  {converted:<14.4f}"
            except:
                row += f"  {'ERROR':<14}"
        print(row)
        v = round(v + step, 10)
    print(f"  {'─'*72}\n")


def print_batch_results(results):
    print(f"\n  {'─'*60}")
    print(f"  {'From':>10}  {'Unit':>4}  {'To Unit':>7}  {'Result':>14}  {'Note'}")
    print(f"  {'─'*60}")
    for val, fu, tu, res, err in results:
        if err:
            print(f"  {val:>10}  {fu:>4}  {tu:>7}  {'ERROR':>14}  {err}")
        else:
            print(f"  {val:>10}  {fu:>4}  {tu:>7}  {res:>14}  ✓")
    print(f"  {'─'*60}\n")


def interactive_convert():
    print("\n  Interactive Conversion")
    print(f"  Available units: {', '.join(f'{u} ({UNIT_NAMES[u]})' for u in UNITS)}")
    try:
        value = float(input("  Enter temperature value: "))
        from_u = input("  From unit (C/F/K/R): ").strip().upper()
        to_u = input("  To unit   (C/F/K/R): ").strip().upper()
        result = convert(value, from_u, to_u)
        print(f"\n  ✓  {value}°{from_u}  =  {result:.4f}°{to_u}")
    except ValueError as e:
        print(f"  ✗  Error: {e}")


def main():
    print("╔══════════════════════════════════════════╗")
    print("║   Temperature Conversion System v1.0     ║")
    print("╚══════════════════════════════════════════╝")

    # Demo batch conversion
    batch = [
        (100, 'C', 'F'), (32, 'F', 'C'), (0, 'C', 'K'),
        (373.15, 'K', 'C'), (-500, 'C', 'F'), (98.6, 'F', 'K'),
        (0, 'K', 'R'), (671.67, 'R', 'C'),
    ]
    print("\n  Batch Conversion Results:")
    results = batch_convert(batch)
    print_batch_results(results)

    # Conversion table: 0 to 100 °C
    print_conversion_table(0, 100, 10, 'C')

    # Interactive
    while True:
        choice = input("  Perform interactive conversion? (y/n): ").strip().lower()
        if choice == 'y':
            interactive_convert()
        else:
            break

    print("\n  Goodbye!")


if __name__ == "__main__":
    main()
