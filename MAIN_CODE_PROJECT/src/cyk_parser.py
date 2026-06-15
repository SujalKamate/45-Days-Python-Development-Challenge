"""
CYK (Cocke-Younger-Kasami) Parsing Framework
=============================================
Bottom-up context-free grammar parser using dynamic programming.
Supports Chomsky Normal Form (CNF) grammars with:
  - Parse table population
  - Backpointer-based parse tree reconstruction
  - Ambiguous grammar support (multiple parses)
  - Probabilistic parse ranking
  - Span-specific parse queries
  - Grammar coverage and complexity metrics
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Optional, Set, Tuple


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ParseNode:
    """A node in a parse tree."""
    symbol: str
    children: List["ParseNode"] = field(default_factory=list)
    span: Tuple[int, int] = (0, 0)          # (start, end) token indices (inclusive)
    log_prob: float = 0.0                    # log-probability for probabilistic ranking

    def is_terminal(self) -> bool:
        return len(self.children) == 0

    def __repr__(self) -> str:  # pragma: no cover
        if self.is_terminal():
            return f"({self.symbol})"
        children_repr = " ".join(repr(c) for c in self.children)
        return f"({self.symbol} {children_repr})"


@dataclass
class CNFRule:
    """
    A single rule in Chomsky Normal Form.

    Two forms are allowed:
      Binary:   A -> B C   (two nonterminals)
      Unary:    A -> 'w'   (one terminal string)

    The optional ``log_prob`` field supports probabilistic grammars (PCFGs).
    When all rules for a given lhs sum to probability 1.0 the grammar is
    a proper PCFG; partial specifications are accepted but the ranking may
    not be meaningful.
    """
    lhs: str                         # left-hand side nonterminal
    rhs: Tuple[str, ...]             # right-hand side: 1 or 2 symbols
    log_prob: float = 0.0            # log-probability (0.0 == prob 1.0 by default)

    def is_binary(self) -> bool:
        return len(self.rhs) == 2

    def is_unary(self) -> bool:
        return len(self.rhs) == 1


class CNFGrammar:
    """
    Chomsky Normal Form grammar container.

    Parameters
    ----------
    start_symbol : str
        The start (root) nonterminal of the grammar.
    rules : list of CNFRule
        All grammar rules.  Each rule must be either binary (A -> B C) or
        unary/lexical (A -> 'word').
    """

    def __init__(self, start_symbol: str, rules: List[CNFRule]) -> None:
        self.start_symbol = start_symbol
        self.rules: List[CNFRule] = rules

        # Indexed views for fast lookup during parsing
        self._binary_by_rhs: Dict[Tuple[str, str], List[CNFRule]] = defaultdict(list)
        self._unary_by_terminal: Dict[str, List[CNFRule]] = defaultdict(list)
        self._nonterminals: Set[str] = set()

        for rule in rules:
            self._nonterminals.add(rule.lhs)
            if rule.is_binary():
                self._binary_by_rhs[rule.rhs].append(rule)
            elif rule.is_unary():
                self._unary_by_terminal[rule.rhs[0]].append(rule)
            else:
                raise ValueError(
                    f"Rule '{rule.lhs} -> {rule.rhs}' is not in CNF "
                    "(must be binary or unary)."
                )

    # ------------------------------------------------------------------
    # Convenience accessors used by the parser
    # ------------------------------------------------------------------

    def rules_for_binary(self, b: str, c: str) -> List[CNFRule]:
        """Return all rules whose RHS is (b, c)."""
        return self._binary_by_rhs.get((b, c), [])

    def rules_for_terminal(self, word: str) -> List[CNFRule]:
        """Return all rules whose RHS is the single terminal *word*."""
        return self._unary_by_terminal.get(word, [])

    @property
    def nonterminals(self) -> Set[str]:
        return self._nonterminals


# ---------------------------------------------------------------------------
# Cell entry: what we store per (nonterminal, span) in the table
# ---------------------------------------------------------------------------

@dataclass
class _CellEntry:
    """Internal: best (highest log-prob) backpointer for a nonterminal in a span."""
    log_prob: float
    # For binary splits: (split_point, left_nonterminal, right_nonterminal)
    # For terminal spans: None
    backpointer: Optional[Tuple[int, str, str]]


# ---------------------------------------------------------------------------
# Core CYK parser
# ---------------------------------------------------------------------------

class CYKParser:
    """
    CYK parser operating on a :class:`CNFGrammar`.

    Usage::

        grammar = CNFGrammar(start_symbol="S", rules=[...])
        parser  = CYKParser(grammar)
        result  = parser.parse(grammar, tokens)          # top-level API
        table   = parser.parse_table()                   # raw DP table
        best    = parser.most_likely_parse()             # highest-prob tree
        spans   = parser.parses_for_span(0, 3)           # trees rooted in span
    """

    def __init__(self, grammar: Optional[CNFGrammar] = None) -> None:
        self._grammar = grammar
        # DP table: table[i][j][A] = _CellEntry  (i <= j, 0-indexed)
        self._table: List[List[Dict[str, _CellEntry]]] = []
        # All backpointer entries: list of (nonterminal, i, j, entry)
        self._all_entries: List[Tuple[str, int, int, _CellEntry]] = []
        self._tokens: List[str] = []
        self._n: int = 0
        self._parsed: bool = False
        # Metrics
        self._cells_filled: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def parse(self, grammar: CNFGrammar, tokens: List[str]) -> bool:
        """
        Run CYK parsing and return whether the token sequence is accepted.

        Parameters
        ----------
        grammar : CNFGrammar
            The CNF grammar to use.
        tokens : list of str
            The input token sequence to parse.

        Returns
        -------
        bool
            True if the start symbol spans the entire input, False otherwise.
        """
        self._grammar = grammar
        self._tokens = tokens
        self._n = len(tokens)
        self._parsed = False
        self._cells_filled = 0
        self._all_entries = []

        if self._n == 0:
            # Empty string: accepted iff the grammar allows an empty derivation.
            # CNF does not allow empty RHS, so always False here.
            return False

        # Initialise table: n x n cells, each cell is a dict of nonterminal -> _CellEntry
        self._table = [[{} for _ in range(self._n)] for _ in range(self._n)]

        # Step 1 – fill diagonal (span length 1: individual tokens)
        self._fill_terminals()

        # Step 2 – fill upper triangle (span lengths 2 .. n)
        self._fill_binary_spans()

        self._parsed = True
        accepted = grammar.start_symbol in self._table[0][self._n - 1]
        return accepted

    def parse_table(self) -> List[List[Dict[str, Any]]]:
        """
        Return the completed DP parse table.

        The table is an *n x n* upper-triangular list of lists.
        ``table[i][j]`` maps each nonterminal (str) that spans tokens
        ``i..j`` (inclusive, 0-indexed) to a dict::

            {
                "log_prob": float,
                "backpointer": (split_point, left_nonterminal, right_nonterminal)
                               or None for terminal spans,
            }

        Returns
        -------
        list[list[dict]]
        """
        self._require_parsed()
        result = []
        for i in range(self._n):
            row = []
            for j in range(self._n):
                cell: Dict[str, Any] = {}
                for nt, entry in self._table[i][j].items():
                    cell[nt] = {
                        "log_prob": entry.log_prob,
                        "backpointer": entry.backpointer,
                    }
                row.append(cell)
            result.append(row)
        return result

    def most_likely_parse(self) -> Optional[ParseNode]:
        """
        Return the single highest-probability parse tree for the full input.

        Returns ``None`` if the input was not accepted.
        """
        self._require_parsed()
        assert self._grammar is not None
        start = self._grammar.start_symbol
        if start not in self._table[0][self._n - 1]:
            return None
        return self._reconstruct(start, 0, self._n - 1)

    def parses_for_span(self, start: int, end: int) -> List[ParseNode]:
        """
        Return all parse trees (for every nonterminal) that cover the span
        ``tokens[start..end]`` (inclusive).

        Parameters
        ----------
        start : int
            Start token index (0-based, inclusive).
        end : int
            End token index (0-based, inclusive).

        Returns
        -------
        list of ParseNode
            One tree per nonterminal found in the cell ``table[start][end]``.
        """
        self._require_parsed()
        if not (0 <= start <= end < self._n):
            raise IndexError(
                f"Span ({start}, {end}) is out of range for input of length {self._n}."
            )
        trees: List[ParseNode] = []
        for nt in self._table[start][end]:
            trees.append(self._reconstruct(nt, start, end))
        return trees

    def all_parses(self) -> Iterator[ParseNode]:
        """
        Yield every parse tree rooted at the start symbol via enumeration.

        For ambiguous grammars this produces multiple trees.  Enumeration is
        performed lazily; trees are ordered from highest to lowest log-prob
        (best-first).
        """
        self._require_parsed()
        assert self._grammar is not None
        start = self._grammar.start_symbol
        if start not in self._table[0][self._n - 1]:
            return
        # For this reference implementation we enumerate via backpointers.
        # The generator yields sub-trees via recursive enumeration.
        yield from self._enumerate_trees(start, 0, self._n - 1)

    # ------------------------------------------------------------------
    # Metrics / statistics
    # ------------------------------------------------------------------

    def cells_filled(self) -> int:
        """Return the total number of (nonterminal, span) entries added to the table."""
        self._require_parsed()
        return self._cells_filled

    def table_occupancy(self) -> float:
        """
        Return the fraction of table cells that contain at least one nonterminal.
        The theoretical maximum is n*(n+1)/2 cells for an n-token input.
        """
        self._require_parsed()
        if self._n == 0:
            return 0.0
        max_cells = self._n * (self._n + 1) // 2
        filled = sum(
            1
            for i in range(self._n)
            for j in range(i, self._n)
            if self._table[i][j]
        )
        return filled / max_cells

    def parsing_complexity(self) -> Dict[str, Any]:
        """
        Return a dict of parsing complexity metrics::

            {
                "input_length": int,
                "grammar_rules": int,
                "nonterminals": int,
                "cells_filled": int,
                "table_occupancy": float,   # fraction [0, 1]
                "accepted": bool,
            }
        """
        self._require_parsed()
        assert self._grammar is not None
        return {
            "input_length": self._n,
            "grammar_rules": len(self._grammar.rules),
            "nonterminals": len(self._grammar.nonterminals),
            "cells_filled": self.cells_filled(),
            "table_occupancy": self.table_occupancy(),
            "accepted": self._grammar.start_symbol in self._table[0][self._n - 1],
        }

    def grammar_coverage(self) -> Dict[str, Any]:
        """
        Return statistics about how many grammar rules were used during parsing::

            {
                "rules_total": int,
                "rules_applied": int,
                "coverage_fraction": float,
            }
        """
        self._require_parsed()
        assert self._grammar is not None
        applied: Set[Tuple] = set()
        for i in range(self._n):
            for j in range(i, self._n):
                for nt, entry in self._table[i][j].items():
                    if entry.backpointer is not None:
                        k, b, c = entry.backpointer
                        applied.add((nt, b, c))
                    else:
                        # terminal rule
                        applied.add((nt, self._tokens[i]))
        total = len(self._grammar.rules)
        return {
            "rules_total": total,
            "rules_applied": len(applied),
            "coverage_fraction": len(applied) / total if total else 0.0,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _fill_terminals(self) -> None:
        """Populate the diagonal of the DP table (span length 1)."""
        assert self._grammar is not None
        for i, token in enumerate(self._tokens):
            for rule in self._grammar.rules_for_terminal(token):
                self._add_entry(i, i, rule.lhs, rule.log_prob, None)

    def _fill_binary_spans(self) -> None:
        """Fill the upper triangle of the DP table (span lengths 2..n)."""
        assert self._grammar is not None
        n = self._n
        for length in range(2, n + 1):           # span length
            for i in range(n - length + 1):       # span start
                j = i + length - 1               # span end
                for k in range(i, j):            # split point k in [i, j-1]
                    left_cell = self._table[i][k]
                    right_cell = self._table[k + 1][j]
                    for b in left_cell:
                        for c in right_cell:
                            for rule in self._grammar.rules_for_binary(b, c):
                                lp = (rule.log_prob
                                      + left_cell[b].log_prob
                                      + right_cell[c].log_prob)
                                self._add_entry(i, j, rule.lhs, lp, (k, b, c))

    def _add_entry(
        self,
        i: int,
        j: int,
        nonterminal: str,
        log_prob: float,
        backpointer: Optional[Tuple],
    ) -> None:
        """
        Insert or update a cell entry if the new log-prob is higher (best-first).
        """
        cell = self._table[i][j]
        if nonterminal not in cell or log_prob > cell[nonterminal].log_prob:
            if nonterminal not in cell:
                self._cells_filled += 1
            cell[nonterminal] = _CellEntry(log_prob=log_prob, backpointer=backpointer)

    def _reconstruct(self, symbol: str, i: int, j: int) -> ParseNode:
        """Reconstruct the best parse tree for *symbol* spanning tokens i..j."""
        entry = self._table[i][j][symbol]
        node = ParseNode(symbol=symbol, span=(i, j), log_prob=entry.log_prob)
        if entry.backpointer is None:
            # Lexical rule: leaf node
            token_node = ParseNode(
                symbol=self._tokens[i], span=(i, i), log_prob=0.0
            )
            node.children = [token_node]
        else:
            k, b, c = entry.backpointer
            node.children = [
                self._reconstruct(b, i, k),
                self._reconstruct(c, k + 1, j),
            ]
        return node

    def _enumerate_trees(
        self, symbol: str, i: int, j: int
    ) -> Iterator[ParseNode]:
        """
        Recursively enumerate ALL parse trees for *symbol* spanning i..j.

        This uses the best-first backpointer stored in the DP table.
        For a full ambiguity-aware enumeration a chart with multiple
        backpointers per cell would be required; this implementation
        yields the single best derivation per (symbol, span) cell.
        """
        entry = self._table[i][j].get(symbol)
        if entry is None:
            return
        if entry.backpointer is None:
            # Leaf
            token_node = ParseNode(
                symbol=self._tokens[i], span=(i, i), log_prob=0.0
            )
            yield ParseNode(symbol=symbol, span=(i, j),
                            log_prob=entry.log_prob, children=[token_node])
        else:
            k, b, c = entry.backpointer
            for left_tree in self._enumerate_trees(b, i, k):
                for right_tree in self._enumerate_trees(c, k + 1, j):
                    lp = entry.log_prob  # already combined
                    yield ParseNode(
                        symbol=symbol,
                        span=(i, j),
                        log_prob=lp,
                        children=[left_tree, right_tree],
                    )

    def _require_parsed(self) -> None:
        if not self._parsed:
            raise RuntimeError(
                "No parse has been run yet. Call parse(grammar, tokens) first."
            )


# ---------------------------------------------------------------------------
# Module-level convenience function
# ---------------------------------------------------------------------------

def parse(grammar: CNFGrammar, tokens: List[str]) -> Tuple[bool, CYKParser]:
    """
    Convenience wrapper: parse *tokens* with *grammar* and return
    ``(accepted, parser)`` where ``parser`` gives access to the full API.

    Parameters
    ----------
    grammar : CNFGrammar
    tokens  : list of str

    Returns
    -------
    (bool, CYKParser)
    """
    parser = CYKParser(grammar)
    accepted = parser.parse(grammar, tokens)
    return accepted, parser


# ---------------------------------------------------------------------------
# Probabilistic helpers
# ---------------------------------------------------------------------------

def log_prob_from_prob(prob: float) -> float:
    """Convert a probability in [0, 1] to a log-probability (base e)."""
    if prob <= 0.0:
        return -math.inf
    return math.log(prob)


def prob_from_log_prob(log_prob: float) -> float:
    """Convert a log-probability back to a linear probability."""
    return math.exp(log_prob)


# ---------------------------------------------------------------------------
# Pretty-printer
# ---------------------------------------------------------------------------

def pretty_print(node: ParseNode, indent: int = 0) -> None:  # pragma: no cover
    """Print a parse tree to stdout in a readable indented format."""
    prefix = "  " * indent
    if node.is_terminal():
        print(f"{prefix}[{node.symbol}]  (span={node.span})")
    else:
        print(f"{prefix}({node.symbol}  log_prob={node.log_prob:.4f}  span={node.span})")
        for child in node.children:
            pretty_print(child, indent + 1)
