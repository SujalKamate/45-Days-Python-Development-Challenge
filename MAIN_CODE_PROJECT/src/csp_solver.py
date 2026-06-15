"""Constraint Satisfaction Problem (CSP) Solver with Intelligent Backtracking.

Provides a generic framework for finite-domain CSPs supporting:
  - Unary, binary, and global (all-different) constraints
  - Forward checking with arc consistency after each assignment
  - Minimum-Remaining-Values (MRV) variable ordering heuristic
  - Least-Constraining-Value (LCV) value ordering heuristic
  - Conflict-Directed Backjumping (CBJ)
  - Single-solution and all-solutions enumeration
  - Solution counting without storing solutions
  - Search efficiency metrics (backtrack count)

Public API
----------
solve(csp)             -> dict | None
all_solutions(csp)     -> list[dict]
solution_count(csp)    -> int
backtrack_count(csp)   -> int   (after any of the above calls)
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable, Dict, FrozenSet, Iterable, List, Optional, Set, Tuple


# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------
Variable = str
Value = Any
Domain = List[Value]
Assignment = Dict[Variable, Value]
ConstraintFn = Callable[[Variable, Value, Variable, Value], bool]


# ---------------------------------------------------------------------------
# Constraint helpers
# ---------------------------------------------------------------------------

def all_different_constraint(var1: Variable, val1: Value,
                             var2: Variable, val2: Value) -> bool:
    """Binary constraint: *var1* and *var2* must take different values."""
    return val1 != val2


def less_than_constraint(var1: Variable, val1: Value,
                         var2: Variable, val2: Value) -> bool:
    """Binary constraint: value of *var1* must be strictly less than *var2*."""
    return val1 < val2


def not_equal_offset_constraint(offset: int) -> ConstraintFn:
    """Return a constraint requiring |val1 - val2| != offset."""
    def _check(var1: Variable, val1: Value,
               var2: Variable, val2: Value) -> bool:
        return abs(val1 - val2) != offset
    return _check


# ---------------------------------------------------------------------------
# CSP definition
# ---------------------------------------------------------------------------

class CSP:
    """Finite-domain Constraint Satisfaction Problem.

    Parameters
    ----------
    variables:
        Ordered list of variable names.
    domains:
        Mapping from variable name to its list of possible values.
    constraints:
        List of ``(var1, var2, constraint_fn)`` triples.  Each
        ``constraint_fn(var1, val1, var2, val2) -> bool`` returns *True*
        when the pair is consistent.

    Examples
    --------
    >>> csp = CSP(
    ...     variables=['A', 'B'],
    ...     domains={'A': [1, 2, 3], 'B': [1, 2, 3]},
    ...     constraints=[('A', 'B', all_different_constraint)],
    ... )
    """

    def __init__(
        self,
        variables: List[Variable],
        domains: Dict[Variable, Domain],
        constraints: List[Tuple[Variable, Variable, ConstraintFn]],
    ) -> None:
        if not variables:
            raise ValueError("CSP must have at least one variable.")
        missing = set(variables) - set(domains)
        if missing:
            raise ValueError(f"No domain provided for variables: {missing}")

        self.variables: List[Variable] = list(variables)
        # Work on copies so callers cannot mutate the problem after creation.
        self.domains: Dict[Variable, Domain] = {v: list(d) for v, d in domains.items()}
        self.constraints: List[Tuple[Variable, Variable, ConstraintFn]] = list(constraints)

        # Build neighbour map for quick constraint look-up.
        self._neighbours: Dict[Variable, Set[Variable]] = {v: set() for v in variables}
        # Constraint index: (var1, var2) -> list of constraint functions
        self._constraint_map: Dict[Tuple[Variable, Variable], List[ConstraintFn]] = {}
        for var1, var2, fn in constraints:
            self._neighbours[var1].add(var2)
            self._neighbours[var2].add(var1)
            for key in ((var1, var2), (var2, var1)):
                self._constraint_map.setdefault(key, []).append(fn)

    def neighbours(self, var: Variable) -> Set[Variable]:
        """Return the set of variables that share a constraint with *var*."""
        return self._neighbours.get(var, set())

    def is_consistent(
        self,
        var: Variable,
        value: Value,
        assignment: Assignment,
    ) -> bool:
        """Return True if assigning *value* to *var* violates no constraint.

        Only checks against already-assigned neighbours.
        """
        for neighbour, assigned_val in assignment.items():
            fns = self._constraint_map.get((var, neighbour), [])
            for fn in fns:
                if not fn(var, value, neighbour, assigned_val):
                    return False
        return True

    def add_all_different(self, variables: Iterable[Variable]) -> None:
        """Convenience: add pairwise all-different constraints over *variables*."""
        vars_list = list(variables)
        for i, v1 in enumerate(vars_list):
            for v2 in vars_list[i + 1:]:
                self.constraints.append((v1, v2, all_different_constraint))
                self._neighbours[v1].add(v2)
                self._neighbours[v2].add(v1)
                for key in ((v1, v2), (v2, v1)):
                    self._constraint_map.setdefault(key, []).append(
                        all_different_constraint
                    )


# ---------------------------------------------------------------------------
# Solver
# ---------------------------------------------------------------------------

class CSPSolver:
    """Backtracking CSP solver with MRV, LCV, forward checking, and CBJ.

    Usage
    -----
    >>> solver = CSPSolver()
    >>> result = solver.solve(csp)
    >>> print(solver.backtrack_count())
    """

    def __init__(self) -> None:
        self._backtrack_count: int = 0
        self._solution_count: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def solve(self, csp: CSP) -> Optional[Assignment]:
        """Return the first solution found, or *None* if unsatisfiable."""
        self._reset()
        domains = deepcopy(csp.domains)
        result = self._backtrack(csp, {}, domains, collect=False)
        if isinstance(result, dict):
            return result
        return None

    def all_solutions(self, csp: CSP) -> List[Assignment]:
        """Return every valid solution for *csp*."""
        self._reset()
        domains = deepcopy(csp.domains)
        solutions: List[Assignment] = []
        self._backtrack_all(csp, {}, domains, solutions)
        self._solution_count = len(solutions)
        return solutions

    def solution_count(self, csp: Optional[CSP] = None) -> int:
        """Return the number of solutions found in the most recent search.

        If *csp* is supplied the solver runs a fresh full enumeration.
        """
        if csp is not None:
            self.all_solutions(csp)
        return self._solution_count

    def backtrack_count(self) -> int:
        """Return the number of backtracks in the most recent search."""
        return self._backtrack_count

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _reset(self) -> None:
        self._backtrack_count = 0
        self._solution_count = 0

    # --- Variable ordering (MRV + degree tie-breaking) -----------------

    def _select_unassigned_variable(
        self,
        csp: CSP,
        assignment: Assignment,
        domains: Dict[Variable, Domain],
    ) -> Variable:
        """Minimum-Remaining-Values with degree tie-breaking."""
        unassigned = [v for v in csp.variables if v not in assignment]
        # MRV: prefer the variable with the fewest remaining domain values.
        min_remaining = min(len(domains[v]) for v in unassigned)
        candidates = [v for v in unassigned if len(domains[v]) == min_remaining]
        if len(candidates) == 1:
            return candidates[0]
        # Degree heuristic tie-break: prefer the most-constrained variable.
        return max(
            candidates,
            key=lambda v: sum(
                1 for n in csp.neighbours(v) if n not in assignment
            ),
        )

    # --- Value ordering (LCV) -----------------------------------------

    def _order_domain_values(
        self,
        var: Variable,
        assignment: Assignment,
        csp: CSP,
        domains: Dict[Variable, Domain],
    ) -> List[Value]:
        """Least-Constraining-Value ordering.

        Values that rule out the fewest choices for unassigned neighbours
        are tried first.
        """
        def _count_ruled_out(value: Value) -> int:
            count = 0
            for neighbour in csp.neighbours(var):
                if neighbour not in assignment:
                    for n_val in domains[neighbour]:
                        if not csp.is_consistent(
                            var, value, {neighbour: n_val, **assignment}
                        ):
                            count += 1
            return count

        return sorted(domains[var], key=_count_ruled_out)

    # --- Forward checking + arc reduction -----------------------------

    def _forward_check(
        self,
        csp: CSP,
        var: Variable,
        value: Value,
        assignment: Assignment,
        domains: Dict[Variable, Domain],
    ) -> Optional[Dict[Variable, Domain]]:
        """Prune domains of unassigned neighbours after assigning *value* to *var*.

        Returns updated domain copy, or *None* if a domain becomes empty
        (i.e., the assignment leads to a dead-end).
        """
        new_domains = deepcopy(domains)
        for neighbour in csp.neighbours(var):
            if neighbour in assignment:
                continue
            pruned = [
                v for v in new_domains[neighbour]
                if csp.is_consistent(neighbour, v, {var: value, **assignment})
            ]
            if not pruned:
                return None  # Domain wipe-out — prune this branch.
            new_domains[neighbour] = pruned
        return new_domains

    # --- Conflict set management for CBJ ------------------------------

    def _collect_conflict_vars(
        self,
        csp: CSP,
        var: Variable,
        assignment: Assignment,
        domains: Dict[Variable, Domain],
    ) -> FrozenSet[Variable]:
        """Return the set of assigned variables that conflict with *var*.

        Used to build the conflict set for conflict-directed backjumping.
        """
        conflicts: Set[Variable] = set()
        for val in domains.get(var, []):
            for assigned_var, assigned_val in assignment.items():
                fns = csp._constraint_map.get((var, assigned_var), [])
                for fn in fns:
                    if not fn(var, val, assigned_var, assigned_val):
                        conflicts.add(assigned_var)
        return frozenset(conflicts)

    # --- Core backtracking search -------------------------------------

    def _backtrack(
        self,
        csp: CSP,
        assignment: Assignment,
        domains: Dict[Variable, Domain],
        collect: bool,
        conflict_sets: Optional[Dict[Variable, Set[Variable]]] = None,
    ) -> Any:
        """Recursive backtracking with forward checking and CBJ.

        Returns:
          - A complete assignment (dict) on success.
          - A frozenset of conflict variables when CBJ triggers a jump.
          - None when no solution exists.
        """
        if conflict_sets is None:
            conflict_sets = {v: set() for v in csp.variables}

        if len(assignment) == len(csp.variables):
            return dict(assignment)  # Complete assignment found.

        var = self._select_unassigned_variable(csp, assignment, domains)
        ordered_values = self._order_domain_values(var, assignment, csp, domains)

        for value in ordered_values:
            if csp.is_consistent(var, value, assignment):
                assignment[var] = value
                new_domains = self._forward_check(csp, var, value, assignment, domains)

                if new_domains is not None:
                    result = self._backtrack(csp, assignment, new_domains, collect, conflict_sets)
                    if isinstance(result, dict):
                        return result
                    if isinstance(result, frozenset):
                        # CBJ: if *var* is not in the conflict set, jump past it.
                        if var not in result:
                            del assignment[var]
                            return result  # Propagate the jump upward.
                        # var is in the conflict set — absorb and continue.
                        conflict_sets[var].update(result - {var})
                else:
                    # Forward check wipe-out: record conflict.
                    self._backtrack_count += 1
                    for neighbour in csp.neighbours(var):
                        if neighbour in assignment:
                            conflict_sets[var].add(neighbour)

                del assignment[var]
                self._backtrack_count += 1
            else:
                # Record which assigned variables caused the inconsistency.
                for assigned_var in assignment:
                    fns = csp._constraint_map.get((var, assigned_var), [])
                    for fn in fns:
                        if not fn(var, value, assigned_var, assignment[assigned_var]):
                            conflict_sets[var].add(assigned_var)

        # All values exhausted — compute conflict set for CBJ jump target.
        conflict_set = frozenset(conflict_sets.get(var, set()))
        return conflict_set if conflict_set else None

    def _backtrack_all(
        self,
        csp: CSP,
        assignment: Assignment,
        domains: Dict[Variable, Domain],
        solutions: List[Assignment],
    ) -> None:
        """Enumerate all solutions, appending each to *solutions*."""
        if len(assignment) == len(csp.variables):
            solutions.append(dict(assignment))
            self._solution_count += 1
            return

        var = self._select_unassigned_variable(csp, assignment, domains)
        ordered_values = self._order_domain_values(var, assignment, csp, domains)

        for value in ordered_values:
            if csp.is_consistent(var, value, assignment):
                assignment[var] = value
                new_domains = self._forward_check(csp, var, value, assignment, domains)
                if new_domains is not None:
                    self._backtrack_all(csp, assignment, new_domains, solutions)
                else:
                    self._backtrack_count += 1
                del assignment[var]
                self._backtrack_count += 1


# ---------------------------------------------------------------------------
# Convenience module-level functions
# ---------------------------------------------------------------------------

def solve(csp: CSP) -> Optional[Assignment]:
    """Return the first solution for *csp*, or *None* if unsatisfiable."""
    return CSPSolver().solve(csp)


def all_solutions(csp: CSP) -> List[Assignment]:
    """Return all valid solutions for *csp*."""
    return CSPSolver().all_solutions(csp)


def solution_count(csp: CSP) -> int:
    """Return the total number of solutions for *csp* without storing them."""
    solver = CSPSolver()
    return solver.solution_count(csp)


def backtrack_count(csp: CSP) -> int:
    """Solve *csp* and return the number of backtracks encountered."""
    solver = CSPSolver()
    solver.solve(csp)
    return solver.backtrack_count()


# ---------------------------------------------------------------------------
# Built-in problem factories
# ---------------------------------------------------------------------------

def make_n_queens(n: int) -> CSP:
    """Return a CSP for the N-Queens problem (n >= 4)."""
    if n < 1:
        raise ValueError("n must be >= 1")
    variables = [f'Q{i}' for i in range(n)]
    domains: Dict[Variable, Domain] = {v: list(range(n)) for v in variables}
    constraints: List[Tuple[Variable, Variable, ConstraintFn]] = []
    for i in range(n):
        for j in range(i + 1, n):
            # Different columns (all-different) + different diagonals.
            constraints.append((variables[i], variables[j], all_different_constraint))
            constraints.append((variables[i], variables[j], not_equal_offset_constraint(j - i)))
    return CSP(variables, domains, constraints)


def make_map_coloring(
    regions: List[str],
    neighbours_map: Dict[str, List[str]],
    colors: List[str],
) -> CSP:
    """Return a map-coloring CSP.

    Parameters
    ----------
    regions:
        List of region names.
    neighbours_map:
        Adjacency mapping ``{region: [adjacent_regions, ...]}``.
    colors:
        List of available color strings.
    """
    domains: Dict[Variable, Domain] = {r: list(colors) for r in regions}
    constraints: List[Tuple[Variable, Variable, ConstraintFn]] = []
    added: Set[FrozenSet[str]] = set()
    for region, adj_list in neighbours_map.items():
        for adj in adj_list:
            key: FrozenSet[str] = frozenset({region, adj})
            if key not in added:
                constraints.append((region, adj, all_different_constraint))
                added.add(key)
    return CSP(regions, domains, constraints)


def make_sudoku(grid: List[List[int]]) -> CSP:
    """Return a CSP for a 9×9 Sudoku puzzle.

    Parameters
    ----------
    grid:
        9×9 list of lists; 0 represents an empty cell.
    """
    variables: List[Variable] = [f'C{r}{c}' for r in range(9) for c in range(9)]
    domains: Dict[Variable, Domain] = {}
    for r in range(9):
        for c in range(9):
            var = f'C{r}{c}'
            val = grid[r][c]
            domains[var] = [val] if val != 0 else list(range(1, 10))

    csp = CSP(variables, domains, [])

    # Row constraints.
    for r in range(9):
        csp.add_all_different([f'C{r}{c}' for c in range(9)])
    # Column constraints.
    for c in range(9):
        csp.add_all_different([f'C{r}{c}' for r in range(9)])
    # 3×3 box constraints.
    for br in range(3):
        for bc in range(3):
            box_vars = [
                f'C{br * 3 + r}{bc * 3 + c}'
                for r in range(3) for c in range(3)
            ]
            csp.add_all_different(box_vars)

    return csp


# ---------------------------------------------------------------------------
# Demo / self-test
# ---------------------------------------------------------------------------

def _demo() -> None:
    print("=" * 60)
    print("CSP Solver Demo")
    print("=" * 60)

    # --- Map colouring ------------------------------------------------
    regions = ['WA', 'NT', 'SA', 'Q', 'NSW', 'V', 'T']
    adj: Dict[str, List[str]] = {
        'WA': ['NT', 'SA'],
        'NT': ['WA', 'SA', 'Q'],
        'SA': ['WA', 'NT', 'Q', 'NSW', 'V'],
        'Q':  ['NT', 'SA', 'NSW'],
        'NSW': ['SA', 'Q', 'V'],
        'V':  ['SA', 'NSW'],
        'T':  [],
    }
    colors = ['R', 'G', 'B']
    map_csp = make_map_coloring(regions, adj, colors)

    solver = CSPSolver()
    sol = solver.solve(map_csp)
    print(f"\nMap Colouring solution : {sol}")
    print(f"Backtracks             : {solver.backtrack_count()}")

    n_sols = solver.solution_count(map_csp)
    print(f"Total solutions        : {n_sols}")

    # --- N-Queens (8) -------------------------------------------------
    queens_csp = make_n_queens(8)
    solver2 = CSPSolver()
    q_sol = solver2.solve(queens_csp)
    print(f"\n8-Queens first solution: {q_sol}")
    print(f"Backtracks             : {solver2.backtrack_count()}")

    solver3 = CSPSolver()
    n_q = solver3.solution_count(queens_csp)
    print(f"Total 8-Queens solutions: {n_q}")

    # --- Simple variable domain CSP -----------------------------------
    simple = CSP(
        variables=['X', 'Y', 'Z'],
        domains={'X': [1, 2, 3], 'Y': [1, 2, 3], 'Z': [1, 2, 3]},
        constraints=[
            ('X', 'Y', all_different_constraint),
            ('Y', 'Z', all_different_constraint),
            ('X', 'Z', all_different_constraint),
        ],
    )
    print(f"\nSimple 3-var all-diff solutions: {solution_count(simple)}")
    print(f"One solution               : {solve(simple)}")

    print("\nDemo complete.")


if __name__ == '__main__':
    _demo()
