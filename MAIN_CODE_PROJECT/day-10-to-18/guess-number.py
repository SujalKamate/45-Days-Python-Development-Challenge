"""
Difficulty-Based Guess the Number Game with High Score Persistence
Features hot/cold hints, attempt scoring, and file-based leaderboard.
"""

import random
import json
import os
import time
from datetime import datetime

SCORE_FILE = "highscores.json"

DIFFICULTIES = {
    'easy':   {'range': (1, 50),   'max_attempts': 10, 'label': '🟢 Easy'},
    'medium': {'range': (1, 200),  'max_attempts': 8,  'label': '🟡 Medium'},
    'hard':   {'range': (1, 1000), 'max_attempts': 7,  'label': '🔴 Hard'},
}


def load_scores():
    if os.path.exists(SCORE_FILE):
        try:
            with open(SCORE_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return {d: [] for d in DIFFICULTIES}


def save_scores(scores):
    with open(SCORE_FILE, 'w') as f:
        json.dump(scores, f, indent=2)


def calculate_score(attempts, max_attempts, time_taken, difficulty):
    multiplier = {'easy': 1, 'medium': 2, 'hard': 3}[difficulty]
    base = max(0, (max_attempts - attempts + 1)) * 100
    time_bonus = max(0, int(60 - time_taken) * 5)
    return (base + time_bonus) * multiplier


def hint(guess, secret):
    diff = abs(guess - secret)
    if diff == 0:
        return "🎯 EXACT MATCH!"
    elif diff <= 5:
        return "🔥 Scorching HOT!"
    elif diff <= 15:
        return "🌡 Very WARM!"
    elif diff <= 30:
        return "😐 Lukewarm."
    elif diff <= 60:
        return "❄ Getting cold..."
    else:
        return "🧊 Ice cold!"


def direction_hint(guess, secret):
    return "⬆ Go HIGHER" if guess < secret else "⬇ Go LOWER"


def play_round(difficulty, scores):
    cfg = DIFFICULTIES[difficulty]
    lo, hi = cfg['range']
    max_att = cfg['max_attempts']
    secret = random.randint(lo, hi)

    print(f"\n  {cfg['label']} Mode | Range: {lo}–{hi} | Max Attempts: {max_att}")
    print(f"  I'm thinking of a number between {lo} and {hi}. Good luck!\n")

    attempts = 0
    start_time = time.time()
    history = []

    while attempts < max_att:
        remaining = max_att - attempts
        print(f"  Attempt {attempts+1}/{max_att}  (Remaining: {remaining})")
        try:
            guess = int(input("  Your guess: "))
        except ValueError:
            print("  ✗ Please enter a valid integer.")
            continue

        if guess < lo or guess > hi:
            print(f"  ✗ Out of range! Please guess between {lo} and {hi}.")
            continue

        attempts += 1
        history.append(guess)
        temperature = hint(guess, secret)
        print(f"  {temperature}")

        if guess == secret:
            elapsed = time.time() - start_time
            score = calculate_score(attempts, max_att, elapsed, difficulty)
            print(f"\n  🎉 Correct! The number was {secret}.")
            print(f"  Solved in {attempts} attempt(s) and {elapsed:.1f}s")
            print(f"  Score: {score} points")
            print(f"  Guess history: {history}")

            entry = {
                "score": score,
                "attempts": attempts,
                "time": round(elapsed, 2),
                "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            }
            scores.setdefault(difficulty, []).append(entry)
            scores[difficulty].sort(key=lambda x: -x['score'])
            scores[difficulty] = scores[difficulty][:5]  # Keep top 5
            save_scores(scores)
            return True, score

        else:
            print(f"  {direction_hint(guess, secret)}")
            if attempts < max_att:
                print()

    elapsed = time.time() - start_time
    print(f"\n  💀 Out of attempts! The number was {secret}.")
    print(f"  Your guesses: {history}")
    return False, 0


def show_leaderboard(scores):
    print(f"\n  {'═'*55}")
    print(f"  🏆  HIGH SCORES LEADERBOARD")
    print(f"  {'═'*55}")
    for diff, cfg in DIFFICULTIES.items():
        entries = scores.get(diff, [])
        print(f"\n  {cfg['label']}")
        if not entries:
            print(f"    No scores yet.")
        else:
            print(f"    {'Rank':<6} {'Score':<10} {'Attempts':<10} {'Time':<10} {'Date'}")
            print(f"    {'─'*50}")
            for i, e in enumerate(entries[:5], 1):
                print(f"    {i:<6} {e['score']:<10} {e['attempts']:<10} {e['time']:<10} {e['date']}")
    print(f"\n  {'═'*55}\n")


def choose_difficulty():
    print("\n  Select Difficulty:")
    for key, cfg in DIFFICULTIES.items():
        lo, hi = cfg['range']
        print(f"    [{key[0]}] {cfg['label']}  |  {lo}–{hi}  |  {cfg['max_attempts']} guesses")
    choice = input("  Enter (e/m/h): ").strip().lower()
    mapping = {'e': 'easy', 'm': 'medium', 'h': 'hard'}
    return mapping.get(choice, 'easy')


def main():
    print("╔══════════════════════════════════════════╗")
    print("║   Guess the Number — Hot/Cold Edition    ║")
    print("╚══════════════════════════════════════════╝")

    scores = load_scores()
    total_wins = 0
    session_scores = []

    while True:
        print("\n  [1] Play  [2] Leaderboard  [3] Quit")
        choice = input("  Choice: ").strip()
        if choice == '3':
            break
        elif choice == '2':
            show_leaderboard(scores)
        elif choice == '1':
            diff = choose_difficulty()
            won, score = play_round(diff, scores)
            if won:
                total_wins += 1
                session_scores.append(score)
            again = input("\n  Play again? (y/n): ").strip().lower()
            if again != 'y':
                break
        else:
            print("  Invalid choice.")

    if session_scores:
        print(f"\n  Session Summary:")
        print(f"  Games Won  : {total_wins}")
        print(f"  Best Score : {max(session_scores)}")
        print(f"  Total Score: {sum(session_scores)}")
    print("  Thanks for playing!")


if __name__ == "__main__":
    main()
