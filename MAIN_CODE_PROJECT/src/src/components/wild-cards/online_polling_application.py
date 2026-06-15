# Online Polling Application with Real-Time Statistics

from datetime import date, timedelta
import random

polls = {}
votes = {}
_poll_id = 1

def create_poll(title, options, creator, end_date=None, allow_multiple=False):
    global _poll_id
    if len(options) < 2: print("  Minimum 2 options required."); return None
    if len(set(options)) != len(options): print("  Duplicate options not allowed."); return None
    pid = f"POLL{_poll_id:04d}"; _poll_id += 1
    end = end_date or (date.today() + timedelta(days=7))
    polls[pid] = {
        "title": title, "options": {opt: 0 for opt in options},
        "creator": creator, "created": date.today(), "end_date": end,
        "allow_multiple": allow_multiple, "total_votes": 0, "active": True
    }
    votes[pid] = {}
    print(f"  [{pid}] '{title}' by {creator} | Options: {options} | Ends: {end}")
    return pid

def cast_vote(pid, voter_id, chosen_options):
    if pid not in polls: print("  Poll not found."); return False
    p = polls[pid]
    if not p["active"]: print(f"  Poll [{pid}] is closed."); return False
    if p["end_date"] < date.today(): p["active"] = False; print("  Poll has expired."); return False
    if voter_id in votes[pid]: print(f"  {voter_id} has already voted in this poll."); return False
    if not isinstance(chosen_options, list): chosen_options = [chosen_options]
    if not p["allow_multiple"] and len(chosen_options) > 1:
        print("  This poll allows only one choice."); return False
    invalid = [o for o in chosen_options if o not in p["options"]]
    if invalid: print(f"  Invalid option(s): {invalid}"); return False
    for opt in chosen_options:
        p["options"][opt] += 1
    p["total_votes"] += 1
    votes[pid][voter_id] = chosen_options
    print(f"  Vote recorded: {voter_id} → {chosen_options} in [{pid}]")
    return True

def live_results(pid):
    if pid not in polls: print("  Poll not found."); return
    p = polls[pid]
    total = p["total_votes"]
    print(f"\n  LIVE RESULTS — {p['title']} [{pid}]")
    print(f"  Status: {'Active' if p['active'] else 'Closed'} | Votes: {total} | Ends: {p['end_date']}")
    print(f"  {'-'*42}")
    sorted_opts = sorted(p["options"].items(), key=lambda x: -x[1])
    for opt, count in sorted_opts:
        pct = (count / total * 100) if total else 0
        bar = "█" * int(pct // 5)
        print(f"  {opt:<25} {count:>4} ({pct:5.1f}%) {bar}")
    if total:
        winner = sorted_opts[0]
        print(f"\n  Leading: '{winner[0]}' with {winner[1]} vote(s)")

def close_poll(pid):
    if pid not in polls: print("  Not found."); return
    polls[pid]["active"] = False
    print(f"  Poll [{pid}] closed. Final votes: {polls[pid]['total_votes']}")

def final_report(pid):
    if pid not in polls: return
    p = polls[pid]
    total = p["total_votes"]
    print(f"\n{'='*50}\n  FINAL POLL REPORT — {p['title']}\n{'='*50}")
    print(f"  Created by : {p['creator']}  |  {p['created']} to {p['end_date']}")
    print(f"  Total Votes: {total}")
    sorted_opts = sorted(p["options"].items(), key=lambda x: -x[1])
    for rank, (opt, count) in enumerate(sorted_opts, 1):
        pct = (count / total * 100) if total else 0
        print(f"  {rank}. {opt:<25} {count:>4} votes  ({pct:.1f}%)")
    if total:
        winner, wvotes = sorted_opts[0]
        print(f"\n  Winner: '{winner}' with {wvotes} vote(s) ({wvotes/total*100:.1f}%)")
    print(f"{'='*50}")

def poll_dashboard():
    print(f"\n{'='*52}\n  POLL DASHBOARD\n{'='*52}")
    for pid, p in polls.items():
        status = "Active" if p["active"] else "Closed"
        print(f"  [{pid}] {p['title'][:35]:<35} | {p['total_votes']:>4} votes | {status}")
    total_votes = sum(p["total_votes"] for p in polls.values())
    print(f"\n  Total Polls: {len(polls)} | Total Votes Cast: {total_votes}")
    print(f"{'='*52}")

def main():
    print("=== Online Polling Application ===")
    p1 = create_poll("Best Programming Language 2025",
                     ["Python","JavaScript","Go","Rust","Java"], "Admin")
    p2 = create_poll("Preferred Work Mode",
                     ["Full Remote","Hybrid","Full Office"], "HR Team")
    p3 = create_poll("Canteen Menu Choice",
                     ["North Indian","South Indian","Chinese","Continental"], "Canteen")
    voters_p1 = ["U001","U002","U003","U004","U005","U006","U007","U008"]
    choices_p1 = ["Python","Python","JavaScript","Go","Python","Rust","Java","Python"]
    for vid, ch in zip(voters_p1, choices_p1):
        cast_vote(p1, vid, ch)
    for i, choice in enumerate(["Full Remote","Hybrid","Full Remote","Full Office","Hybrid"]):
        cast_vote(p2, f"E{i+1:03d}", choice)
    cast_vote(p1, "U001", "Go")   # duplicate attempt
    for i, ch in enumerate(["North Indian","South Indian","Chinese","North Indian"]):
        cast_vote(p3, f"C{i+1:03d}", ch)
    live_results(p1)
    close_poll(p2)
    final_report(p1)
    final_report(p2)
    poll_dashboard()

if __name__ == "__main__":
    main()
