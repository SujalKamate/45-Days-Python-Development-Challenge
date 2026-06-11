"""
CLI Habit Tracker with Streak Calculation and Monthly Calendar View
Add/remove/list habits, mark daily completion, streaks, monthly calendar.
"""

import json
import os
from datetime import date, timedelta
from calendar import monthrange

DATA_FILE = "habits.json"


def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {"habits": {}}


def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)


def today_str():
    return str(date.today())


def add_habit(data):
    name = input("  Habit name: ").strip()
    if not name:
        print("  ✗ Name cannot be empty."); return
    key = name.lower().replace(" ", "_")
    if key in data["habits"]:
        print(f"  ✗ Habit '{name}' already exists."); return
    data["habits"][key] = {
        "name": name,
        "created": today_str(),
        "completions": [],
        "color": "🟢",
    }
    save_data(data)
    print(f"  ✓ Habit '{name}' added.")


def remove_habit(data):
    list_habits(data)
    key = input("  Enter habit key to remove: ").strip().lower().replace(" ", "_")
    if key not in data["habits"]:
        print("  ✗ Habit not found."); return
    name = data["habits"][key]["name"]
    confirm = input(f"  Remove '{name}'? (y/n): ").strip().lower()
    if confirm == "y":
        del data["habits"][key]
        save_data(data)
        print(f"  ✓ '{name}' removed.")


def list_habits(data):
    habits = data["habits"]
    if not habits:
        print("  No habits yet. Add one!"); return
    print(f"\n  {'─'*55}")
    print(f"  {'Key':<22} {'Name':<25} {'Today'}")
    print(f"  {'─'*55}")
    today = today_str()
    for key, h in habits.items():
        done = today in h["completions"]
        status = "✓ Done" if done else "○ Pending"
        print(f"  {key:<22} {h['name']:<25} {status}")
    print(f"  {'─'*55}")


def mark_complete(data):
    list_habits(data)
    key = input("  Enter habit key to mark complete: ").strip().lower().replace(" ", "_")
    if key not in data["habits"]:
        print("  ✗ Habit not found."); return
    today = today_str()
    h = data["habits"][key]
    if today in h["completions"]:
        print(f"  ℹ  '{h['name']}' already marked complete today.")
        undo = input("  Unmark? (y/n): ").strip().lower()
        if undo == "y":
            h["completions"].remove(today)
            save_data(data)
            print(f"  ✓ Unmarked.")
    else:
        h["completions"].append(today)
        save_data(data)
        streak = calculate_streak(h["completions"])
        print(f"  ✓ '{h['name']}' marked complete! 🔥 Streak: {streak} day(s)")


def calculate_streak(completions):
    if not completions:
        return 0
    dates = sorted(set(completions), reverse=True)
    streak = 0
    expected = date.today()
    for d_str in dates:
        d = date.fromisoformat(d_str)
        if d == expected:
            streak += 1
            expected -= timedelta(days=1)
        elif d == expected + timedelta(days=1):
            # Allow for yesterday starting
            streak += 1
            expected = d - timedelta(days=1)
        else:
            break
    return streak


def longest_streak(completions):
    if not completions:
        return 0
    dates = sorted(set(date.fromisoformat(d) for d in completions))
    max_s = curr_s = 1
    for i in range(1, len(dates)):
        if dates[i] - dates[i-1] == timedelta(days=1):
            curr_s += 1
            max_s = max(max_s, curr_s)
        else:
            curr_s = 1
    return max_s


def show_streaks(data):
    habits = data["habits"]
    if not habits:
        print("  No habits tracked."); return
    print(f"\n  {'═'*55}")
    print(f"  STREAK REPORT — {today_str()}")
    print(f"  {'═'*55}")
    print(f"  {'Habit':<25} {'Current':>9} {'Longest':>9} {'Total':>7}")
    print(f"  {'─'*55}")
    for key, h in habits.items():
        curr = calculate_streak(h["completions"])
        best = longest_streak(h["completions"])
        total = len(h["completions"])
        bar = "🔥" * min(curr, 10)
        print(f"  {h['name']:<25} {curr:>9}  {best:>9}  {total:>7}  {bar}")
    print(f"  {'═'*55}\n")


def monthly_calendar(data):
    today = date.today()
    year = today.year
    month = today.month
    _, days_in_month = monthrange(year, month)
    first_weekday = date(year, month, 1).weekday()  # 0=Mon

    print(f"\n  {'═'*55}")
    print(f"  MONTHLY CALENDAR — {today.strftime('%B %Y')}")

    habits = data["habits"]
    if not habits:
        print("  No habits to display."); return

    # Collect completion data
    month_prefix = f"{year}-{month:02d}-"

    print(f"\n  {'Habit':<28} ", end="")
    for d in range(1, days_in_month + 1):
        print(f"{d:>2}", end=" ")
    print()
    print(f"  {'─'*55}")

    for key, h in habits.items():
        done_days = set()
        for comp in h["completions"]:
            if comp.startswith(month_prefix):
                done_days.add(int(comp.split("-")[2]))

        print(f"  {h['name'][:26]:<28} ", end="")
        for d in range(1, days_in_month + 1):
            if d in done_days:
                print("✓ ", end="")
            elif date(year, month, d) > today:
                print("· ", end="")
            else:
                print("✗ ", end="")
        print()

    print(f"  {'═'*55}\n")


def weekly_summary(data):
    today = date.today()
    week_dates = [str(today - timedelta(days=i)) for i in range(6, -1, -1)]
    print(f"\n  LAST 7 DAYS SUMMARY")
    print(f"  {'─'*60}")
    print(f"  {'Habit':<25}", end="")
    for d_str in week_dates:
        d = date.fromisoformat(d_str)
        print(f" {d.strftime('%a'):>5}", end="")
    print(f"  {'Done':>5}")
    print(f"  {'─'*60}")

    for key, h in data["habits"].items():
        comp_set = set(h["completions"])
        count = 0
        print(f"  {h['name'][:23]:<25}", end="")
        for d_str in week_dates:
            if d_str in comp_set:
                print("    ✓", end="")
                count += 1
            else:
                print("    ·", end="")
        print(f"  {count:>5}/7")
    print(f"  {'─'*60}\n")


def main():
    print("╔══════════════════════════════════════════╗")
    print("║   CLI Habit Tracker v1.0                ║")
    print("╚══════════════════════════════════════════╝")
    data = load_data()

    # Seed demo habits if empty
    if not data["habits"]:
        for name in ["Morning Exercise", "Read 30 mins", "Drink 8 glasses water", "Code Practice"]:
            key = name.lower().replace(" ", "_")
            data["habits"][key] = {"name": name, "created": today_str(), "completions": [], "color": "🟢"}
        # Simulate some past completions
        h = data["habits"]["morning_exercise"]
        for i in range(5, 0, -1):
            h["completions"].append(str(date.today() - timedelta(days=i)))
        h["completions"].append(today_str())
        save_data(data)
        print("  Demo habits loaded.\n")

    menu = {
        "1": ("List Habits",       lambda: list_habits(data)),
        "2": ("Add Habit",         lambda: add_habit(data)),
        "3": ("Remove Habit",      lambda: remove_habit(data)),
        "4": ("Mark Complete",     lambda: mark_complete(data)),
        "5": ("Streak Report",     lambda: show_streaks(data)),
        "6": ("Monthly Calendar",  lambda: monthly_calendar(data)),
        "7": ("Weekly Summary",    lambda: weekly_summary(data)),
        "8": ("Quit", None),
    }

    while True:
        print("\n  ── Menu ──")
        for k, (label, _) in menu.items():
            print(f"  [{k}] {label}")
        choice = input("  Choice: ").strip()
        if choice == "8":
            print("  Keep building good habits! Goodbye.")
            break
        if choice in menu and menu[choice][1]:
            menu[choice][1]()
        else:
            print("  Invalid choice.")

    if os.path.exists(DATA_FILE):
        os.remove(DATA_FILE)


if __name__ == "__main__":
    main()
