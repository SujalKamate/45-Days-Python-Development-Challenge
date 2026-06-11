"""
Keyword-Based Sentiment Analyzer with Scoring and Custom Dictionary Support
Analyzes paragraphs, scores sentiment, highlights contributing words, supports custom dicts.
"""

import re
import json
import os
from collections import defaultdict


# ── Built-in sentiment lexicon ────────────────────────────────────────────────
POSITIVE_WORDS = {
    "amazing": 3, "excellent": 3, "outstanding": 3, "fantastic": 3,
    "superb": 3, "brilliant": 3, "wonderful": 3, "exceptional": 3,
    "good": 2, "great": 2, "happy": 2, "love": 2, "nice": 2,
    "positive": 2, "awesome": 2, "beautiful": 2, "best": 2,
    "enjoy": 1, "like": 1, "pleasant": 1, "helpful": 1,
    "fine": 1, "okay": 1, "decent": 1, "satisfactory": 1,
    "recommend": 2, "impressive": 2, "delightful": 2, "charming": 2,
    "innovative": 2, "efficient": 2, "reliable": 2, "perfect": 3,
    "excited": 2, "thrilled": 3, "grateful": 2, "pleased": 2,
}

NEGATIVE_WORDS = {
    "terrible": -3, "horrible": -3, "awful": -3, "dreadful": -3,
    "atrocious": -3, "disgusting": -3, "pathetic": -3, "abysmal": -3,
    "bad": -2, "poor": -2, "hate": -2, "dislike": -2, "wrong": -2,
    "ugly": -2, "failure": -2, "useless": -2, "waste": -2,
    "disappointing": -2, "frustrating": -2, "annoying": -2,
    "slow": -1, "mediocre": -1, "bland": -1, "boring": -1,
    "difficult": -1, "problem": -1, "issue": -1, "complaint": -1,
    "broken": -2, "buggy": -2, "unreliable": -2, "confusing": -2,
    "angry": -2, "upset": -2, "miserable": -3, "depressed": -2,
}

NEUTRAL_WORDS = {
    "product": 0, "service": 0, "feature": 0, "update": 0,
    "version": 0, "software": 0, "application": 0, "system": 0,
}

NEGATION_WORDS = {"not", "never", "no", "nor", "neither", "without", "barely",
                  "hardly", "scarcely", "don't", "doesn't", "didn't", "won't",
                  "cannot", "can't", "isn't", "wasn't", "aren't", "weren't"}

INTENSIFIERS = {
    "very": 1.5, "extremely": 2.0, "absolutely": 2.0, "incredibly": 2.0,
    "quite": 1.2, "rather": 1.1, "somewhat": 0.8, "slightly": 0.6,
    "fairly": 0.9, "really": 1.3, "totally": 1.5, "completely": 1.8,
}


def build_lexicon(positive=None, negative=None, neutral=None):
    lex = {}
    lex.update(NEUTRAL_WORDS if neutral is None else neutral)
    lex.update(POSITIVE_WORDS if positive is None else positive)
    lex.update(NEGATIVE_WORDS if negative is None else negative)
    return lex


def load_custom_lexicon(filepath):
    if not os.path.exists(filepath):
        print(f"  ✗ File '{filepath}' not found.")
        return {}
    with open(filepath) as f:
        data = json.load(f)
    print(f"  ✓ Loaded {len(data)} custom words from '{filepath}'.")
    return data


def tokenize(text):
    return re.findall(r"\b[a-zA-Z']+\b", text.lower())


def analyze(text: str, lexicon: dict = None, return_details=True):
    if lexicon is None:
        lexicon = build_lexicon()

    tokens = tokenize(text)
    score  = 0.0
    contributions = []
    negated_next  = False
    intensifier   = 1.0

    for i, word in enumerate(tokens):
        if word in NEGATION_WORDS:
            negated_next = True
            continue

        if word in INTENSIFIERS:
            intensifier = INTENSIFIERS[word]
            continue

        if word in lexicon and lexicon[word] != 0:
            base_score = lexicon[word] * intensifier
            if negated_next:
                base_score = -base_score * 0.8  # negation flips and slightly reduces
                negated_next = False

            score += base_score
            contributions.append({
                "word":     word,
                "base":     lexicon[word],
                "modifier": intensifier,
                "final":    round(base_score, 3),
                "negated":  negated_next,
            })
            intensifier = 1.0
        else:
            negated_next  = False
            intensifier   = 1.0

    if not return_details:
        return score

    return {
        "text":          text,
        "score":         round(score, 3),
        "tokens":        len(tokens),
        "scored_words":  len(contributions),
        "contributions": contributions,
        "label":         label_score(score),
        "magnitude":     abs(score),
    }


def label_score(score: float) -> str:
    if score >= 6:   return "Very Positive 😊"
    if score >= 3:   return "Positive 🙂"
    if score >= 1:   return "Slightly Positive 😐"
    if score > -1:   return "Neutral 😶"
    if score > -3:   return "Slightly Negative 😕"
    if score > -6:   return "Negative 😞"
    return           "Very Negative 😠"


def print_analysis(result: dict):
    text  = result["text"]
    score = result["score"]
    label = result["label"]
    contributions = result["contributions"]

    print(f"\n  {'═'*60}")
    print(f"  TEXT: \"{text[:70]}{'...' if len(text)>70 else ''}\"")
    print(f"  {'─'*60}")
    print(f"  Score    : {score:+.3f}")
    print(f"  Sentiment: {label}")
    print(f"  Tokens   : {result['tokens']}  |  Scored words: {result['scored_words']}")

    if contributions:
        print(f"\n  Contributing Words:")
        print(f"  {'─'*50}")
        pos = [c for c in contributions if c["final"] > 0]
        neg = [c for c in contributions if c["final"] < 0]

        if pos:
            print(f"  Positive contributors:")
            for c in sorted(pos, key=lambda x: -x["final"])[:8]:
                mod = f" ×{c['modifier']:.1f}" if c["modifier"] != 1.0 else ""
                print(f"    + '{c['word']}'  base={c['base']:+}  {mod}  final={c['final']:+.3f}")

        if neg:
            print(f"  Negative contributors:")
            for c in sorted(neg, key=lambda x: x["final"])[:8]:
                neg_tag = " [NEGATED]" if c["negated"] else ""
                print(f"    - '{c['word']}'  base={c['base']:+}  final={c['final']:+.3f}{neg_tag}")

    # Visual score bar
    bar_pos = min(20, max(0, int(score)))
    bar_neg = min(20, max(0, int(-score)))
    bar = "─" * 20 + "│" + "─" * 20
    if score > 0:
        bar = " " * 20 + "│" + "█" * bar_pos + "─" * (20 - bar_pos)
    elif score < 0:
        bar = "─" * (20 - bar_neg) + "█" * bar_neg + "│" + " " * 20
    print(f"\n  [-20 {bar} +20]  {score:+.1f}")
    print(f"  {'═'*60}")


def batch_analyze(texts, lexicon=None):
    if lexicon is None:
        lexicon = build_lexicon()
    results = [analyze(t, lexicon) for t in texts]
    avg = sum(r["score"] for r in results) / len(results) if results else 0
    print(f"\n  Batch Analysis ({len(results)} texts):")
    print(f"  {'─'*65}")
    print(f"  {'#':<4} {'Score':>7}  {'Label':<25}  {'Preview'}")
    print(f"  {'─'*65}")
    for i, r in enumerate(results, 1):
        preview = r["text"][:40]
        print(f"  {i:<4} {r['score']:>+7.2f}  {r['label']:<25}  {preview}")
    print(f"  {'─'*65}")
    print(f"  Average score: {avg:+.3f}  ({label_score(avg)})")
    return results


def word_cloud(results):
    """Show most impactful words across all analyzed texts."""
    word_scores = defaultdict(list)
    for r in results:
        for c in r.get("contributions", []):
            word_scores[c["word"]].append(c["final"])
    ranked = sorted(word_scores.items(), key=lambda x: abs(sum(x[1])), reverse=True)
    print(f"\n  Top Contributing Words (across all texts):")
    print(f"  {'─'*40}")
    for word, scores in ranked[:15]:
        total = sum(scores)
        icon  = "+" if total > 0 else "-"
        bar   = "█" * min(10, int(abs(total)))
        print(f"  {icon} {word:<20} {total:>+7.2f}  {bar}")


def main():
    print("╔══════════════════════════════════════════╗")
    print("║   Sentiment Analyzer v1.0               ║")
    print("╚══════════════════════════════════════════╝")

    lexicon = build_lexicon()

    sample_texts = [
        "This product is absolutely amazing and I love it! The quality is excellent and very reliable.",
        "Terrible experience. The service was horrible and the product was broken. Total waste of money.",
        "The software is not bad but could be improved. It's quite slow sometimes and a bit confusing.",
        "I'm extremely satisfied with this purchase! The customer support was incredibly helpful.",
        "The movie was mediocre at best. Not horrible but definitely disappointing given the hype.",
        "Fantastic tool! It's incredibly efficient and the interface is beautiful. Highly recommend!",
        "I don't like the new update. It's not good and has many bugs. Very frustrating experience.",
        "The course was fairly good. I enjoyed the practical exercises and found them quite helpful.",
    ]

    print("\n  ── Individual Analysis ──")
    for text in sample_texts[:4]:
        result = analyze(text, lexicon)
        print_analysis(result)

    print("\n  ── Batch Analysis ──")
    results = batch_analyze(sample_texts, lexicon)
    word_cloud(results)

    print("\n  ── Interactive Mode ──")
    while True:
        text = input("\n  Enter text to analyze (or 'q' to quit): ").strip()
        if text.lower() == "q": break
        if text:
            result = analyze(text, lexicon)
            print_analysis(result)


if __name__ == "__main__":
    main()
