"""Earley Parser for Ambiguous and General Context-Free Grammar Analysis.

Implements the Earley algorithm with full support for:
  - Arbitrary context-free grammars (including ambiguous and left-recursive)
  - Prediction, scanning, and completion chart operations
  - Shared Packed Parse Forest (SPPF) construction for ambiguous grammars
  - Multiple derivation tree recovery
  - Grammar ambiguity measurement
  - Parsing complexity and chart-growth metrics

Public API
----------
parse(grammar, tokens)     -> EarleyParser   (parse and return self)
chart()                    -> List[EarleySet]
trees_for(symbol)          -> List[ParseNode]
is_accepted()              -> bool
ambiguity_measure()        -> AmbiguityInfo

Module-level convenience functions mirror the class API.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, Generator, List, Optional, Set, Tuple


# ---------------------------------------------------------------------------
# Grammar representation
# ---------------------------------------------------------------------------

Symbol = str          # terminal or non-terminal name
Tokens = List[str]    # input token sequence


@dataclass(frozen=True)
class Production:
    """A single CFG production rule: ``lhs -> rhs[0] rhs[1] ...``"""
    lhs: Symbol
    rhs: Tuple[Symbol, ...]

    def __str__(self) -> str:
        rhs_str = ' '.join(self.rhs) if self.rhs else 'ε'
        return f'{self.lhs} -> {rhs_str}'


class Grammar:
    """Context-free grammar with a designated start symbol.

    Parameters
    ----------
    start:
        The start (top-level) non-terminal symbol.
    productions:
        Iterable of ``(lhs, [rhs_symbol, ...])`` pairs.
        An empty rhs list represents an ε-production.

    Examples
    --------
    >>> g = Grammar('S', [
    ...     ('S', ['S', '+', 'S']),
    ...     ('S', ['S', '*', 'S']),
    ...     ('S', ['num']),
    ... ])
    """

    def __init__(
        self,
        start: Symbol,
        productions: List[Tuple[Symbol, List[Symbol]]],
    ) -> None:
        self.start = start
        self.productions: List[Production] = [
            Production(lhs, tuple(rhs)) for lhs, rhs in productions
        ]
        # Index: non-terminal -> list of productions
        self._rules: Dict[Symbol, List[Production]] = defaultdict(list)
        self._terminals: Set[Symbol] = set()
        self._nonterminals: Set[Symbol] = set()

        for prod in self.productions:
            self._rules[prod.lhs].append(prod)
            self._nonterminals.add(prod.lhs)

        # Symbols that appear only on the rhs (and never as lhs) are terminals.
        for prod in self.productions:
            for sym in prod.rhs:
                if sym not in self._nonterminals:
                    self._terminals.add(sym)

    def rules_for(self, symbol: Symbol) -> List[Production]:
        """Return all productions whose lhs is *symbol*."""
        return self._rules.get(symbol, [])

    def is_terminal(self, symbol: Symbol) -> bool:
        return symbol not in self._nonterminals

    def is_nonterminal(self, symbol: Symbol) -> bool:
        return symbol in self._nonterminals

    @property
    def nonterminals(self) -> FrozenSet[Symbol]:
        return frozenset(self._nonterminals)

    @property
    def terminals(self) -> FrozenSet[Symbol]:
        return frozenset(self._terminals)


# ---------------------------------------------------------------------------
# Earley items
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class EarleyItem:
    """An Earley item: ``[production, dot_position, origin_set]``.

    ``origin`` is the chart-set index where this item was predicted.
    ``dot`` is the position of the • in the rhs (0 = before first symbol).
    """
    production: Production
    dot: int
    origin: int

    # Backpointer set stored separately in SPPF nodes; kept mutable.

    @property
    def completed(self) -> bool:
        return self.dot == len(self.production.rhs)

    @property
    def next_symbol(self) -> Optional[Symbol]:
        """The symbol immediately after the dot, or None if completed."""
        if self.completed:
            return None
        return self.production.rhs[self.dot]

    def advance(self) -> 'EarleyItem':
        """Return a new item with the dot moved one position right."""
        return EarleyItem(self.production, self.dot + 1, self.origin)

    def __str__(self) -> str:
        rhs = list(self.production.rhs)
        rhs.insert(self.dot, '•')
        rhs_str = ' '.join(rhs) if rhs else '•'
        return f'[{self.production.lhs} -> {rhs_str}, @{self.origin}]'


# ---------------------------------------------------------------------------
# SPPF (Shared Packed Parse Forest)
# ---------------------------------------------------------------------------

@dataclass
class ParseNode:
    """A node in the Shared Packed Parse Forest.

    ``symbol``    — the grammar symbol this node represents.
    ``start``     — chart index where the span begins.
    ``end``       — chart index where the span ends.
    ``families``  — list of alternative child-list expansions (ambiguity).
                    Each family is a list of child ParseNodes.
    """
    symbol: Symbol
    start: int
    end: int
    families: List[List['ParseNode']] = field(default_factory=list)

    def is_terminal_node(self) -> bool:
        return not self.families

    def __repr__(self) -> str:
        return f'ParseNode({self.symbol!r}, {self.start}:{self.end}, families={len(self.families)})'

    def all_trees(self) -> Generator['ParseNode', None, None]:
        """Yield each distinct full derivation tree rooted at this node."""
        if not self.families:
            yield ParseNode(self.symbol, self.start, self.end)
            return
        for family in self.families:
            yield from _expand_family(self.symbol, self.start, self.end, family)


def _expand_family(
    symbol: Symbol,
    start: int,
    end: int,
    children: List[ParseNode],
) -> Generator[ParseNode, None, None]:
    """Cartesian-product expansion of a single family's child alternatives."""
    if not children:
        yield ParseNode(symbol, start, end)
        return
    # Recursively expand each child's alternatives.
    child_tree_lists: List[List[ParseNode]] = [list(c.all_trees()) for c in children]
    for combo in _cartesian(child_tree_lists):
        node = ParseNode(symbol, start, end)
        node.families.append(combo)
        yield node


def _cartesian(lists: List[List[Any]]) -> Generator[List[Any], None, None]:
    """Yield all combinations taking one element from each list."""
    if not lists:
        yield []
        return
    for item in lists[0]:
        for rest in _cartesian(lists[1:]):
            yield [item] + rest


# ---------------------------------------------------------------------------
# Chart set (Earley set)
# ---------------------------------------------------------------------------

class EarleySet:
    """One Earley chart set S_k."""

    def __init__(self, index: int) -> None:
        self.index = index
        self._items: List[EarleyItem] = []
        self._seen: Set[EarleyItem] = set()

    def add(self, item: EarleyItem) -> bool:
        """Add *item* if not already present; return True if newly added."""
        if item not in self._seen:
            self._seen.add(item)
            self._items.append(item)
            return True
        return False

    def __iter__(self):
        # Iterate with an index so items added during iteration are included.
        idx = 0
        while idx < len(self._items):
            yield self._items[idx]
            idx += 1

    def __len__(self) -> int:
        return len(self._items)

    def __contains__(self, item: EarleyItem) -> bool:
        return item in self._seen

    def items(self) -> List[EarleyItem]:
        return list(self._items)


# ---------------------------------------------------------------------------
# Ambiguity metrics
# ---------------------------------------------------------------------------

@dataclass
class AmbiguityInfo:
    """Metrics describing grammar ambiguity for the last parsed input."""
    total_parse_trees: int
    """Total number of distinct full derivation trees."""

    ambiguous_nonterminals: List[Symbol]
    """Non-terminals that have more than one derivation for some span."""

    max_derivations: int
    """Maximum number of derivations for any single (symbol, span) pair."""

    chart_item_count: int
    """Total Earley items across all chart sets (parse complexity proxy)."""

    is_ambiguous: bool
    """True when the grammar produces more than one parse tree."""

    def __str__(self) -> str:
        return (
            f'AmbiguityInfo('
            f'trees={self.total_parse_trees}, '
            f'ambiguous_NTs={self.ambiguous_nonterminals}, '
            f'max_derivations={self.max_derivations}, '
            f'chart_items={self.chart_item_count}, '
            f'is_ambiguous={self.is_ambiguous})'
        )


# ---------------------------------------------------------------------------
# Earley parser
# ---------------------------------------------------------------------------

class EarleyParser:
    """Full Earley parser with SPPF construction and ambiguity analysis.

    Usage
    -----
    >>> parser = EarleyParser()
    >>> parser.parse(grammar, tokens)
    >>> if parser.is_accepted():
    ...     trees = parser.trees_for(grammar.start)
    """

    def __init__(self) -> None:
        self._chart: List[EarleySet] = []
        self._grammar: Optional[Grammar] = None
        self._tokens: Tokens = []
        self._sppf: Dict[Tuple[Symbol, int, int], ParseNode] = {}
        # backpointers[item] = list of (completed_item, predecessor_item)
        self._backpointers: Dict[EarleyItem, List[Tuple[Optional[EarleyItem], Optional[EarleyItem]]]] = defaultdict(list)
        self._parsed = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def parse(self, grammar: Grammar, tokens: Tokens) -> 'EarleyParser':
        """Run the Earley algorithm on *tokens* under *grammar*.

        Returns *self* for chaining.
        """
        self._grammar = grammar
        self._tokens = list(tokens)
        self._chart = []
        self._sppf = {}
        self._backpointers = defaultdict(list)
        self._parsed = False

        n = len(tokens)
        # Initialise chart sets S_0 ... S_n.
        for i in range(n + 1):
            self._chart.append(EarleySet(i))

        # Seed S_0 with productions for the start symbol.
        for prod in grammar.rules_for(grammar.start):
            self._chart[0].add(EarleyItem(prod, 0, 0))

        for k in range(n + 1):
            for item in self._chart[k]:
                if item.completed:
                    self._complete(item, k)
                elif grammar.is_nonterminal(item.next_symbol):
                    self._predict(item, k, grammar)
                else:
                    self._scan(item, k, tokens)

        self._parsed = True
        return self

    def chart(self) -> List[EarleySet]:
        """Return the full Earley chart (list of EarleySets S_0 … S_n)."""
        self._require_parsed()
        return list(self._chart)

    def is_accepted(self) -> bool:
        """Return True if the input is accepted by the grammar."""
        self._require_parsed()
        n = len(self._tokens)
        target_set = self._chart[n]
        for item in target_set:
            if (
                item.completed
                and item.production.lhs == self._grammar.start
                and item.origin == 0
            ):
                return True
        return False

    def trees_for(self, symbol: Symbol) -> List[ParseNode]:
        """Return all distinct parse trees whose root is *symbol*.

        Uses the SPPF built during the last parse call.
        """
        self._require_parsed()
        n = len(self._tokens)
        root_key = (symbol, 0, n)
        if root_key not in self._sppf:
            self._build_sppf()
        node = self._sppf.get(root_key)
        if node is None:
            return []
        return list(node.all_trees())

    def ambiguity_measure(self) -> AmbiguityInfo:
        """Compute and return ambiguity metrics for the last parse."""
        self._require_parsed()
        n = len(self._tokens)

        # Ensure SPPF is built.
        if not self._sppf:
            self._build_sppf()

        chart_item_count = sum(len(s) for s in self._chart)

        # Find non-terminals with multiple derivations for some span.
        ambiguous_nts: List[Symbol] = []
        max_derivations = 0
        for (sym, start, end), node in self._sppf.items():
            if self._grammar.is_nonterminal(sym):
                n_fam = len(node.families)
                if n_fam > 1:
                    if sym not in ambiguous_nts:
                        ambiguous_nts.append(sym)
                    if n_fam > max_derivations:
                        max_derivations = n_fam

        # Count total trees from start symbol.
        root_trees = self.trees_for(self._grammar.start)
        total_trees = len(root_trees)
        if total_trees > max_derivations:
            max_derivations = total_trees

        return AmbiguityInfo(
            total_parse_trees=total_trees,
            ambiguous_nonterminals=ambiguous_nts,
            max_derivations=max(max_derivations, total_trees),
            chart_item_count=chart_item_count,
            is_ambiguous=total_trees > 1,
        )

    # ------------------------------------------------------------------
    # Core Earley operations
    # ------------------------------------------------------------------

    def _predict(self, item: EarleyItem, k: int, grammar: Grammar) -> None:
        """Predictor: add items for all productions of the next symbol."""
        sym = item.next_symbol
        for prod in grammar.rules_for(sym):
            new_item = EarleyItem(prod, 0, k)
            self._chart[k].add(new_item)
            # ε-production: immediately complete it.
            if len(prod.rhs) == 0:
                completed = EarleyItem(prod, 0, k)
                self._complete(completed, k)

    def _scan(self, item: EarleyItem, k: int, tokens: Tokens) -> None:
        """Scanner: if next token matches, advance item into S_{k+1}."""
        if k >= len(tokens):
            return
        token = tokens[k]
        if item.next_symbol == token:
            advanced = item.advance()
            self._chart[k + 1].add(advanced)
            # Record backpointer for SPPF.
            self._backpointers[advanced].append((item, None))

    def _complete(self, completed_item: EarleyItem, k: int) -> None:
        """Completor: advance all items waiting for the completed symbol."""
        lhs = completed_item.production.lhs
        origin = completed_item.origin
        for waiting_item in self._chart[origin]:
            if not waiting_item.completed and waiting_item.next_symbol == lhs:
                advanced = waiting_item.advance()
                is_new = self._chart[k].add(advanced)
                # Record backpointer regardless (captures ambiguity).
                bp = (waiting_item, completed_item)
                if bp not in self._backpointers[advanced]:
                    self._backpointers[advanced].append(bp)

    # ------------------------------------------------------------------
    # SPPF construction
    # ------------------------------------------------------------------

    def _build_sppf(self) -> None:
        """Build the Shared Packed Parse Forest from backpointers."""
        n = len(self._tokens)
        # Process completed items that contribute to the start parse.
        for k in range(n + 1):
            for item in self._chart[k]:
                if item.completed:
                    self._sppf_for_item(item, k)

    def _sppf_for_item(self, item: EarleyItem, end: int) -> ParseNode:
        """Return (or create) the SPPF node for a completed *item* ending at *end*."""
        sym = item.production.lhs
        start = item.origin
        key = (sym, start, end)
        if key in self._sppf:
            node = self._sppf[key]
        else:
            node = ParseNode(sym, start, end)
            self._sppf[key] = node

        # Build child lists from backpointers.
        for (pred, comp) in self._backpointers.get(item, []):
            children = self._build_children(item, end, pred, comp)
            if children is not None and children not in node.families:
                node.families.append(children)

        return node

    def _build_children(
        self,
        item: EarleyItem,
        end: int,
        predecessor: Optional[EarleyItem],
        completer: Optional[EarleyItem],
    ) -> Optional[List[ParseNode]]:
        """Reconstruct the child node list for one derivation of *item*."""
        if predecessor is None and completer is None:
            return []

        # Scanned token: leaf node.
        if completer is None and predecessor is not None:
            # Scanning produced this item from predecessor at position end-1.
            sym = item.production.rhs[item.dot - 1]
            leaf = self._sppf.setdefault(
                (sym, end - 1, end),
                ParseNode(sym, end - 1, end)
            )
            parent_children = self._build_children_of_predecessor(
                predecessor, end - 1
            )
            if parent_children is None:
                return [leaf]
            return parent_children + [leaf]

        # Completion: completer covers [comp_start, end].
        if completer is not None:
            comp_start = completer.origin
            comp_node = self._sppf_for_item(completer, end)
            if predecessor is not None:
                parent_children = self._build_children_of_predecessor(
                    predecessor, comp_start
                )
                if parent_children is None:
                    return [comp_node]
                return parent_children + [comp_node]
            return [comp_node]

        return None

    def _build_children_of_predecessor(
        self,
        pred_item: EarleyItem,
        end: int,
    ) -> Optional[List[ParseNode]]:
        """Recursively unwind a predecessor item to get its child nodes."""
        if pred_item.dot == 0:
            return []
        # Find a matching backpointer for this predecessor at position *end*.
        for (pp, pc) in self._backpointers.get(pred_item, []):
            children = self._build_children(pred_item, end, pp, pc)
            if children is not None:
                return children
        # No backpointer found — treat as leaf boundary.
        return None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _require_parsed(self) -> None:
        if not self._parsed:
            raise RuntimeError(
                "parse() must be called before accessing results."
            )


# ---------------------------------------------------------------------------
# Module-level convenience functions
# ---------------------------------------------------------------------------

def parse(grammar: Grammar, tokens: Tokens) -> EarleyParser:
    """Parse *tokens* with *grammar* and return the EarleyParser instance."""
    return EarleyParser().parse(grammar, tokens)


def chart(grammar: Grammar, tokens: Tokens) -> List[EarleySet]:
    """Return the full Earley chart for *tokens* under *grammar*."""
    return parse(grammar, tokens).chart()


def trees_for(grammar: Grammar, tokens: Tokens, symbol: Symbol) -> List[ParseNode]:
    """Return all parse trees rooted at *symbol* for *tokens* in *grammar*."""
    return parse(grammar, tokens).trees_for(symbol)


def is_accepted(grammar: Grammar, tokens: Tokens) -> bool:
    """Return True if *tokens* is accepted by *grammar*."""
    return parse(grammar, tokens).is_accepted()


def ambiguity_measure(grammar: Grammar, tokens: Tokens) -> AmbiguityInfo:
    """Return ambiguity metrics for parsing *tokens* with *grammar*."""
    return parse(grammar, tokens).ambiguity_measure()


# ---------------------------------------------------------------------------
# Grammar factory helpers
# ---------------------------------------------------------------------------

def arithmetic_grammar() -> Grammar:
    """Return a classic ambiguous arithmetic expression grammar.

    Productions::

        E -> E + E | E - E | E * E | E / E | ( E ) | num
    """
    return Grammar('E', [
        ('E', ['E', '+', 'E']),
        ('E', ['E', '-', 'E']),
        ('E', ['E', '*', 'E']),
        ('E', ['E', '/', 'E']),
        ('E', ['(', 'E', ')']),
        ('E', ['num']),
    ])


def palindrome_grammar() -> Grammar:
    """Return a grammar for palindromes over {a, b}.

    Productions::

        S -> a S a | b S b | a | b | ε
    """
    return Grammar('S', [
        ('S', ['a', 'S', 'a']),
        ('S', ['b', 'S', 'b']),
        ('S', ['a']),
        ('S', ['b']),
        ('S', []),
    ])


def left_recursive_grammar() -> Grammar:
    """Return a left-recursive grammar for sequences of 'x'.

    Productions::

        S -> S x | x
    """
    return Grammar('S', [
        ('S', ['S', 'x']),
        ('S', ['x']),
    ])


def balanced_parens_grammar() -> Grammar:
    """Return a grammar for balanced parentheses.

    Productions::

        S -> ( S ) S | ε
    """
    return Grammar('S', [
        ('S', ['(', 'S', ')', 'S']),
        ('S', []),
    ])


# ---------------------------------------------------------------------------
# Demo / self-test
# ---------------------------------------------------------------------------

def _demo() -> None:
    print("=" * 62)
    print("Earley Parser Demo")
    print("=" * 62)

    # --- Arithmetic (ambiguous) ---------------------------------------
    g = arithmetic_grammar()
    tokens = ['num', '+', 'num', '*', 'num']
    p = parse(g, tokens)
    accepted = p.is_accepted()
    print(f"\nArithmetic: {' '.join(tokens)}")
    print(f"  Accepted          : {accepted}")
    chart_sets = p.chart()
    total_items = sum(len(s) for s in chart_sets)
    print(f"  Chart sets        : {len(chart_sets)}")
    print(f"  Total chart items : {total_items}")
    amb = p.ambiguity_measure()
    print(f"  Ambiguity info    : {amb}")
    trees = p.trees_for('E')
    print(f"  Parse trees       : {len(trees)}")

    # --- Left-recursive grammar ---------------------------------------
    g2 = left_recursive_grammar()
    toks2 = ['x', 'x', 'x']
    p2 = parse(g2, toks2)
    print(f"\nLeft-recursive 'x x x': accepted={p2.is_accepted()}")
    print(f"  Parse trees : {len(p2.trees_for('S'))}")

    # --- Balanced parentheses ----------------------------------------
    g3 = balanced_parens_grammar()
    toks3 = list('(())')
    p3 = parse(g3, toks3)
    print(f"\nBalanced parens '(())': accepted={p3.is_accepted()}")
    print(f"  Parse trees : {len(p3.trees_for('S'))}")

    # Rejected input.
    toks4 = list('(()')
    p4 = parse(g3, toks4)
    print(f"\nUnbalanced '(()': accepted={p4.is_accepted()}")

    # --- Palindrome ---------------------------------------------------
    g5 = palindrome_grammar()
    toks5 = list('abba')
    p5 = parse(g5, toks5)
    print(f"\nPalindrome 'abba': accepted={p5.is_accepted()}")
    a5 = p5.ambiguity_measure()
    print(f"  Ambiguity info : {a5}")

    print("\nDemo complete.")


if __name__ == '__main__':
    _demo()
