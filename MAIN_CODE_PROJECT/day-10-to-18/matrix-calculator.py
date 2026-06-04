"""
Matrix Operations Calculator with Determinant and Inverse Support
Implements addition, subtraction, multiplication, transpose, determinant,
and inverse using nested lists. Validates dimensions and pretty-prints.
"""


def make_matrix(rows, cols, fill=0):
    return [[fill] * cols for _ in range(rows)]


def dims(matrix):
    return len(matrix), len(matrix[0]) if matrix else 0


def print_matrix(matrix, label="Matrix"):
    rows, cols = dims(matrix)
    print(f"\n  {label} ({rows}×{cols}):")
    col_w = max(len(f"{matrix[r][c]:.4g}") for r in range(rows) for c in range(cols)) + 2
    top = "  ┌" + " " * (col_w * cols + 1) + "┐"
    bot = "  └" + " " * (col_w * cols + 1) + "┘"
    print(top)
    for row in matrix:
        line = "  │ "
        for val in row:
            s = f"{val:.4g}"
            line += s.rjust(col_w - 1) + " "
        print(line + "│")
    print(bot)


def add(A, B):
    r1, c1 = dims(A); r2, c2 = dims(B)
    if (r1, c1) != (r2, c2):
        raise ValueError(f"Cannot add {r1}×{c1} and {r2}×{c2}")
    return [[A[i][j] + B[i][j] for j in range(c1)] for i in range(r1)]


def subtract(A, B):
    r1, c1 = dims(A); r2, c2 = dims(B)
    if (r1, c1) != (r2, c2):
        raise ValueError(f"Cannot subtract {r1}×{c1} and {r2}×{c2}")
    return [[A[i][j] - B[i][j] for j in range(c1)] for i in range(r1)]


def multiply(A, B):
    r1, c1 = dims(A); r2, c2 = dims(B)
    if c1 != r2:
        raise ValueError(f"Cannot multiply {r1}×{c1} by {r2}×{c2}: inner dims must match.")
    result = make_matrix(r1, c2)
    for i in range(r1):
        for j in range(c2):
            result[i][j] = sum(A[i][k] * B[k][j] for k in range(c1))
    return result


def transpose(A):
    r, c = dims(A)
    return [[A[i][j] for i in range(r)] for j in range(c)]


def scalar_multiply(A, scalar):
    return [[A[i][j] * scalar for j in range(len(A[0]))] for i in range(len(A))]


def identity(n):
    return [[1 if i == j else 0 for j in range(n)] for i in range(n)]


def determinant(A):
    n, m = dims(A)
    if n != m:
        raise ValueError("Determinant only defined for square matrices.")
    if n == 1:
        return A[0][0]
    if n == 2:
        return A[0][0]*A[1][1] - A[0][1]*A[1][0]
    det = 0
    for col in range(n):
        minor = [row[:col] + row[col+1:] for row in A[1:]]
        sign = (-1) ** col
        det += sign * A[0][col] * determinant(minor)
    return det


def cofactor_matrix(A):
    n = len(A)
    cof = make_matrix(n, n)
    for r in range(n):
        for c in range(n):
            minor = [row[:c] + row[c+1:] for i, row in enumerate(A) if i != r]
            cof[r][c] = ((-1) ** (r + c)) * determinant(minor)
    return cof


def inverse(A):
    n, m = dims(A)
    if n != m:
        raise ValueError("Inverse only defined for square matrices.")
    det = determinant(A)
    if abs(det) < 1e-10:
        raise ValueError("Matrix is singular (det ≈ 0); inverse does not exist.")
    cof = cofactor_matrix(A)
    adj = transpose(cof)
    return [[adj[i][j] / det for j in range(n)] for i in range(n)]


def trace(A):
    n, m = dims(A)
    if n != m:
        raise ValueError("Trace only defined for square matrices.")
    return sum(A[i][i] for i in range(n))


def is_symmetric(A):
    return A == transpose(A)


def flatten(A):
    return [A[i][j] for i in range(len(A)) for j in range(len(A[0]))]


def demo():
    A = [[2, 3, 1],
         [4, 1, 0],
         [1, 2, 3]]

    B = [[1, 0, 2],
         [3, 1, 1],
         [0, 2, 1]]

    C = [[1, 2],
         [3, 4]]

    print_matrix(A, "Matrix A")
    print_matrix(B, "Matrix B")

    print_matrix(add(A, B),      "A + B")
    print_matrix(subtract(A, B), "A - B")
    print_matrix(multiply(A, B), "A × B")
    print_matrix(transpose(A),   "Aᵀ (Transpose)")
    print_matrix(scalar_multiply(A, 2), "2A")

    det_A = determinant(A)
    print(f"\n  det(A) = {det_A:.4g}")
    print(f"  trace(A) = {trace(A)}")
    print(f"  A symmetric? {is_symmetric(A)}")

    try:
        inv_C = inverse(C)
        print_matrix(inv_C, "C⁻¹")
        # Verify: C × C⁻¹ should be identity
        result = multiply(C, inv_C)
        print_matrix(result, "C × C⁻¹ (should be I₂)")
    except ValueError as e:
        print(f"  Inverse error: {e}")

    # Test singular matrix
    singular = [[1, 2], [2, 4]]
    print_matrix(singular, "Singular Matrix")
    try:
        inverse(singular)
    except ValueError as e:
        print(f"  ✓ Expected error: {e}")


def main():
    print("╔══════════════════════════════════════════╗")
    print("║   Matrix Operations Calculator v1.0     ║")
    print("╚══════════════════════════════════════════╝")
    demo()


if __name__ == "__main__":
    main()
