"""
Real-Time Typing Speed Test with WPM, Accuracy and Personal Best Tracker
Displays sentence, measures WPM and accuracy, highlights errors, stores best scores.
"""

import time
import os
import json
import random
from datetime import datetime

SCORES_FILE = "typing_scores.json"

SENTENCES = [
    "The quick brown fox jumps over the lazy dog.",
    "Python is a versatile programming language used in many fields.",
    "Practice makes perfect when it comes to touch typing skills.",
    "Every great developer you know got there by solving problems they were unqualified to solve.",
    "Code is like humor. When you have to explain it, it's bad.",
    "The best way to predict the future is to invent it.",
    "First, solve the problem. Then, write the code.",
    "Experience is the name everyone gives to their mistakes.",
    "In order to be irreplaceable one must always be different.",
    "Java is to JavaScript what car is to carpet.",
    "Always code as if the guy who ends up maintaining your code is a violent psychopath.",
    "Simplicity is the soul of efficiency.",
    "Before software can be reusable it first has to be usable.",
    "Make it work, make it right, make it fast.",
    "Debugging is twice as hard as writing the code in the first place.",
]


def load_scores():
    if os.path.exists(SCORES_FILE):
        try:
            with open(SCORES_FILE) as f:
                return json.load(f)
        except:
            pass
    return []


def save_score(scores, entry):
    scores.append(entry)
    scores.sort(key=lambda x: -x['wpm'])
    with open(SCORES_FILE, 'w') as f:
        json.dump(scores[:20], f, indent=2)


def calculate_wpm(text, seconds):
    words = len(text.split())
    minutes = seconds / 60
    return round(words / minutes, 1) if minutes > 0 else 0


def calculate_accuracy(original, typed):
    if not original:
        return 100.0
    errors = sum(1 for a, b in zip(original, typed) if a != b)
    errors += abs(len(original) - len(typed))
    accuracy = max(0, (1 - errors / len(original)) * 100)
    return round(accuracy, 1)


def highlight_errors(original, typed):
    result_correct = []
    result_wrong   = []
    for i, ch in enumerate(original):
        if i < len(typed):
            if typed[i] == ch:
                result_correct.append(ch)
                result_wrong.append(' ')
            else:
                result_correct.append(' ')
                result_wrong.append(typed[i] if typed[i] != ' ' else '_')
        else:
            result_correct.append(' ')
            result_wrong.append('_')

    print(f"\n  Original : {original}")
    print(f"  Correct  : {''.join(result_correct)}")
    print(f"  Errors   : {''.join(result_wrong)}")

    char_errors = [(i, original[i], typed[i] if i < len(typed) else '?')
                   for i in range(len(original))
                   if i >= len(typed) or original[i] != typed[i]]
    return char_errors


def difficulty_sentence(level):
    short   = [s for s in SENTENCES if len(s) <= 50]
    medium  = [s for s in SENTENCES if 50 < len(s) <= 80]
    long_s  = [s for s in SENTENCES if len(s) > 80]

    pool = {1: short or SENTENCES, 2: medium or SENTENCES, 3: long_s or SENTENCES}
    return random.choice(pool.get(level, SENTENCES))


def run_test(difficulty=2):
    sentence = difficulty_sentence(difficulty)

    print(f"\n  {'═'*65}")
    print(f"  TYPING TEST  |  Difficulty: {'Easy' if difficulty==1 else 'Medium' if difficulty==2 else 'Hard'}")
    print(f"  {'═'*65}")
    print(f"\n  Type the following sentence exactly:")
    print(f"\n  ► {sentence}\n")
    print(f"  {'─'*65}")
    input("  Press Enter when ready...")
    print(f"\n  START TYPING NOW:\n  ", end='', flush=True)

    start_time = time.time()
    typed = input()
    end_time = time.time()

    elapsed = end_time - start_time
    wpm      = calculate_wpm(sentence, elapsed)
    accuracy = calculate_accuracy(sentence, typed)
    char_errors = highlight_errors(sentence, typed)

    score = round(wpm * (accuracy / 100))

    print(f"\n  {'═'*55}")
    print(f"  RESULTS")
    print(f"  {'─'*55}")
    print(f"  Time Taken   : {elapsed:.2f} seconds")
    print(f"  WPM          : {wpm}")
    print(f"  Accuracy     : {accuracy}%")
    print(f"  Score        : {score} (WPM × Accuracy%)")
    print(f"  Characters   : {len(typed)} typed / {len(sentence)} expected")
    print(f"  Errors       : {len(char_errors)}")

    if char_errors:
        print(f"\n  Error Details (first 5):")
        for i, orig, got in char_errors[:5]:
            print(f"    Position {i+1}: expected '{orig}', got '{got}'")

    if accuracy == 100:
        print("\n  🎯 Perfect accuracy!")
    elif accuracy >= 95:
        print("\n  ✓ Great accuracy!")
    elif accuracy >= 80:
        print("\n  Decent accuracy — keep practicing.")
    else:
        print("\n  Focus on accuracy before speed!")

    return {'wpm': wpm, 'accuracy': accuracy, 'score': score,
            'time': round(elapsed, 2), 'difficulty': difficulty,
            'date': datetime.now().strftime('%Y-%m-%d %H:%M')}


def show_leaderboard(scores):
    if not scores:
        print("  No scores yet."); return
    print(f"\n  {'═'*60}")
    print(f"  🏆  Personal Best Scores (Top 10)")
    print(f"  {'─'*60}")
    print(f"  {'#':<4} {'WPM':>6} {'Accuracy':>9} {'Score':>7} {'Diff':>6}  {'Date'}")
    print(f"  {'─'*60}")
    for i, s in enumerate(scores[:10], 1):
        diff = {1: 'Easy', 2: 'Med', 3: 'Hard'}.get(s.get('difficulty', 2), '?')
        print(f"  {i:<4} {s['wpm']:>6} {s['accuracy']:>8}% {s['score']:>7} {diff:>6}  {s.get('date','?')}")
    print(f"  {'═'*60}\n")


def typing_tips():
    tips = [
        "Keep your eyes on the screen, not your hands.",
        "Use all 10 fingers — learn proper finger placement.",
        "Don't rush. Accuracy first, speed comes naturally.",
        "Take short breaks to avoid fatigue.",
        "Practice 15-20 minutes daily for best improvement.",
        "Use the home row keys (ASDF JKL;) as your base.",
    ]
    print(f"\n  💡 Typing Tips:")
    for tip in random.sample(tips, 3):
        print(f"    • {tip}")


def main():
    print("╔══════════════════════════════════════════╗")
    print("║   Typing Speed Test v1.0                ║")
    print("╚══════════════════════════════════════════╝")

    scores = load_scores()
    show_leaderboard(scores)

    while True:
        print("  [1] Start Test  [2] Leaderboard  [3] Tips  [4] Quit")
        choice = input("  Choice: ").strip()
        if choice == '4':
            break
        elif choice == '2':
            show_leaderboard(scores)
        elif choice == '3':
            typing_tips()
        elif choice == '1':
            print("  Difficulty: [1] Easy  [2] Medium  [3] Hard")
            try:
                diff = int(input("  Select (1-3): ") or "2")
                diff = max(1, min(3, diff))
            except ValueError:
                diff = 2
            result = run_test(diff)
            save_score(scores, result)
            best = scores[0] if scores else result
            if result['wpm'] >= best['wpm']:
                print("\n  🎉 New personal best!")
            show_leaderboard(scores)
        else:
            print("  Invalid choice.")

    if os.path.exists(SCORES_FILE):
        os.remove(SCORES_FILE)
    print("  Goodbye!")


if __name__ == "__main__":
    main()
