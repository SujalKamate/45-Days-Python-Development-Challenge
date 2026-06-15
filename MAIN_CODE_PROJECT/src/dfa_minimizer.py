"""
DFA Minimization and Automata Optimization Using Hopcroft's Algorithm
=====================================================================
Minimizes deterministic finite automata (DFAs) via Hopcroft's
partition-refinement algorithm.

Capabilities
------------
* Accept DFAs defined as explicit state/transition tables.
* Convert NFAs to DFAs via subset construction.
* Remove unreachable and dead (non-accepting-reachable) states.
* Partition states into equivalence classes using Hopcroft's algorithm.
* Generate an equivalent minimal DFA.
* Report state-reduction and partition-refinement statistics.

Public API
----------
  minimize(dfa)              -> MinimizedDFA
  MinimizedDFA.equivalent_states()   -> list[frozenset[str]]
  MinimizedDFA.partition()           -> list[frozenset[str]]
  MinimizedDFA.transition_table()    -> dict[str, dict[str, str]]
  MinimizedDFA.stats()               -> dict[str, Any]

  NFA                        -- NFA container
  DFA                        -- DFA container
  nfa_to_dfa(nfa)            -> DFA   (subset construction)
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, List, Optional, Set, Tuple


# ---------------------------------------------------------------------------
# Core automata data structures
# ---------------------------------------------------------------------------

@dataclass
class DFA:
    """
    Deterministic Finite Automaton.

    Parameters
    ----------
    states : set of str
        All state names.
    alphabet : set of str
        Input symbols (single characters or labels).
    transitions : dict[state, dict[symbol, state]]
        ``transitions[q][a]`` gives the unique next state from *q* on *a*.
        Missing entries are treated as transitions to an implicit dead state.
    start : str
        The start state (must be in *states*).
    accept : set of str
        Accepting / final states (subset of *states*).
    """
    states: Set[str]
    alphabet: Set[str]
    transitions: Dict[str, Dict[str, str]]
    start: str
    accept: Set[str]

    def __post_init__(self) -> None:
        if self.start not in self.states:
            raise ValueError(f"Start state '{self.start}' not in states.")
        if not self.accept.issubset(self.states):
            missing = self.accept - self.states
            raise ValueError(f"Accept states not in states: {missing}")


@dataclass
class NFA:
    """
    Nondeterministic Finite Automaton (with epsilon transitions).

    Parameters
    ----------
    states : set of str
        All state names.
    alphabet : set of str
        Input symbols (excluding epsilon).
    transitions : dict[state, dict[symbol | 'ε', set[state]]]
        ``transitions[q][a]`` is the set of states reachable from *q* on *a*.
        Use ``'ε'`` for epsilon transitions.
    start : str
        The start state.
    accept : set of str
        Accepting states.
    """
    states: Set[str]
    alphabet: Set[str]
    transitions: Dict[str, Dict[str, Set[str]]]
    start: str
    accept: Set[str]


# ---------------------------------------------------------------------------
# NFA -> DFA  (subset construction)
# ---------------------------------------------------------------------------

def nfa_to_dfa(nfa: NFA) -> DFA:
    """
    Convert *nfa* to an equivalent DFA using the subset-construction algorithm.

    Returns
    -------
    DFA
        Equivalent deterministic automaton (may contain unreachable states
        only if the NFA has them; call :func:`minimize` to clean up).
    """

    def _epsilon_closure(states: FrozenSet[str]) -> FrozenSet[str]:
        closure: Set[str] = set(states)
        stack = list(states)
        while stack:
            q = stack.pop()
            for t in nfa.transitions.get(q, {}).get("ε", set()):
                if t not in closure:
                    closure.add(t)
                    stack.append(t)
        return frozenset(closure)

    def _move(states: FrozenSet[str], symbol: str) -> FrozenSet[str]:
        result: Set[str] = set()
        for q in states:
            result.update(nfa.transitions.get(q, {}).get(symbol, set()))
        return frozenset(result)

    start_set = _epsilon_closure(frozenset({nfa.start}))
    # Map frozenset -> DFA state name
    state_map: Dict[FrozenSet[str], str] = {start_set: _set_name(start_set)}
    queue: deque[FrozenSet[str]] = deque([start_set])
    dfa_transitions: Dict[str, Dict[str, str]] = {}
    dfa_states: Set[str] = {state_map[start_set]}
    dfa_accept: Set[str] = set()

    while queue:
        current = queue.popleft()
        cname = state_map[current]
        dfa_transitions.setdefault(cname, {})
        if current & nfa.accept:
            dfa_accept.add(cname)
        for sym in nfa.alphabet:
            moved = _epsilon_closure(_move(current, sym))
            if not moved:
                continue
            if moved not in state_map:
                state_map[moved] = _set_name(moved)
                queue.append(moved)
                dfa_states.add(state_map[moved])
            dfa_transitions[cname][sym] = state_map[moved]

    return DFA(
        states=dfa_states,
        alphabet=nfa.alphabet,
        transitions=dfa_transitions,
        start=state_map[start_set],
        accept=dfa_accept,
    )


def _set_name(states: FrozenSet[str]) -> str:
    """Stable name for a subset-construction super-state."""
    return "{" + ",".join(sorted(states)) + "}"


# ---------------------------------------------------------------------------
# Reachability and dead-state pruning
# ---------------------------------------------------------------------------

def _reachable_states(dfa: DFA) -> Set[str]:
    """BFS from start; return all reachable state names."""
    visited: Set[str] = set()
    queue: deque[str] = deque([dfa.start])
    while queue:
        q = queue.popleft()
        if q in visited:
            continue
        visited.add(q)
        for sym in dfa.alphabet:
            nxt = dfa.transitions.get(q, {}).get(sym)
            if nxt and nxt not in visited:
                queue.append(nxt)
    return visited


def _live_states(dfa: DFA) -> Set[str]:
    """
    Return states from which an accepting state is reachable (reverse BFS).
    Dead states (traps) are excluded.
    """
    # Build reverse graph
    reverse: Dict[str, Set[str]] = {q: set() for q in dfa.states}
    for q, trans in dfa.transitions.items():
        for sym, nxt in trans.items():
            if nxt in reverse:
                reverse[nxt].add(q)

    live: Set[str] = set(dfa.accept)
    queue: deque[str] = deque(dfa.accept)
    while queue:
        q = queue.popleft()
        for pred in reverse.get(q, set()):
            if pred not in live:
                live.add(pred)
                queue.append(pred)
    return live


def _prune(dfa: DFA) -> DFA:
    """Remove unreachable and dead states from *dfa*."""
    keep = _reachable_states(dfa) & _live_states(dfa)
    if dfa.start not in keep:
        # Edge case: start is dead; return trivially empty DFA
        keep = {dfa.start}
    new_trans: Dict[str, Dict[str, str]] = {}
    for q in keep:
        row: Dict[str, str] = {}
        for sym, nxt in dfa.transitions.get(q, {}).items():
            if nxt in keep:
                row[sym] = nxt
        new_trans[q] = row
    return DFA(
        states=keep,
        alphabet=dfa.alphabet,
        transitions=new_trans,
        start=dfa.start,
        accept=dfa.accept & keep,
    )


# ---------------------------------------------------------------------------
# Hopcroft's partition-refinement
# ---------------------------------------------------------------------------

def _hopcroft(dfa: DFA) -> List[FrozenSet[str]]:
    """
    Run Hopcroft's algorithm on a pruned DFA.

    Returns
    -------
    list of frozenset
        The final partition: each frozenset is a group of equivalent states.
    """
    non_accept = dfa.states - dfa.accept
    # Initial partition: {accept states}, {non-accept states}
    partition: List[FrozenSet[str]] = []
    if dfa.accept:
        partition.append(frozenset(dfa.accept))
    if non_accept:
        partition.append(frozenset(non_accept))

    # Worklist: start with the smaller of the two initial sets
    worklist: deque[FrozenSet[str]] = deque(partition)

    # Build reverse transition map: rev[sym][q] = set of predecessors of q on sym
    rev: Dict[str, Dict[str, Set[str]]] = {sym: {} for sym in dfa.alphabet}
    for q in dfa.states:
        for sym in dfa.alphabet:
            nxt = dfa.transitions.get(q, {}).get(sym)
            if nxt:
                rev[sym].setdefault(nxt, set()).add(q)

    # Map each state -> its current partition block index for O(1) lookup
    state_to_block: Dict[str, int] = {}
    for idx, block in enumerate(partition):
        for s in block:
            state_to_block[s] = idx

    while worklist:
        splitter = worklist.popleft()
        for sym in dfa.alphabet:
            # X = predecessors of splitter on sym
            X: Set[str] = set()
            for q in splitter:
                X.update(rev[sym].get(q, set()))
            if not X:
                continue
            new_partition: List[FrozenSet[str]] = []
            for block in partition:
                inter = block & X
                diff = block - X
                if inter and diff:
                    new_partition.append(frozenset(inter))
                    new_partition.append(frozenset(diff))
                    if block in worklist:
                        worklist.remove(block)
                        worklist.append(frozenset(inter))
                        worklist.append(frozenset(diff))
                    else:
                        # Add the smaller piece
                        worklist.append(
                            frozenset(inter) if len(inter) <= len(diff)
                            else frozenset(diff)
                        )
                else:
                    new_partition.append(block)
            partition = new_partition

    return partition


# ---------------------------------------------------------------------------
# Minimized DFA wrapper
# ---------------------------------------------------------------------------

class MinimizedDFA:
    """
    Result of minimizing a DFA.

    Do not construct directly; use :func:`minimize`.
    """

    def __init__(
        self,
        original: DFA,
        pruned: DFA,
        blocks: List[FrozenSet[str]],
        minimal: DFA,
    ) -> None:
        self._original = original
        self._pruned = pruned
        self._blocks = blocks
        self._minimal = minimal

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def equivalent_states(self) -> List[FrozenSet[str]]:
        """
        Return groups of equivalent (indistinguishable) states from the
        original DFA.  Each group collapses into a single state in the
        minimal DFA.

        Returns
        -------
        list of frozenset
            Groups with more than one state are the "merged" equivalences.
        """
        return [b for b in self._blocks if len(b) > 1]

    def partition(self) -> List[FrozenSet[str]]:
        """
        Return the complete final partition produced by Hopcroft's algorithm.
        Each block in the partition corresponds to exactly one state in the
        minimal DFA.

        Returns
        -------
        list of frozenset[str]
        """
        return list(self._blocks)

    def transition_table(self) -> Dict[str, Dict[str, str]]:
        """
        Return the transition table of the **minimal** DFA.

        Keys are representative state names (one per equivalence class).
        Values are dicts mapping input symbol -> next representative state.

        Returns
        -------
        dict[str, dict[str, str]]
        """
        return {
            q: dict(row)
            for q, row in self._minimal.transitions.items()
        }

    def minimal_dfa(self) -> DFA:
        """Return the fully constructed minimal :class:`DFA` object."""
        return self._minimal

    def stats(self) -> Dict[str, Any]:
        """
        Return a statistics dictionary::

            {
                "original_states":  int,
                "pruned_states":    int,
                "minimal_states":   int,
                "states_removed":   int,
                "reduction_pct":    float,   # percentage reduction
                "partitions":       int,     # number of equivalence classes
                "equivalent_groups": int,    # groups with >1 member
            }
        """
        orig = len(self._original.states)
        pruned = len(self._pruned.states)
        minimal = len(self._minimal.states)
        removed = orig - minimal
        return {
            "original_states": orig,
            "pruned_states": pruned,
            "minimal_states": minimal,
            "states_removed": removed,
            "reduction_pct": round(100.0 * removed / orig, 2) if orig else 0.0,
            "partitions": len(self._blocks),
            "equivalent_groups": len(self.equivalent_states()),
        }

    def __repr__(self) -> str:
        s = self.stats()
        return (
            f"MinimizedDFA(original={s['original_states']} states, "
            f"minimal={s['minimal_states']} states, "
            f"reduction={s['reduction_pct']}%)"
        )


# ---------------------------------------------------------------------------
# minimize() — main entry point
# ---------------------------------------------------------------------------

def minimize(dfa: DFA) -> MinimizedDFA:
    """
    Minimize *dfa* using Hopcroft's partition-refinement algorithm.

    Steps performed
    ---------------
    1. Remove unreachable and dead states.
    2. Run Hopcroft's algorithm to obtain the coarsest stable partition.
    3. Build the minimal DFA from the partition blocks.

    Parameters
    ----------
    dfa : DFA
        The input deterministic finite automaton.

    Returns
    -------
    MinimizedDFA
        Object providing the minimized automaton and all statistics.
    """
    pruned = _prune(dfa)

    # Edge case: empty language (no reachable accepting states)
    if not pruned.accept:
        # Single dead state
        dead = pruned.start
        blocks: List[FrozenSet[str]] = [frozenset(pruned.states)]
        minimal = DFA(
            states={dead},
            alphabet=dfa.alphabet,
            transitions={dead: {}},
            start=dead,
            accept=set(),
        )
        return MinimizedDFA(dfa, pruned, blocks, minimal)

    blocks = _hopcroft(pruned)

    # Build representative map: state -> representative of its block
    rep_of: Dict[str, str] = {}
    for block in blocks:
        rep = min(block)           # lexicographically smallest as canonical name
        for s in block:
            rep_of[s] = rep

    # Determine minimal DFA components
    min_states: Set[str] = {rep_of[q] for q in pruned.states}
    min_start = rep_of[pruned.start]
    min_accept: Set[str] = {rep_of[q] for q in pruned.accept}
    min_trans: Dict[str, Dict[str, str]] = {q: {} for q in min_states}
    for q in pruned.states:
        r = rep_of[q]
        for sym, nxt in pruned.transitions.get(q, {}).items():
            min_trans[r][sym] = rep_of[nxt]

    minimal = DFA(
        states=min_states,
        alphabet=dfa.alphabet,
        transitions=min_trans,
        start=min_start,
        accept=min_accept,
    )
    return MinimizedDFA(dfa, pruned, blocks, minimal)


# ---------------------------------------------------------------------------
# Automata comparison
# ---------------------------------------------------------------------------

def are_equivalent(dfa1: DFA, dfa2: DFA) -> bool:
    """
    Determine whether *dfa1* and *dfa2* accept the same language.

    Uses the table-filling (distinguishability) method on the product automaton.

    Returns
    -------
    bool
        True if both DFAs are language-equivalent.
    """
    if dfa1.alphabet != dfa2.alphabet:
        return False

    alphabet = dfa1.alphabet

    # Product automaton states: pairs (q1, q2)
    # Accept iff exactly one of the pair is accepting (symmetric difference)
    visited: Set[Tuple[str, str]] = set()
    queue: deque[Tuple[str, str]] = deque([(dfa1.start, dfa2.start)])
    while queue:
        q1, q2 = queue.popleft()
        if (q1, q2) in visited:
            continue
        visited.add((q1, q2))
        # If one is accepting and the other isn't -> not equivalent
        if (q1 in dfa1.accept) != (q2 in dfa2.accept):
            return False
        for sym in alphabet:
            n1 = dfa1.transitions.get(q1, {}).get(sym)
            n2 = dfa2.transitions.get(q2, {}).get(sym)
            if n1 is None and n2 is None:
                continue
            if (n1 is None) != (n2 is None):
                # One has a transition, the other goes to implicit dead state
                return False
            if (n1, n2) not in visited:
                queue.append((n1, n2))  # type: ignore[arg-type]
    return True
