# Classroom Seating Arrangement Generator

import random

students = []
no_pair_rules = []
arrangements = {}

def add_students(names):
    for name in names:
        if name not in students:
            students.append(name)
    print(f"  {len(names)} student(s) added. Total: {len(students)}")

def add_no_pair_rule(s1, s2):
    rule = tuple(sorted([s1, s2]))
    if rule not in no_pair_rules:
        no_pair_rules.append(rule)
        print(f"  Rule added: '{s1}' and '{s2}' must not sit together.")

def is_adjacent(seat_map, s1, s2, cols):
    pos = {v: k for k, v in seat_map.items()}
    if s1 not in pos or s2 not in pos:
        return False
    r1, c1 = pos[s1]
    r2, c2 = pos[s2]
    return abs(r1 - r2) <= 1 and abs(c1 - c2) <= 1

def generate_arrangement(layout_name, rows, cols, attempts=200):
    seats_needed = rows * cols
    shuffled = students.copy()
    for attempt in range(attempts):
        random.shuffle(shuffled)
        seat_map = {}
        idx = 0
        for r in range(rows):
            for c in range(cols):
                if idx < len(shuffled):
                    seat_map[(r, c)] = shuffled[idx]
                    idx += 1
                else:
                    seat_map[(r, c)] = "---"
        valid = True
        for s1, s2 in no_pair_rules:
            if is_adjacent(seat_map, s1, s2, cols):
                valid = False
                break
        if valid:
            arrangements[layout_name] = {"rows": rows, "cols": cols, "map": seat_map}
            print(f"  Arrangement '{layout_name}' ({rows}x{cols}) generated in {attempt+1} attempt(s).")
            return True
    print(f"  Could not satisfy all rules after {attempts} attempts for '{layout_name}'.")
    return False

def print_seating_chart(layout_name):
    if layout_name not in arrangements:
        print("  Layout not found.")
        return
    a = arrangements[layout_name]
    rows, cols = a["rows"], a["cols"]
    seat_map = a["map"]
    print(f"\n{'='*50}")
    print(f"  SEATING CHART — {layout_name}  ({rows}x{cols})")
    print(f"  [BOARD / FRONT]")
    print(f"{'='*50}")
    for r in range(rows):
        row_str = "  "
        for c in range(cols):
            name = seat_map.get((r, c), "---")
            row_str += f"{name[:10]:<12}"
        print(row_str)
    print(f"{'='*50}")

def check_violations(layout_name):
    if layout_name not in arrangements:
        return
    a = arrangements[layout_name]
    cols = a["cols"]
    violations = []
    for s1, s2 in no_pair_rules:
        if is_adjacent(a["map"], s1, s2, cols):
            violations.append((s1, s2))
    if violations:
        print(f"  VIOLATIONS in '{layout_name}':")
        for v in violations:
            print(f"    ⚠ {v[0]} and {v[1]} are adjacent!")
    else:
        print(f"  No rule violations in '{layout_name}'.")

def swap_seats(layout_name, s1, s2):
    if layout_name not in arrangements:
        print("  Layout not found.")
        return
    seat_map = arrangements[layout_name]["map"]
    pos = {v: k for k, v in seat_map.items()}
    if s1 not in pos or s2 not in pos:
        print("  One or both students not found in layout.")
        return
    p1, p2 = pos[s1], pos[s2]
    seat_map[p1], seat_map[p2] = seat_map[p2], seat_map[p1]
    print(f"  Swapped: {s1} ↔ {s2} in '{layout_name}'")

def main():
    print("=== Classroom Seating Arrangement Generator ===")
    add_students(["Alice","Bob","Charlie","Diana","Eve","Frank",
                  "Grace","Hank","Iris","Jack","Karen","Leo",
                  "Mia","Nate","Olivia","Paul","Quinn","Rita"])
    add_no_pair_rule("Alice", "Bob")
    add_no_pair_rule("Charlie", "Diana")
    add_no_pair_rule("Eve", "Frank")
    add_no_pair_rule("Grace", "Hank")
    generate_arrangement("Standard 6x3", 3, 6)
    generate_arrangement("U-Shape 3x6", 3, 6)
    print_seating_chart("Standard 6x3")
    check_violations("Standard 6x3")
    swap_seats("Standard 6x3", "Quinn", "Rita")
    print("\nAfter swap:")
    print_seating_chart("Standard 6x3")

if __name__ == "__main__":
    main()
