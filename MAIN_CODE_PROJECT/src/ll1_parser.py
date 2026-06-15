"""
LL(1) Parser Generation with Predictive Parsing Table Construction Framework
=============================================================================
Automatically computes FIRST / FOLLOW sets, builds the LL(1) predictive
parsing table, detects grammar conflicts, and drives a table-driven parser
with panic-mode error recovery.

Terminology
-----------
  Nonterminal  – uppercase or user-defined grammar variables (e.g. "S", "E")
  Terminal     – lowercase tokens / literals (e.g. "id", "+", "(")
  EPSILON      – the empty string (represented by the constant below)
  EOF          – end-of-input marker fed to the parser

Public API
----------
  Grammar(start, rules)           – grammar container
  LL1Generator(grammar)           – parser-generator
    .compute_first()              -> dict[str, set[str]]
    .compute_follow()             -> dict[str, set[str]]
    .parsing_table()              -> dict[str, dict[str, list[str]]]
    .is_ll1()                     -> bool
    .conflicts()                  -> list[Conflict]
    .stats()                      -> dict[str, Any]
  LL1Parser(generator)            – table-driven parser
    .parse(tokens)                -> ParseResult
  parse(grammar, tokens)          – convenience one-shot wrapper
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, List, Optional, Set, Tuple

# ---------------------------------------------------------------------------
# Sentinels
# ---------------------------------------------------------------------------

EPSILON: str = "ε"   # empty-string symbol
EOF: str = "$"        # end-of-input marker


# ---------------------------------------------------------------------------
# Grammar data structures
# ---------------------------------------------------------------------------

@dataclass
class Production:
    """A single grammar production  lhs -> rhs."""
    lhs: str                   # nonterminal on the left
    rhs: List[str]             # list of symbols on the right (may contain EPSILON)

    def __str__(self) -> str:
        rhs_str = " ".join(self.rhs) if self.rhs else EPSILON
        return f"{self.lhs} -> {rhs_str}"


class Grammar:
    """
    Context-free grammar container.

    Parameters
    ----------
    start : str
        The start (root) nonterminal symbol.
    rules : list of Production
        All grammar productions.  Each production must be either
        ``lhs -> [sym1, sym2, ...]`` or an epsilon production
        ``lhs -> [EPSILON]``.

    Notes
    -----
    Terminals are any symbol that appears on a RHS but is *not* a LHS of any
    production (and is not EPSILON).  Nonterminals are all LHS symbols.
    """

    def __init__(self, start: str, rules: List[Production]) -> None:
        self.start = start
        self.productions: List[Production] = rules

        # Build sets of nonterminals and terminals
        lhs_set: Set[str] = {p.lhs for p in rules}
        self.nonterminals: Set[str] = lhs_set
        self.terminals: Set[str] = set()
        for p in rules:
            for sym in p.rhs:
                if sym != EPSILON and sym not in lhs_set:
                    self.terminals.add(sym)
        self.terminals.add(EOF)

        # Lookup: nonterminal -> list of its productions
        self._prods_for: Dict[str, List[Production]] = {nt: [] for nt in self.nonterminals}
        for p in rules:
            self._prods_for[p.lhs].append(p)

    def productions_for(self, nonterminal: str) -> List[Production]:
        """Return all productions whose LHS is *nonterminal*."""
        return self._prods_for.get(nonterminal, [])

    def is_nonterminal(self, sym: str) -> bool:
        return sym in self.nonterminals

    def is_terminal(self, sym: str) -> bool:
        return sym in self.terminals or (sym != EPSILON and not self.is_nonterminal(sym))


# ---------------------------------------------------------------------------
# Conflict descriptor
# ---------------------------------------------------------------------------

@dataclass
class Conflict:
    """Describes an LL(1) conflict in the parsing table."""
    kind: str                      # "FIRST/FIRST" or "FIRST/FOLLOW"
    nonterminal: str
    lookahead: str
    productions: List[Production]  # conflicting productions

    def __str__(self) -> str:
        prods = " | ".join(str(p) for p in self.productions)
        return (
            f"[{self.kind}] Conflict on ({self.nonterminal!r}, {self.lookahead!r}): "
            f"{prods}"
        )


# ---------------------------------------------------------------------------
# LL(1) Generator
# ---------------------------------------------------------------------------

class LL1Generator:
    """
    Computes FIRST / FOLLOW sets and the LL(1) predictive parsing table for a
    given :class:`Grammar`.

    Usage::

        grammar = Grammar("S", [...])
        gen     = LL1Generator(grammar)
        first   = gen.compute_first()
        follow  = gen.compute_follow()
        table   = gen.parsing_table()
        ok      = gen.is_ll1()
    """

    def __init__(self, grammar: Grammar) -> None:
        self._grammar = grammar
        self._first: Optional[Dict[str, Set[str]]] = None
        self._follow: Optional[Dict[str, Set[str]]] = None
        self._table: Optional[Dict[str, Dict[str, List[str]]]] = None
        self._conflicts: Optional[List[Conflict]] = None

    # ------------------------------------------------------------------
    # FIRST sets
    # ------------------------------------------------------------------

    def compute_first(self) -> Dict[str, Set[str]]:
        """
        Compute and return the FIRST sets for every grammar symbol.

        FIRST(X) = set of terminals that begin strings derivable from X.
        EPSILON is included if X can derive the empty string.

        Returns
        -------
        dict[str, set[str]]
            Mapping from symbol name to its FIRST set.
        """
        if self._first is not None:
            return self._first

        g = self._grammar
        first: Dict[str, Set[str]] = {}

        # Initialise: terminals are their own FIRST set
        for t in g.terminals:
            first[t] = {t}
        first[EPSILON] = {EPSILON}

        # Nonterminals start empty
        for nt in g.nonterminals:
            first[nt] = set()

        changed = True
        while changed:
            changed = False
            for prod in g.productions:
                lhs = prod.lhs
                rhs = prod.rhs
                added = _first_of_sequence(rhs, first)
                before = len(first[lhs])
                first[lhs].update(added)
                if len(first[lhs]) != before:
                    changed = True

        self._first = first
        return first

    # ------------------------------------------------------------------
    # FOLLOW sets
    # ------------------------------------------------------------------

    def compute_follow(self) -> Dict[str, Set[str]]:
        """
        Compute and return the FOLLOW sets for every nonterminal.

        FOLLOW(A) = set of terminals that can appear immediately to the
        right of A in some sentential form.  EOF is in FOLLOW(start).

        Returns
        -------
        dict[str, set[str]]
            Mapping from nonterminal name to its FOLLOW set.
        """
        if self._follow is not None:
            return self._follow

        first = self.compute_first()
        g = self._grammar

        follow: Dict[str, Set[str]] = {nt: set() for nt in g.nonterminals}
        follow[g.start].add(EOF)

        changed = True
        while changed:
            changed = False
            for prod in g.productions:
                lhs = prod.lhs
                rhs = prod.rhs
                trailer: Set[str] = set(follow[lhs])
                for sym in reversed(rhs):
                    if sym == EPSILON:
                        continue
                    if g.is_nonterminal(sym):
                        before = len(follow[sym])
                        follow[sym].update(trailer)
                        if len(follow[sym]) != before:
                            changed = True
                        if EPSILON in first.get(sym, set()):
                            trailer = trailer | (first[sym] - {EPSILON})
                        else:
                            trailer = set(first.get(sym, set())) - {EPSILON}
                    else:
                        # Terminal: trailer resets
                        trailer = set(first.get(sym, {sym})) - {EPSILON}

        self._follow = follow
        return follow

    # ------------------------------------------------------------------
    # Parsing table
    # ------------------------------------------------------------------

    def parsing_table(self) -> Dict[str, Dict[str, List[str]]]:
        """
        Build and return the LL(1) predictive parsing table.

        The table is indexed as ``table[A][a]`` where *A* is a nonterminal
        and *a* is a terminal (lookahead).  The value is the RHS list of the
        production to apply.  If a cell contains multiple entries a conflict
        exists.

        Returns
        -------
        dict[str, dict[str, list[str]]]
        """
        if self._table is not None:
            return self._table

        first = self.compute_first()
        follow = self.compute_follow()
        g = self._grammar

        # table[A][a] -> list of RHS (multiple = conflict)
        raw: Dict[str, Dict[str, List[List[str]]]] = {
            nt: {} for nt in g.nonterminals
        }
        conflicts: List[Conflict] = []

        for prod in g.productions:
            lhs = prod.lhs
            rhs = prod.rhs
            first_rhs = _first_of_sequence(rhs, first)

            for terminal in first_rhs - {EPSILON}:
                raw[lhs].setdefault(terminal, []).append(rhs)

            if EPSILON in first_rhs:
                for terminal in follow[lhs]:
                    raw[lhs].setdefault(terminal, []).append(rhs)

        # Flatten and record conflicts
        table: Dict[str, Dict[str, List[str]]] = {}
        for nt, row in raw.items():
            table[nt] = {}
            for terminal, rhss in row.items():
                if len(rhss) > 1:
                    # Record conflict
                    prods = [Production(nt, r) for r in rhss]
                    kind = "FIRST/FIRST"
                    # Detect FIRST/FOLLOW conflict: epsilon in first_rhs and
                    # terminal is in FOLLOW -> FIRST/FOLLOW
                    for r in rhss:
                        fr = _first_of_sequence(r, first)
                        if EPSILON in fr:
                            kind = "FIRST/FOLLOW"
                            break
                    conflicts.append(
                        Conflict(kind=kind, nonterminal=nt,
                                 lookahead=terminal, productions=prods)
                    )
                # Keep first entry for driving the parser (best-effort)
                table[nt][terminal] = rhss[0]

        self._table = table
        self._conflicts = conflicts
        return table

    # ------------------------------------------------------------------
    # LL(1) check and diagnostics
    # ------------------------------------------------------------------

    def is_ll1(self) -> bool:
        """
        Return True if the grammar is LL(1) (no conflicts in the parsing table).
        """
        self.parsing_table()  # ensure computed
        return len(self._conflicts or []) == 0

    def conflicts(self) -> List[Conflict]:
        """
        Return all detected parsing-table conflicts.

        Each entry is a :class:`Conflict` with kind ``'FIRST/FIRST'`` or
        ``'FIRST/FOLLOW'``.
        """
        self.parsing_table()
        return list(self._conflicts or [])

    def stats(self) -> Dict[str, Any]:
        """
        Return parser-generation statistics::

            {
                "nonterminals":       int,
                "terminals":          int,
                "productions":        int,
                "table_entries":      int,
                "conflict_count":     int,
                "is_ll1":             bool,
                "first_set_sizes":    dict[str, int],
                "follow_set_sizes":   dict[str, int],
            }
        """
        first = self.compute_first()
        follow = self.compute_follow()
        table = self.parsing_table()
        g = self._grammar
        entries = sum(len(row) for row in table.values())
        return {
            "nonterminals": len(g.nonterminals),
            "terminals": len(g.terminals),
            "productions": len(g.productions),
            "table_entries": entries,
            "conflict_count": len(self._conflicts or []),
            "is_ll1": self.is_ll1(),
            "first_set_sizes": {sym: len(s) for sym, s in first.items()
                                 if g.is_nonterminal(sym)},
            "follow_set_sizes": {nt: len(s) for nt, s in follow.items()},
        }


# ---------------------------------------------------------------------------
# Helper: FIRST of a sequence of symbols
# ---------------------------------------------------------------------------

def _first_of_sequence(
    symbols: List[str], first: Dict[str, Set[str]]
) -> Set[str]:
    """Compute FIRST of a sequence of grammar symbols."""
    result: Set[str] = set()
    for sym in symbols:
        sym_first = first.get(sym, {sym})
        result.update(sym_first - {EPSILON})
        if EPSILON not in sym_first:
            return result
    result.add(EPSILON)
    return result


# ---------------------------------------------------------------------------
# Parse result
# ---------------------------------------------------------------------------

@dataclass
class ParseResult:
    """Result returned by :class:`LL1Parser`."""
    accepted: bool
    tokens: List[str]
    steps: List[str] = field(default_factory=list)   # human-readable trace
    errors: List[str] = field(default_factory=list)  # error messages

    def __repr__(self) -> str:
        status = "ACCEPTED" if self.accepted else "REJECTED"
        return (
            f"ParseResult({status}, tokens={self.tokens}, "
            f"errors={len(self.errors)})"
        )


# ---------------------------------------------------------------------------
# LL(1) Table-driven parser with panic-mode error recovery
# ---------------------------------------------------------------------------

class LL1Parser:
    """
    Table-driven LL(1) parser backed by a :class:`LL1Generator`.

    Implements panic-mode error recovery: on a mismatch the parser discards
    input tokens until it finds a token in the FOLLOW set of the current
    nonterminal on the stack.

    Usage::

        gen    = LL1Generator(grammar)
        parser = LL1Parser(gen)
        result = parser.parse(["id", "+", "id"])
    """

    def __init__(self, generator: LL1Generator) -> None:
        self._gen = generator
        self._table = generator.parsing_table()
        self._follow = generator.compute_follow()
        self._grammar = generator._grammar

    def parse(self, tokens: List[str]) -> ParseResult:
        """
        Parse *tokens* using the predictive parsing table.

        Parameters
        ----------
        tokens : list of str
            Input token sequence (do **not** include EOF; it is appended
            automatically).

        Returns
        -------
        ParseResult
        """
        input_tokens = list(tokens) + [EOF]
        stack: List[str] = [EOF, self._grammar.start]
        pos = 0
        steps: List[str] = []
        errors: List[str] = []

        while stack:
            top = stack[-1]
            current = input_tokens[pos] if pos < len(input_tokens) else EOF
            step = f"stack={stack!r}  input={input_tokens[pos:]!r}"
            steps.append(step)

            if top == EOF:
                if current == EOF:
                    break
                else:
                    errors.append(
                        f"Extra input after EOF: {input_tokens[pos:]!r}"
                    )
                    break

            if self._grammar.is_terminal(top) or top == EOF:
                if top == current:
                    stack.pop()
                    pos += 1
                else:
                    errors.append(
                        f"Expected terminal '{top}', got '{current}' "
                        f"at position {pos}."
                    )
                    # Panic: skip input until we find something useful
                    pos = self._panic_skip(input_tokens, pos, stack)
            else:
                # Nonterminal: look up table
                row = self._table.get(top, {})
                if current in row:
                    production_rhs = row[current]
                    stack.pop()
                    # Push RHS in reverse (skip EPSILON)
                    if production_rhs != [EPSILON]:
                        for sym in reversed(production_rhs):
                            stack.append(sym)
                else:
                    errors.append(
                        f"No rule for ({top!r}, {current!r}) at position {pos}. "
                        f"Panic-mode recovery."
                    )
                    # Panic: pop stack until we find a nonterminal with entry
                    pos, stack = self._panic_recover(
                        input_tokens, pos, stack
                    )

        accepted = len(errors) == 0 and pos >= len(input_tokens) - 1
        return ParseResult(
            accepted=accepted,
            tokens=tokens,
            steps=steps,
            errors=errors,
        )

    # ------------------------------------------------------------------
    # Panic-mode helpers
    # ------------------------------------------------------------------

    def _panic_skip(
        self, tokens: List[str], pos: int, stack: List[str]
    ) -> int:
        """Skip input tokens until we find one we can handle."""
        while pos < len(tokens):
            top = stack[-1] if stack else EOF
            if self._grammar.is_terminal(top) and tokens[pos] == top:
                return pos
            if self._grammar.is_nonterminal(top):
                if tokens[pos] in self._table.get(top, {}):
                    return pos
                follow_top = self._follow.get(top, set())
                if tokens[pos] in follow_top:
                    return pos
            pos += 1
        return pos

    def _panic_recover(
        self, tokens: List[str], pos: int, stack: List[str]
    ) -> Tuple[int, List[str]]:
        """Pop stack entries and/or skip input to resync."""
        # Try to find a stack symbol whose FOLLOW contains current token
        current = tokens[pos] if pos < len(tokens) else EOF
        while stack:
            top = stack[-1]
            if self._grammar.is_nonterminal(top):
                if current in self._follow.get(top, set()):
                    stack.pop()
                    return pos, stack
                if current in self._table.get(top, {}):
                    return pos, stack
            stack.pop()
        # Last resort: skip one input token
        if pos < len(tokens) - 1:
            pos += 1
        return pos, stack


# ---------------------------------------------------------------------------
# Convenience one-shot entry point
# ---------------------------------------------------------------------------

def parse(grammar: Grammar, tokens: List[str]) -> ParseResult:
    """
    Compile an LL(1) parser for *grammar* and parse *tokens*.

    Parameters
    ----------
    grammar : Grammar
    tokens  : list of str

    Returns
    -------
    ParseResult
    """
    gen = LL1Generator(grammar)
    parser = LL1Parser(gen)
    return parser.parse(tokens)
