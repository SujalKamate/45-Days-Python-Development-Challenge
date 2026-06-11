"""
Text-Based Fractal Pattern Generator with Pascal's Triangle and Sierpinski
Generates Pascal's triangle, Sierpinski triangle, box fractal, and other patterns.
"""

import math


# ── Pascal's Triangle ─────────────────────────────────────────────────────────
def pascals_triangle(rows: int, highlight_even=False):
    """Generate Pascal's triangle up to N rows."""
    triangle = [[1]]
    for i in range(1, rows):
        prev = triangle[-1]
        row  = [1] + [prev[j] + prev[j+1] for j in range(len(prev)-1)] + [1]
        triangle.append(row)
    return triangle


def print_pascals(rows: int, highlight_even=False):
    tri = pascals_triangle(rows)
    max_val  = max(max(row) for row in tri)
    cell_w   = len(str(max_val)) + 1
    max_width = len(tri[-1]) * cell_w

    print(f"\n  Pascal's Triangle ({rows} rows):")
    print(f"  {'─'*max_width}")
    for i, row in enumerate(tri):
        line = ""
        for val in row:
            if highlight_even:
                cell = "  * " if val % 2 == 0 else f"{val:>{cell_w}}"
            else:
                cell = f"{val:>{cell_w}}"
            line += cell
        padding = (max_width - len(line)) // 2
        print(" " * (padding + 2) + line)
    print()


# ── Sierpinski Triangle ───────────────────────────────────────────────────────
def sierpinski_triangle(n: int):
    """
    Generate Sierpinski triangle using Pascal's triangle parity.
    Cells where C(row, col) is odd get '*', others get ' '.
    """
    rows_needed = 2**n
    tri = pascals_triangle(rows_needed)

    print(f"\n  Sierpinski Triangle (n={n}, {rows_needed} rows):")
    max_w = rows_needed * 2
    for i, row in enumerate(tri):
        cells = ["*" if v % 2 != 0 else " " for v in row]
        line  = " ".join(cells)
        pad   = (max_w - len(line)) // 2
        print("  " + " " * pad + line)
    print()


def sierpinski_simple(size: int):
    """Character-art Sierpinski triangle using recursive fill."""
    grid = [[" "] * (2*size) for _ in range(size)]

    def fill(row, col, sz):
        if sz == 1:
            if 0 <= row < size and 0 <= col < 2*size:
                grid[row][col] = "*"
            return
        half = sz // 2
        fill(row,       col,        half)   # top
        fill(row+half,  col-half,   half)   # bottom-left
        fill(row+half,  col+half,   half)   # bottom-right

    fill(0, size-1, size)
    print(f"\n  Sierpinski (simple, size={size}):")
    for row in grid:
        print("  " + "".join(row))
    print()


# ── Box / Cantor Fractal ──────────────────────────────────────────────────────
def cantor_set(n: int, line: str = "█" * 27):
    """Print Cantor set — iteratively remove middle thirds."""
    print(f"\n  Cantor Set (depth={n}):")
    current = [line]
    for depth in range(n):
        print(f"  {depth}: " + " | ".join(current))
        nxt = []
        for seg in current:
            l = len(seg)
            third = l // 3
            nxt.append(seg[:third])
            nxt.append(seg[l-third:])
        current = [s for s in nxt if s]
    if current:
        print(f"  {n}: " + " | ".join(current))
    print()


# ── Box Fractal ───────────────────────────────────────────────────────────────
def box_fractal(depth: int, symbol="█", empty=" "):
    """
    Build a 3×3-based box fractal (Vicsek fractal) at a given depth.
    """
    PATTERN = [
        [1, 0, 1],
        [0, 1, 0],
        [1, 0, 1],
    ]

    def build(d):
        if d == 0:
            return [[symbol]]
        sub = build(d - 1)
        sub_size = len(sub)
        rows = []
        for pr in PATTERN:
            for sr in range(sub_size):
                row = []
                for pc in pr:
                    if pc:
                        row.extend(sub[sr])
                    else:
                        row.extend([empty] * sub_size)
                rows.append(row)
        return rows

    grid = build(depth)
    print(f"\n  Box (Vicsek) Fractal — depth {depth}  ({len(grid)}×{len(grid[0])} cells):")
    for row in grid:
        print("  " + "".join(row))
    print()


# ── Koch Snowflake (ASCII approximation) ─────────────────────────────────────
def dragon_curve(iterations: int):
    """Print a folded strip Dragon Curve as a direction sequence."""
    directions = ["R"]
    for _ in range(iterations):
        mid   = len(directions) // 2
        first = directions[:mid]
        last  = [{"R": "L", "L": "R"}[d] for d in reversed(directions[mid+1:])]
        directions = first + ["R"] + last + [directions[mid]] + ["L"]
    print(f"\n  Dragon Curve (iter={iterations}, {len(directions)} segments):")
    print("  " + "".join(directions[:80]) + ("..." if len(directions) > 80 else ""))
    return directions


# ── Fractal Tree (ASCII) ──────────────────────────────────────────────────────
def fractal_tree(depth: int, width: int = 40):
    """Print an ASCII fractal tree."""
    grid = [[" "] * (width * 2) for _ in range(depth * 2 + 2)]
    center = width

    def draw(x, y, angle_deg, length, d):
        if d == 0 or length < 1:
            return
        angle = math.radians(angle_deg)
        dx = int(round(length * math.sin(angle)))
        dy = int(round(length * math.cos(angle)))
        nx, ny = x + dx, y - dy
        # Draw branch (simple line)
        steps = max(abs(dx), abs(dy))
        for s in range(steps + 1):
            bx = x + dx * s // max(steps, 1)
            by = y - dy * s // max(steps, 1)
            if 0 <= by < len(grid) and 0 <= bx < len(grid[0]):
                grid[by][bx] = "│" if abs(dx) <= 1 else ("/" if dx < 0 else "\\")
        draw(nx, ny, angle_deg - 25, int(length * 0.7), d - 1)
        draw(nx, ny, angle_deg + 25, int(length * 0.7), d - 1)

    draw(center, depth * 2, 0, depth * 2, depth)
    grid[-1][center] = "▲"

    print(f"\n  Fractal Tree (depth={depth}):")
    for row in grid:
        line = "".join(row)
        if line.strip():
            print("  " + line)
    print()


# ── Hilbert Curve (order pattern only) ───────────────────────────────────────
def hilbert_curve_points(order: int):
    """Generate 2D points for a Hilbert curve."""
    def rot(n, x, y, rx, ry):
        if ry == 0:
            if rx == 1:
                x = n - 1 - x
                y = n - 1 - y
            x, y = y, x
        return x, y

    n = 2**order
    points = []
    for d in range(n * n):
        x = y = 0
        s = 1
        t = d
        while s < n:
            rx = 1 if (t & 2) else 0
            ry = 1 if (t & 1) ^ rx else 0
            x, y = rot(s, x, y, rx, ry)
            x += s * rx
            y += s * ry
            t //= 4
            s *= 2
        points.append((x, y))
    return points


def draw_hilbert(order: int):
    size = 2 ** order
    points = hilbert_curve_points(order)
    grid = [[" "] * (size * 2) for _ in range(size)]
    for i, (x, y) in enumerate(points):
        if 0 <= y < size and 0 <= x*2 < size*2:
            grid[size-1-y][x*2] = "·"
    print(f"\n  Hilbert Curve (order={order}, {size}×{size} grid):")
    for row in grid:
        print("  " + "".join(row))
    print()


def main():
    print("╔══════════════════════════════════════════╗")
    print("║   Text Fractal Pattern Generator v1.0  ║")
    print("╚══════════════════════════════════════════╝")

    # Pascal's triangle
    print_pascals(8)
    print_pascals(12, highlight_even=True)

    # Sierpinski
    sierpinski_triangle(3)
    sierpinski_simple(8)

    # Cantor set
    cantor_set(5)

    # Box fractal
    for d in range(1, 4):
        box_fractal(d)

    # Fractal tree
    fractal_tree(5)

    # Dragon curve
    dragon_curve(6)

    # Hilbert curve
    draw_hilbert(3)

    while True:
        print("\n  [1] Pascal  [2] Sierpinski  [3] Box  [4] Tree  [5] Quit")
        choice = input("  Choice: ").strip()
        if choice == "5": break
        try:
            n = int(input("  Depth/rows: "))
            if choice == "1": print_pascals(n)
            elif choice == "2": sierpinski_triangle(min(n, 4))
            elif choice == "3": box_fractal(min(n, 3))
            elif choice == "4": fractal_tree(min(n, 6))
        except ValueError:
            print("  Invalid number.")


if __name__ == "__main__":
    main()
