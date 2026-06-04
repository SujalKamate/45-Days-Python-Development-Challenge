"""
Word Frequency Analyzer with Stopword Filtering and Ranked Output
Analyzes text or file, filters stopwords, displays top/bottom N words with percentages.
"""

import re
import os
from collections import Counter

STOPWORDS = {
    'a', 'an', 'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
    'of', 'with', 'by', 'from', 'is', 'are', 'was', 'were', 'be', 'been',
    'has', 'have', 'had', 'do', 'does', 'did', 'not', 'this', 'that', 'it',
    'its', 'as', 'if', 'so', 'he', 'she', 'they', 'we', 'you', 'i', 'me',
    'him', 'her', 'us', 'them', 'my', 'your', 'his', 'our', 'their', 'what',
    'which', 'who', 'will', 'can', 'could', 'would', 'should', 'may', 'might',
    'then', 'than', 'more', 'also', 'into', 'up', 'out', 'about', 'no', 'any',
    'all', 'each', 'there', 'when', 'where', 'how', 'some', 'such', 'just',
}


def tokenize(text):
    """Extract words, strip punctuation, lowercase."""
    return re.findall(r"\b[a-zA-Z']+\b", text.lower())


def filter_stopwords(words, use_stopwords=True, min_length=2):
    if use_stopwords:
        return [w for w in words if w not in STOPWORDS and len(w) >= min_length]
    return [w for w in words if len(w) >= min_length]


def analyze(text, use_stopwords=True, min_length=2):
    raw_words = tokenize(text)
    filtered = filter_stopwords(raw_words, use_stopwords, min_length)
    counter = Counter(filtered)
    total = sum(counter.values())
    return counter, total, len(raw_words), len(filtered)


def print_ranked(counter, total, top_n=10, bottom_n=5, title="Word Frequency Report"):
    print(f"\n  {'═'*65}")
    print(f"  {title}")
    print(f"  Total unique words (filtered): {len(counter)}")
    print(f"  Total word tokens  (filtered): {total}")
    print(f"  {'═'*65}")

    print(f"\n  🔝 Top {top_n} Most Frequent:")
    print(f"  {'#':<5} {'Word':<20} {'Count':<8} {'%':>6}  {'Bar'}")
    print(f"  {'─'*60}")
    for i, (word, count) in enumerate(counter.most_common(top_n), 1):
        pct = count / total * 100 if total else 0
        bar = '▇' * min(30, int(pct * 2))
        print(f"  {i:<5} {word:<20} {count:<8} {pct:>5.1f}%  {bar}")

    if bottom_n and len(counter) > top_n:
        print(f"\n  📉 Bottom {bottom_n} Least Frequent:")
        print(f"  {'#':<5} {'Word':<20} {'Count':<8} {'%':>6}")
        print(f"  {'─'*45}")
        least = counter.most_common()[:-bottom_n-1:-1]
        for i, (word, count) in enumerate(reversed(least), 1):
            pct = count / total * 100 if total else 0
            print(f"  {i:<5} {word:<20} {count:<8} {pct:>5.2f}%")

    print(f"  {'═'*65}\n")


def word_length_distribution(counter):
    lengths = Counter(len(w) for w in counter)
    print(f"\n  Word Length Distribution:")
    print(f"  {'Length':<10} {'Count':<8} {'Bar'}")
    print(f"  {'─'*40}")
    for length in sorted(lengths):
        bar = '▇' * min(30, lengths[length])
        print(f"  {length:<10} {lengths[length]:<8} {bar}")


def percent_breakdown(counter, total, categories=None):
    """Show percentage of custom word categories."""
    if not categories:
        return
    print(f"\n  Custom Category Breakdown:")
    for cat_name, words in categories.items():
        cat_count = sum(counter.get(w, 0) for w in words)
        pct = cat_count / total * 100 if total else 0
        print(f"  {cat_name:<20}: {cat_count} words ({pct:.1f}%)")


SAMPLE_TEXT = """
Python is a versatile programming language that emphasizes code readability.
Python supports multiple programming paradigms including procedural object-oriented
and functional programming. Python has a large standard library that provides many
useful modules for various tasks. Many developers love Python because it combines
simplicity with power. Python is widely used in data science machine learning
web development automation and scripting. The Python community is known for being
welcoming and helpful to newcomers. Learning Python is often recommended as a
first programming language for beginners. Python programs are typically shorter
and easier to read than equivalent programs written in other languages. Python's
philosophy encourages writing clean and readable code through its design principles.
"""


def main():
    print("╔══════════════════════════════════════════╗")
    print("║   Word Frequency Analyzer v1.0           ║")
    print("╚══════════════════════════════════════════╝")

    # Option to load from file or use sample
    source = input("\n  Load from file? (y/n): ").strip().lower()
    if source == 'y':
        path = input("  File path: ").strip()
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                text = f.read()
        else:
            print("  File not found. Using sample text.")
            text = SAMPLE_TEXT
    else:
        text = SAMPLE_TEXT
        print("  Using built-in sample text.")

    use_sw = input("  Filter stopwords? (y/n): ").strip().lower() != 'n'

    try:
        top_n = int(input("  How many top words to show? (default 10): ") or "10")
    except ValueError:
        top_n = 10

    counter, total, raw_count, filtered_count = analyze(text, use_stopwords=use_sw)

    print(f"\n  Raw word count   : {raw_count}")
    print(f"  Filtered count   : {filtered_count}")
    print(f"  Unique words     : {len(counter)}")

    print_ranked(counter, total, top_n=top_n, bottom_n=5)
    word_length_distribution(counter)

    categories = {
        "Programming terms": ['python', 'programming', 'code', 'language', 'library', 'function'],
        "Learning terms": ['learning', 'beginners', 'newcomers', 'developers'],
    }
    percent_breakdown(counter, total, categories)


if __name__ == "__main__":
    main()
