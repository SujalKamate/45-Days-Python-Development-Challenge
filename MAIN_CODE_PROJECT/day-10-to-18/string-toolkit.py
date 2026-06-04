"""
Advanced String Manipulation and Pattern Detection Toolkit
Handles word reversal, character analysis, anagram/pangram/isogram checks,
and duplicate removal.
"""

import re
from collections import Counter


def reverse_words(sentence):
    """Reverse word order without reversing individual letters."""
    words = sentence.split()
    return ' '.join(reversed(words))


def count_characters(s):
    """Count vowels, consonants, digits, and special characters."""
    vowels = set('aeiouAEIOU')
    counts = {'vowels': 0, 'consonants': 0, 'digits': 0, 'spaces': 0, 'specials': 0}
    for ch in s:
        if ch in vowels:
            counts['vowels'] += 1
        elif ch.isalpha():
            counts['consonants'] += 1
        elif ch.isdigit():
            counts['digits'] += 1
        elif ch.isspace():
            counts['spaces'] += 1
        else:
            counts['specials'] += 1
    return counts


def is_anagram(s1, s2):
    """Check if two strings are anagrams (ignoring spaces and case)."""
    clean = lambda s: sorted(re.sub(r'[^a-zA-Z]', '', s).lower())
    return clean(s1) == clean(s2)


def is_pangram(s):
    """Check if a string contains every letter of the alphabet."""
    return set('abcdefghijklmnopqrstuvwxyz').issubset(set(s.lower()))


def is_isogram(s):
    """Check if a string has no repeating letters."""
    clean = re.sub(r'[^a-zA-Z]', '', s).lower()
    return len(clean) == len(set(clean))


def remove_duplicates(s):
    """Remove duplicate characters while preserving original order."""
    seen = set()
    result = []
    for ch in s:
        if ch not in seen:
            seen.add(ch)
            result.append(ch)
    return ''.join(result)


def longest_word(sentence):
    words = sentence.split()
    if not words:
        return ""
    return max(words, key=len)


def title_case_custom(sentence):
    """Capitalize first letter of each word, lowercase rest."""
    return ' '.join(w.capitalize() for w in sentence.split())


def count_word_frequency(sentence):
    words = re.findall(r'\b[a-zA-Z]+\b', sentence.lower())
    return Counter(words)


def caesar_shift(s, shift=13):
    """ROT-style shift for strings."""
    result = []
    for ch in s:
        if ch.isalpha():
            base = ord('A') if ch.isupper() else ord('a')
            result.append(chr((ord(ch) - base + shift) % 26 + base))
        else:
            result.append(ch)
    return ''.join(result)


def find_repeated_words(sentence):
    words = re.findall(r'\b[a-zA-Z]+\b', sentence.lower())
    freq = Counter(words)
    return {w: c for w, c in freq.items() if c > 1}


def print_analysis(s):
    print(f"\n{'═'*55}")
    print(f"  Input  : \"{s}\"")
    print(f"{'═'*55}")

    print(f"\n  Reversed Words  : \"{reverse_words(s)}\"")
    print(f"  Title Case      : \"{title_case_custom(s)}\"")
    print(f"  No Duplicates   : \"{remove_duplicates(s)}\"")
    print(f"  Longest Word    : \"{longest_word(s)}\"")

    counts = count_characters(s)
    print(f"\n  Character Breakdown:")
    for k, v in counts.items():
        print(f"    {k:<15}: {v}")

    print(f"\n  Pattern Checks:")
    print(f"    Is Pangram      : {is_pangram(s)}")
    print(f"    Is Isogram      : {is_isogram(s)}")

    freq = count_word_frequency(s)
    if freq:
        print(f"\n  Word Frequencies (top 5):")
        for word, count in freq.most_common(5):
            print(f"    '{word}' → {count}")

    repeated = find_repeated_words(s)
    if repeated:
        print(f"\n  Repeated Words  : {repeated}")

    print(f"{'═'*55}\n")


def anagram_demo():
    pairs = [
        ("listen", "silent"),
        ("hello", "world"),
        ("Astronomer", "Moon starer"),
        ("Python", "Typhon"),
    ]
    print("\n  Anagram Pairs:")
    for a, b in pairs:
        print(f"    '{a}' & '{b}' → {'✓ Anagram' if is_anagram(a, b) else '✗ Not Anagram'}")


def main():
    print("╔══════════════════════════════════════════╗")
    print("║   String Manipulation Toolkit v1.0       ║")
    print("╚══════════════════════════════════════════╝")

    samples = [
        "The quick brown fox jumps over the lazy dog",
        "Hello World hello again world",
        "Was it a car or a cat I saw",
        "abcdefgh",
    ]

    for s in samples:
        print_analysis(s)

    anagram_demo()

    while True:
        user = input("\nEnter your own string (or 'q' to quit): ")
        if user.lower() == 'q':
            break
        print_analysis(user)


if __name__ == "__main__":
    main()
