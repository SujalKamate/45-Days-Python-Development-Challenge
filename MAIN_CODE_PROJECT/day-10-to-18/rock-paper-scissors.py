"""
Rock Paper Scissors with Adaptive AI, Statistics and Best-of-N Mode
Tracks win/loss/draw stats, best-of-N rounds, weighted adaptive AI.
"""

import random
import json
import os
from collections import Counter
from datetime import datetime

STATS_FILE = "rps_stats.json"
CHOICES = ["rock", "paper", "scissors"]
BEATS   = {"rock": "scissors", "scissors": "paper", "paper": "rock"}
LOSES   = {"rock": "paper", "scissors": "rock", "paper": "scissors"}
EMOJI   = {"rock": "🪨", "paper": "📄", "scissors": "✂️"}
SHORT   = {"r": "rock", "p": "paper", "s": "scissors"}


def load_stats():
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {"wins": 0, "losses": 0, "draws": 0, "history": [], "ai_mode": "random"}


def save_stats(stats):
    with open(STATS_FILE, "w") as f:
        json.dump(stats, f, indent=2)


def result(player, ai):
    if player == ai:
        return "draw"
    if BEATS[player] == ai:
        return "win"
    return "loss"


# ── AI strategies ─────────────────────────────────────────────────────────────
def ai_random():
    return random.choice(CHOICES)


def ai_adaptive(history):
    """Predict player's next move based on their recent pattern, then counter it."""
    if len(history) < 5:
        return ai_random()
    recent = [h["player"] for h in history[-10:]]
    freq = Counter(recent)
    # Predict the most common choice, counter it
    predicted = max(freq, key=freq.get)
    return LOSES[predicted]   # what beats predicted


def ai_markov(history):
    """Use 2nd-order Markov chain: given last 2 moves, predict next."""
    if len(history) < 3:
        return ai_random()
    transitions = {}
    for i in range(len(history) - 2):
        state = (history[i]["player"], history[i+1]["player"])
        nxt   = history[i+2]["player"]
        transitions.setdefault(state, []).append(nxt)

    last_two = (history[-2]["player"], history[-1]["player"])
    if last_two in transitions and transitions[last_two]:
        predicted = Counter(transitions[last_two]).most_common(1)[0][0]
        return LOSES[predicted]
    return ai_random()


def ai_anti_loss(history):
    """If AI keeps losing to the same move, switch strategy."""
    if len(history) < 3:
        return ai_random()
    recent_ai_losses = [
        h["player"] for h in history[-5:]
        if h["result"] == "win"
    ]
    if recent_ai_losses:
        freq = Counter(recent_ai_losses)
        likely_repeat = freq.most_common(1)[0][0]
        return LOSES[likely_repeat]
    return ai_random()


def choose_ai_move(stats, mode="adaptive"):
    history = stats.get("history", [])
    if mode == "random":
        return ai_random()
    elif mode == "adaptive":
        return ai_adaptive(history)
    elif mode == "markov":
        return ai_markov(history)
    elif mode == "anti_loss":
        return ai_anti_loss(history)
    return ai_random()


# ── Display ───────────────────────────────────────────────────────────────────
def display_round(player, ai, res, round_num=None):
    label = f"Round {round_num}" if round_num else "Result"
    print(f"\n  {label}")
    print(f"  {'─'*35}")
    print(f"  You : {EMOJI[player]} {player.capitalize()}")
    print(f"  AI  : {EMOJI[ai]} {ai.capitalize()}")
    print(f"  {'─'*35}")
    if res == "win":
        print(f"  🎉 You WIN!  {player.capitalize()} beats {ai.capitalize()}")
    elif res == "loss":
        print(f"  💀 You LOSE. {ai.capitalize()} beats {player.capitalize()}")
    else:
        print(f"  🤝 DRAW! Both chose {player.capitalize()}")


def show_stats(stats):
    total = stats["wins"] + stats["losses"] + stats["draws"]
    if total == 0:
        print("  No games played yet."); return
    win_pct  = stats["wins"]   / total * 100
    loss_pct = stats["losses"] / total * 100
    draw_pct = stats["draws"]  / total * 100

    print(f"\n  {'═'*45}")
    print(f"  OVERALL STATISTICS ({total} games)")
    print(f"  {'─'*45}")
    print(f"  Wins   : {stats['wins']:>4}  ({win_pct:>5.1f}%)  {'🟩'*min(stats['wins']//2,10)}")
    print(f"  Losses : {stats['losses']:>4}  ({loss_pct:>5.1f}%)  {'🟥'*min(stats['losses']//2,10)}")
    print(f"  Draws  : {stats['draws']:>4}  ({draw_pct:>5.1f}%)  {'⬜'*min(stats['draws']//2,10)}")
    print(f"  {'─'*45}")

    if stats["history"]:
        move_counts = Counter(h["player"] for h in stats["history"])
        print(f"\n  Your move distribution:")
        for move in CHOICES:
            c = move_counts.get(move, 0)
            pct = c / total * 100 if total else 0
            bar = "▇" * int(pct / 5)
            print(f"  {EMOJI[move]} {move.capitalize():<10} {c:>4}  ({pct:>4.1f}%)  {bar}")

    print(f"  AI mode: {stats.get('ai_mode', 'random')}")
    print(f"  {'═'*45}\n")


def get_player_choice():
    while True:
        raw = input("  Your choice (r/p/s or rock/paper/scissors, q=quit): ").strip().lower()
        if raw == "q":
            return None
        if raw in SHORT:
            return SHORT[raw]
        if raw in CHOICES:
            return raw
        print("  ✗ Invalid. Enter r, p, or s.")


def play_single(stats):
    player = get_player_choice()
    if player is None:
        return False
    ai = choose_ai_move(stats, stats.get("ai_mode", "adaptive"))
    res = result(player, ai)
    display_round(player, ai, res)
    stats["wins" if res == "win" else "losses" if res == "loss" else "draws"] += 1
    stats["history"].append({"player": player, "ai": ai, "result": res,
                              "time": datetime.now().isoformat()})
    save_stats(stats)
    return True


def play_best_of_n(stats, n=5):
    target = (n // 2) + 1
    p_wins = ai_wins = draws = 0
    print(f"\n  ╔══════════════════════════════╗")
    print(f"  ║  Best of {n} — First to {target} wins ║")
    print(f"  ╚══════════════════════════════╝")

    round_num = 0
    while p_wins < target and ai_wins < target and round_num < n:
        round_num += 1
        print(f"\n  Score: You {p_wins} — {ai_wins} AI  |  Draws: {draws}")
        player = get_player_choice()
        if player is None:
            print("  Match abandoned."); return
        ai = choose_ai_move(stats, stats.get("ai_mode", "adaptive"))
        res = result(player, ai)
        display_round(player, ai, res, round_num)
        if res == "win":
            p_wins += 1
            stats["wins"] += 1
        elif res == "loss":
            ai_wins += 1
            stats["losses"] += 1
        else:
            draws += 1
            stats["draws"] += 1
        stats["history"].append({"player": player, "ai": ai, "result": res,
                                  "time": datetime.now().isoformat()})

    print(f"\n  {'═'*35}")
    print(f"  Final Score: You {p_wins} — {ai_wins} AI  |  Draws: {draws}")
    if p_wins >= target:
        print("  🏆 You win the match!")
    elif ai_wins >= target:
        print("  💻 AI wins the match!")
    else:
        print("  🤝 Match drawn!")
    print(f"  {'═'*35}")
    save_stats(stats)


def choose_ai_mode(stats):
    modes = {"1": "random", "2": "adaptive", "3": "markov", "4": "anti_loss"}
    print("\n  AI Modes:")
    print("  [1] Random      — pure random")
    print("  [2] Adaptive    — counters your most common move")
    print("  [3] Markov      — predicts based on your pattern")
    print("  [4] Anti-loss   — adjusts when it keeps losing")
    choice = input("  Select mode (1-4): ").strip()
    if choice in modes:
        stats["ai_mode"] = modes[choice]
        save_stats(stats)
        print(f"  ✓ AI mode set to: {modes[choice]}")


def main():
    print("╔══════════════════════════════════════════╗")
    print("║   Rock Paper Scissors — Adaptive AI      ║")
    print("╚══════════════════════════════════════════╝")

    stats = load_stats()
    show_stats(stats)

    while True:
        print("\n  [1] Single Round  [2] Best-of-5  [3] Best-of-9  [4] AI Mode  [5] Stats  [6] Quit")
        choice = input("  Choice: ").strip()
        if choice == "6":
            print("  Thanks for playing!")
            break
        elif choice == "1":
            play_single(stats)
        elif choice == "2":
            play_best_of_n(stats, 5)
        elif choice == "3":
            play_best_of_n(stats, 9)
        elif choice == "4":
            choose_ai_mode(stats)
        elif choice == "5":
            show_stats(stats)
        else:
            print("  Invalid choice.")

    if os.path.exists(STATS_FILE):
        os.remove(STATS_FILE)


if __name__ == "__main__":
    main()
