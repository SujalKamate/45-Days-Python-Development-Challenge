"""
Thompson NFA Regular Expression Compilation and Matching Framework
=================================================================
Compiles regular expressions into epsilon-NFAs using Thompson construction
and performs simulation-based matching.

Supported syntax
----------------
  .          Wildcard (any single character except newline)
  *          Zero-or-more (Kleene star)
  +          One-or-more
  ?          Zero-or-one (optional)
  |          Alternation
  (...)      Grouping
  [abc]      Character class (literal chars; leading ^ negates)
  ^          Start-of-string anchor
  $          End-of-string anchor
  \\n \\t ...  Standard escape sequences

Public API
----------
  compile(pattern)       -> CompiledRegex
  CompiledRegex.match(text)      -> Match | None
  CompiledRegex.search(text)     -> Match | None
  CompiledRegex.find_all(text)   -> list[Match]
  CompiledRegex.nfa_graph()      -> dict
  CompiledRegex.state_count()    -> int
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, Iterator, List, Optional, Set, Tuple


# ---------------------------------------------------------------------------
# NFA state & transition primitives
# ---------------------------------------------------------------------------

_state_counter: int = 0


def _new_state() -> int:
    global _state_counter
    _state_counter += 1
    return _state_counter


# Sentinel for epsilon transitions
_EPSILON = "\x00"
# Sentinel for wildcard (any char)
_ANY = "\x01"


@dataclass
class _State:
    """A single NFA state."""
    sid: int
    transitions: Dict[str, List[int]] = field(default_factory=dict)  # label -> [states]
    is_accept: bool = False

    def add_transition(self, label: str, target: int) -> None:
        self.transitions.setdefault(label, []).append(target)


class _NFA:
    """Fragment of a Thompson NFA (start state + accept state)."""

    def __init__(self, states: Dict[int, _State], start: int, accept: int) -> None:
        self.states = states          # sid -> _State
        self.start = start
        self.accept = accept          # single accept state per fragment

    # ------------------------------------------------------------------
    # Thompson construction combinators
    # ------------------------------------------------------------------

    @staticmethod
    def from_literal(ch: str) -> "_NFA":
        """NFA that matches exactly one character *ch*."""
        s = _new_state()
        a = _new_state()
        st = _State(s)
        ac = _State(a, is_accept=True)
        st.add_transition(ch, a)
        return _NFA({s: st, a: ac}, s, a)

    @staticmethod
    def from_char_class(chars: Set[str], negated: bool = False) -> "_NFA":
        """NFA matching any character in (or outside if negated) *chars*."""
        s = _new_state()
        a = _new_state()
        st = _State(s)
        ac = _State(a, is_accept=True)
        label = _CharClass(frozenset(chars), negated)
        st.add_transition(label, a)  # type: ignore[arg-type]
        return _NFA({s: st, a: ac}, s, a)

    @staticmethod
    def from_any() -> "_NFA":
        """NFA matching any single character (wildcard '.')."""
        s = _new_state()
        a = _new_state()
        st = _State(s)
        ac = _State(a, is_accept=True)
        st.add_transition(_ANY, a)
        return _NFA({s: st, a: ac}, s, a)

    @staticmethod
    def concatenate(left: "_NFA", right: "_NFA") -> "_NFA":
        """AB: left then right."""
        states = {**left.states, **right.states}
        # Connect left accept -> right start via epsilon
        states[left.accept].is_accept = False
        states[left.accept].add_transition(_EPSILON, right.start)
        return _NFA(states, left.start, right.accept)

    @staticmethod
    def alternate(left: "_NFA", right: "_NFA") -> "_NFA":
        """A|B: new split state epsilon-linked to both fragments."""
        s = _new_state()
        a = _new_state()
        split = _State(s)
        accept = _State(a, is_accept=True)
        states = {s: split, a: accept, **left.states, **right.states}
        split.add_transition(_EPSILON, left.start)
        split.add_transition(_EPSILON, right.start)
        states[left.accept].is_accept = False
        states[left.accept].add_transition(_EPSILON, a)
        states[right.accept].is_accept = False
        states[right.accept].add_transition(_EPSILON, a)
        return _NFA(states, s, a)

    @staticmethod
    def star(nfa: "_NFA") -> "_NFA":
        """A*: zero or more."""
        s = _new_state()
        a = _new_state()
        split = _State(s)
        accept = _State(a, is_accept=True)
        states = {s: split, a: accept, **nfa.states}
        split.add_transition(_EPSILON, nfa.start)
        split.add_transition(_EPSILON, a)
        states[nfa.accept].is_accept = False
        states[nfa.accept].add_transition(_EPSILON, nfa.start)
        states[nfa.accept].add_transition(_EPSILON, a)
        return _NFA(states, s, a)

    @staticmethod
    def plus(nfa: "_NFA") -> "_NFA":
        """A+: one or more (= A then A*)."""
        return _NFA.concatenate(nfa, _NFA.star(_NFA._clone(nfa)))

    @staticmethod
    def optional(nfa: "_NFA") -> "_NFA":
        """A?: zero or one."""
        s = _new_state()
        a = _new_state()
        split = _State(s)
        accept = _State(a, is_accept=True)
        states = {s: split, a: accept, **nfa.states}
        split.add_transition(_EPSILON, nfa.start)
        split.add_transition(_EPSILON, a)
        states[nfa.accept].is_accept = False
        states[nfa.accept].add_transition(_EPSILON, a)
        return _NFA(states, s, a)

    @staticmethod
    def _clone(nfa: "_NFA") -> "_NFA":
        """Deep-clone an NFA with fresh state IDs."""
        mapping: Dict[int, int] = {sid: _new_state() for sid in nfa.states}
        new_states: Dict[int, _State] = {}
        for old_sid, old_st in nfa.states.items():
            new_sid = mapping[old_sid]
            new_st = _State(new_sid, is_accept=old_st.is_accept)
            for label, targets in old_st.transitions.items():
                new_st.transitions[label] = [mapping[t] for t in targets]
            new_states[new_sid] = new_st
        return _NFA(new_states, mapping[nfa.start], mapping[nfa.accept])


# ---------------------------------------------------------------------------
# Character class helper (used as a dict key / label)
# ---------------------------------------------------------------------------

class _CharClass:
    """Immutable character-class label for NFA transitions."""

    __slots__ = ("chars", "negated")

    def __init__(self, chars: FrozenSet[str], negated: bool) -> None:
        self.chars = chars
        self.negated = negated

    def matches(self, ch: str) -> bool:
        return (ch not in self.chars) if self.negated else (ch in self.chars)

    def __repr__(self) -> str:
        inner = "".join(sorted(self.chars))
        return f"[^{inner}]" if self.negated else f"[{inner}]"

    def __hash__(self) -> int:
        return hash((self.chars, self.negated))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, _CharClass):
            return NotImplemented
        return self.chars == other.chars and self.negated == other.negated


# ---------------------------------------------------------------------------
# Regex parser (recursive descent -> Thompson NFA)
# ---------------------------------------------------------------------------

class _Parser:
    """Recursive-descent parser that emits Thompson NFA fragments."""

    def __init__(self, pattern: str) -> None:
        self._pat = pattern
        self._pos = 0

    # ------------------------------------------------------------------
    # Top-level
    # ------------------------------------------------------------------

    def parse(self) -> _NFA:
        nfa = self._parse_alternation()
        if self._pos != len(self._pat):
            raise ValueError(
                f"Unexpected character at position {self._pos}: "
                f"'{self._pat[self._pos]}'"
            )
        return nfa

    # ------------------------------------------------------------------
    # Grammar:  alternation -> concatenation ('|' concatenation)*
    # ------------------------------------------------------------------

    def _parse_alternation(self) -> _NFA:
        left = self._parse_concatenation()
        while self._pos < len(self._pat) and self._pat[self._pos] == "|":
            self._pos += 1  # consume '|'
            right = self._parse_concatenation()
            left = _NFA.alternate(left, right)
        return left

    def _parse_concatenation(self) -> _NFA:
        fragments: List[_NFA] = []
        while self._pos < len(self._pat) and self._pat[self._pos] not in ("|", ")"):
            fragments.append(self._parse_quantified())
        if not fragments:
            # Empty alternative: NFA that matches empty string
            s = _new_state()
            a = _new_state()
            st = _State(s)
            ac = _State(a, is_accept=True)
            st.add_transition(_EPSILON, a)
            nfa = _NFA({s: st, a: ac}, s, a)
            return nfa
        result = fragments[0]
        for frag in fragments[1:]:
            result = _NFA.concatenate(result, frag)
        return result

    def _parse_quantified(self) -> _NFA:
        base = self._parse_atom()
        if self._pos < len(self._pat):
            q = self._pat[self._pos]
            if q == "*":
                self._pos += 1
                return _NFA.star(base)
            if q == "+":
                self._pos += 1
                return _NFA.plus(base)
            if q == "?":
                self._pos += 1
                return _NFA.optional(base)
        return base

    def _parse_atom(self) -> _NFA:
        if self._pos >= len(self._pat):
            raise ValueError("Unexpected end of pattern.")
        ch = self._pat[self._pos]

        if ch == "(":
            self._pos += 1
            inner = self._parse_alternation()
            if self._pos >= len(self._pat) or self._pat[self._pos] != ")":
                raise ValueError("Unmatched '(' in pattern.")
            self._pos += 1
            return inner

        if ch == "[":
            return self._parse_char_class()

        if ch == ".":
            self._pos += 1
            return _NFA.from_any()

        if ch == "\\":
            return self._parse_escape()

        # Anchors – represented as zero-width assertions via epsilon transitions
        if ch == "^":
            self._pos += 1
            return self._anchor_nfa("^")

        if ch == "$":
            self._pos += 1
            return self._anchor_nfa("$")

        # Literal character
        self._pos += 1
        return _NFA.from_literal(ch)

    def _parse_escape(self) -> _NFA:
        self._pos += 1  # consume '\\'
        if self._pos >= len(self._pat):
            raise ValueError("Trailing backslash in pattern.")
        ch = self._pat[self._pos]
        self._pos += 1
        mapping = {"n": "\n", "t": "\t", "r": "\r", "s": " \t\n\r", "d": "0123456789"}
        if ch in mapping:
            chars = set(mapping[ch])
            if len(chars) == 1:
                return _NFA.from_literal(next(iter(chars)))
            return _NFA.from_char_class(chars)
        return _NFA.from_literal(ch)

    def _parse_char_class(self) -> _NFA:
        self._pos += 1  # consume '['
        negated = False
        if self._pos < len(self._pat) and self._pat[self._pos] == "^":
            negated = True
            self._pos += 1
        chars: Set[str] = set()
        while self._pos < len(self._pat) and self._pat[self._pos] != "]":
            ch = self._pat[self._pos]
            if ch == "\\" and self._pos + 1 < len(self._pat):
                self._pos += 1
                ch = self._pat[self._pos]
            chars.add(ch)
            self._pos += 1
        if self._pos >= len(self._pat):
            raise ValueError("Unmatched '[' in pattern.")
        self._pos += 1  # consume ']'
        return _NFA.from_char_class(chars, negated)

    @staticmethod
    def _anchor_nfa(kind: str) -> _NFA:
        """Create a zero-width anchor NFA (matched during simulation)."""
        s = _new_state()
        a = _new_state()
        st = _State(s)
        ac = _State(a, is_accept=True)
        st.add_transition(kind, a)   # special labels "^" / "$"
        return _NFA({s: st, a: ac}, s, a)


# ---------------------------------------------------------------------------
# Match result
# ---------------------------------------------------------------------------

@dataclass
class Match:
    """Result of a successful regex match."""
    text: str           # full input text
    start: int          # start index of match (inclusive)
    end: int            # end index of match (exclusive)

    @property
    def group(self) -> str:
        """Return the matched substring."""
        return self.text[self.start:self.end]

    def __repr__(self) -> str:
        return f"Match(start={self.start}, end={self.end}, group={self.group!r})"


# ---------------------------------------------------------------------------
# NFA simulator
# ---------------------------------------------------------------------------

class _Simulator:
    """
    Simulates a Thompson NFA on input text using the powerset (active-states)
    technique.  Time complexity: O(|text| * |states|).
    """

    def __init__(self, nfa: _NFA) -> None:
        self._nfa = nfa

    def _epsilon_closure(
        self, sids: Set[int], text: str, pos: int, at_start: bool, at_end: bool
    ) -> FrozenSet[int]:
        """Compute epsilon closure, honouring anchor labels."""
        stack = list(sids)
        visited: Set[int] = set(sids)
        while stack:
            sid = stack.pop()
            state = self._nfa.states[sid]
            for label, targets in state.transitions.items():
                if label == _EPSILON:
                    for t in targets:
                        if t not in visited:
                            visited.add(t)
                            stack.append(t)
                elif label == "^" and at_start:
                    for t in targets:
                        if t not in visited:
                            visited.add(t)
                            stack.append(t)
                elif label == "$" and at_end:
                    for t in targets:
                        if t not in visited:
                            visited.add(t)
                            stack.append(t)
        return frozenset(visited)

    def _step(
        self, current: FrozenSet[int], ch: str, pos: int,
        at_start: bool, at_end: bool
    ) -> FrozenSet[int]:
        """Advance active states by consuming character *ch*."""
        next_states: Set[int] = set()
        for sid in current:
            state = self._nfa.states[sid]
            for label, targets in state.transitions.items():
                if label == _EPSILON or label in ("^", "$"):
                    continue
                matched = False
                if isinstance(label, _CharClass):
                    matched = label.matches(ch)
                elif label == _ANY:
                    matched = (ch != "\n")
                elif label == ch:
                    matched = True
                if matched:
                    next_states.update(targets)
        return self._epsilon_closure(next_states, "", pos, at_start, at_end)

    def _is_accepting(self, states: FrozenSet[int]) -> bool:
        return any(self._nfa.states[s].is_accept for s in states)

    def try_match(self, text: str, start: int) -> Optional[int]:
        """
        Try to match starting at *start*.  Returns the end index (exclusive)
        of the longest match, or None if no match.
        """
        n = len(text)
        at_start = start == 0
        at_end = start == n
        current = self._epsilon_closure({self._nfa.start}, text, start, at_start, at_end)
        last_accept: Optional[int] = None
        if self._is_accepting(current):
            last_accept = start
        for i in range(start, n):
            ch = text[i]
            at_end = (i + 1 == n)
            current = self._step(current, ch, i, at_start=(i == 0), at_end=at_end)
            if not current:
                break
            if self._is_accepting(current):
                last_accept = i + 1
        return last_accept


# ---------------------------------------------------------------------------
# Compiled regular expression
# ---------------------------------------------------------------------------

class CompiledRegex:
    """
    A compiled regular expression backed by a Thompson NFA.

    Obtain instances via :func:`compile`.
    """

    def __init__(self, pattern: str, nfa: _NFA, compile_time_ns: int) -> None:
        self._pattern = pattern
        self._nfa = nfa
        self._sim = _Simulator(nfa)
        self._compile_time_ns = compile_time_ns

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def match(self, text: str) -> Optional[Match]:
        """
        Try to match the pattern at the *beginning* of *text*.

        Returns a :class:`Match` on success, ``None`` otherwise.
        """
        end = self._sim.try_match(text, 0)
        if end is None:
            return None
        return Match(text=text, start=0, end=end)

    def search(self, text: str) -> Optional[Match]:
        """
        Scan through *text* looking for the first location where the pattern
        produces a match.

        Returns a :class:`Match` on success, ``None`` otherwise.
        """
        for start in range(len(text) + 1):
            end = self._sim.try_match(text, start)
            if end is not None:
                return Match(text=text, start=start, end=end)
        return None

    def find_all(self, text: str) -> List[Match]:
        """
        Return a list of all non-overlapping matches in *text*.

        Matches are found left-to-right; after each match the search resumes
        from the end of the previous match (or advances by 1 if the match was
        zero-length to avoid infinite loops).
        """
        results: List[Match] = []
        pos = 0
        n = len(text)
        while pos <= n:
            end = self._sim.try_match(text, pos)
            if end is None:
                pos += 1
                continue
            results.append(Match(text=text, start=pos, end=end))
            if end == pos:
                pos += 1  # zero-length match: advance to avoid loop
            else:
                pos = end
        return results

    def state_count(self) -> int:
        """Return the number of NFA states in the compiled automaton."""
        return len(self._nfa.states)

    def nfa_graph(self) -> Dict[str, Any]:
        """
        Return a graph representation of the NFA as a plain dict::

            {
                "pattern":    str,
                "start":      int,
                "accept":     int,
                "states":     [{"id": int, "is_accept": bool}, ...],
                "transitions": [
                    {"from": int, "label": str, "to": int}, ...
                ],
            }
        """
        states_list = [
            {"id": st.sid, "is_accept": st.is_accept}
            for st in self._nfa.states.values()
        ]
        transitions_list = []
        for st in self._nfa.states.values():
            for label, targets in st.transitions.items():
                if label == _EPSILON:
                    label_str = "ε"
                elif label == _ANY:
                    label_str = "."
                elif label == "^":
                    label_str = "^"
                elif label == "$":
                    label_str = "$"
                elif isinstance(label, _CharClass):
                    label_str = repr(label)
                else:
                    label_str = repr(label)
                for t in targets:
                    transitions_list.append(
                        {"from": st.sid, "label": label_str, "to": t}
                    )
        return {
            "pattern": self._pattern,
            "start": self._nfa.start,
            "accept": self._nfa.accept,
            "states": states_list,
            "transitions": transitions_list,
        }

    def compile_time_ns(self) -> int:
        """Return compilation time in nanoseconds."""
        return self._compile_time_ns

    def __repr__(self) -> str:
        return f"CompiledRegex(pattern={self._pattern!r}, states={self.state_count()})"


# ---------------------------------------------------------------------------
# Module-level compile() entry point
# ---------------------------------------------------------------------------

def compile(pattern: str) -> CompiledRegex:  # noqa: A001  (shadows built-in intentionally)
    """
    Compile a regular expression *pattern* into a :class:`CompiledRegex`.

    Parameters
    ----------
    pattern : str
        Regular expression string using the syntax described at the top of
        this module.

    Returns
    -------
    CompiledRegex
        Reusable compiled regex object.

    Raises
    ------
    ValueError
        If the pattern contains a syntax error.
    """
    t0 = time.perf_counter_ns()
    parser = _Parser(pattern)
    nfa = parser.parse()
    t1 = time.perf_counter_ns()
    return CompiledRegex(pattern=pattern, nfa=nfa, compile_time_ns=(t1 - t0))


# ---------------------------------------------------------------------------
# Convenience wrappers (module-level)
# ---------------------------------------------------------------------------

def match(pattern: str, text: str) -> Optional[Match]:
    """Compile *pattern* and attempt to match at the start of *text*."""
    return compile(pattern).match(text)


def search(pattern: str, text: str) -> Optional[Match]:
    """Compile *pattern* and search for the first occurrence in *text*."""
    return compile(pattern).search(text)


def find_all(pattern: str, text: str) -> List[Match]:
    """Compile *pattern* and return all non-overlapping matches in *text*."""
    return compile(pattern).find_all(text)
