"""
Pomodoro Productivity Timer with Task Labelling and Session Log Analytics
25-min work + 5-min break cycles, customizable, session logging, daily stats.
"""

import time
import os
import json
import sys
from datetime import datetime, date

LOG_FILE = "pomodoro_log.json"

DEFAULT_CONFIG = {
    "work_minutes":       25,
    "short_break_minutes": 5,
    "long_break_minutes": 15,
    "sessions_before_long_break": 4,
}


def load_log():
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE) as f:
                return json.load(f)
        except:
            pass
    return []


def save_log(log):
    with open(LOG_FILE, 'w') as f:
        json.dump(log, f, indent=2)


def format_duration(minutes):
    h = int(minutes // 60)
    m = int(minutes % 60)
    return f"{h}h {m}m" if h else f"{m}m"


def countdown(seconds, label, symbol="🍅"):
    print(f"\n  {symbol} {label} — {format_duration(seconds/60)}")
    print(f"  Press Ctrl+C to skip.\n")

    try:
        start = time.time()
        while True:
            elapsed = time.time() - start
            remaining = max(0, seconds - elapsed)
            if remaining <= 0:
                break
            mins = int(remaining // 60)
            secs = int(remaining % 60)
            bar_len = 30
            filled = int((elapsed / seconds) * bar_len)
            bar = '█' * filled + '░' * (bar_len - filled)
            sys.stdout.write(f"\r  [{bar}] {mins:02d}:{secs:02d} remaining  ")
            sys.stdout.flush()
            time.sleep(0.5)

        sys.stdout.write(f"\r  {'─'*50}\n")
        sys.stdout.flush()
        return True   # completed normally

    except KeyboardInterrupt:
        sys.stdout.write(f"\r  ⚠  Skipped.{' '*40}\n")
        sys.stdout.flush()
        return False  # skipped


def alert(message):
    print(f"\n  {'='*50}")
    print(f"  🔔 {message}")
    print(f"  {'='*50}")
    sys.stdout.write('\a'); sys.stdout.flush()


def run_pomodoro(config=None, task_name="Focus Session"):
    if config is None:
        config = DEFAULT_CONFIG

    log = load_log()
    work_secs        = config['work_minutes'] * 60
    short_break_secs = config['short_break_minutes'] * 60
    long_break_secs  = config['long_break_minutes'] * 60
    cycles_for_long  = config['sessions_before_long_break']

    session_count   = 0
    total_work_mins = 0

    print(f"\n  ╔══════════════════════════════════════╗")
    print(f"  ║   Pomodoro Timer — {task_name[:20]:<20}  ║")
    print(f"  ╚══════════════════════════════════════╝")
    print(f"  Work: {config['work_minutes']}m | Short break: {config['short_break_minutes']}m | Long break: {config['long_break_minutes']}m")
    print(f"  Long break after every {cycles_for_long} sessions.\n")

    while True:
        session_count += 1
        print(f"\n  ── Session {session_count} | Task: {task_name} ──")

        start_time = datetime.now()
        completed  = countdown(work_secs, f"Work Session #{session_count}", "🍅")
        end_time   = datetime.now()

        if completed:
            alert(f"Session #{session_count} complete! Time for a break.")
            actual_mins = round((end_time - start_time).total_seconds() / 60, 1)
            total_work_mins += actual_mins

            entry = {
                "task":       task_name,
                "session":    session_count,
                "start":      start_time.isoformat(),
                "end":        end_time.isoformat(),
                "duration_m": actual_mins,
                "completed":  True,
                "date":       str(date.today()),
            }
            log.append(entry)
            save_log(log)

        print(f"\n  Total work today: {format_duration(total_work_mins)}")

        continue_ans = input("  Continue to next session? (y/n): ").strip().lower()
        if continue_ans != 'y':
            break

        # Choose break type
        if session_count % cycles_for_long == 0:
            alert(f"🌿 Long break — {config['long_break_minutes']} minutes")
            countdown(long_break_secs, "Long Break", "☕")
        else:
            alert(f"☕ Short break — {config['short_break_minutes']} minutes")
            countdown(short_break_secs, "Short Break", "💤")

    print(f"\n  Session ended. Total sessions: {session_count}, Work: {format_duration(total_work_mins)}")
    return log


def daily_stats(log):
    today = str(date.today())
    today_entries = [e for e in log if e.get('date') == today]

    print(f"\n  {'═'*55}")
    print(f"  📊 Daily Stats — {today}")
    print(f"  {'═'*55}")

    if not today_entries:
        print("  No sessions logged today.")
        return

    total_mins = sum(e.get('duration_m', 0) for e in today_entries)
    tasks = {}
    for e in today_entries:
        t = e.get('task', 'Unknown')
        tasks[t] = tasks.get(t, 0) + e.get('duration_m', 0)

    print(f"  Sessions completed : {len(today_entries)}")
    print(f"  Total focus time   : {format_duration(total_mins)}")
    print(f"\n  By Task:")
    for task, mins in sorted(tasks.items(), key=lambda x: -x[1]):
        bar = '▇' * min(20, int(mins / 5))
        print(f"    {task:<25} {format_duration(mins):>8}  {bar}")

    print(f"  {'═'*55}\n")


def weekly_stats(log):
    from datetime import timedelta
    today = date.today()
    week_ago = today - timedelta(days=7)

    week_entries = [e for e in log
                    if e.get('date') and date.fromisoformat(e['date']) >= week_ago]

    print(f"\n  {'═'*55}")
    print(f"  📈 Weekly Stats (last 7 days)")
    print(f"  {'═'*55}")

    if not week_entries:
        print("  No sessions in the past week.")
        return

    by_day = {}
    for e in week_entries:
        d = e.get('date', '?')
        by_day.setdefault(d, {'sessions': 0, 'minutes': 0})
        by_day[d]['sessions'] += 1
        by_day[d]['minutes']  += e.get('duration_m', 0)

    print(f"  {'Date':<14} {'Sessions':>9} {'Work Time':>12}  {'Bar'}")
    print(f"  {'─'*55}")
    for d in sorted(by_day):
        data = by_day[d]
        bar = '▇' * min(20, data['sessions'])
        print(f"  {d:<14} {data['sessions']:>9} {format_duration(data['minutes']):>12}  {bar}")

    total = sum(d['minutes'] for d in by_day.values())
    print(f"  {'─'*55}")
    print(f"  Total: {format_duration(total)} across {len(week_entries)} sessions\n")


def configure():
    config = {**DEFAULT_CONFIG}
    print("\n  ── Custom Configuration ──")
    print(f"  (Press Enter to keep default values)")
    try:
        w = input(f"  Work minutes       [{config['work_minutes']}]: ").strip()
        s = input(f"  Short break minutes [{config['short_break_minutes']}]: ").strip()
        l = input(f"  Long break minutes  [{config['long_break_minutes']}]: ").strip()
        c = input(f"  Sessions before long break [{config['sessions_before_long_break']}]: ").strip()
        if w: config['work_minutes'] = int(w)
        if s: config['short_break_minutes'] = int(s)
        if l: config['long_break_minutes'] = int(l)
        if c: config['sessions_before_long_break'] = int(c)
    except ValueError:
        print("  Invalid input. Using defaults.")
    return config


def main():
    print("╔══════════════════════════════════════════╗")
    print("║   Pomodoro Productivity Timer v1.0      ║")
    print("╚══════════════════════════════════════════╝")

    log  = load_log()
    cfg  = DEFAULT_CONFIG

    while True:
        print("\n  [1] Start Session  [2] Daily Stats  [3] Weekly Stats  [4] Configure  [5] Quit")
        choice = input("  Choice: ").strip()
        if choice == '5':
            break
        elif choice == '1':
            task = input("  Task name (e.g. 'Study Python'): ").strip() or "Focus Session"
            run_pomodoro(cfg, task)
            log = load_log()
        elif choice == '2':
            daily_stats(log)
        elif choice == '3':
            weekly_stats(log)
        elif choice == '4':
            cfg = configure()
        else:
            print("  Invalid choice.")

    if os.path.exists(LOG_FILE):
        os.remove(LOG_FILE)
    print("  Goodbye! Stay productive.")


if __name__ == "__main__":
    main()
