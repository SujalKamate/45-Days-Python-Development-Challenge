# Construction Project Monitoring System with Milestone Tracking
from datetime import date, timedelta
projects   = {}
milestones = {}
_pid = _mid = 1
def create_project(name, client, total_budget, start_date, end_date, manager):
    global _pid
    pid = f"CONS{_pid:04d}"; _pid += 1
    projects[pid] = {
        "name":name, "client":client, "budget":total_budget,
        "spent":0, "start":start_date, "end":end_date,
        "manager":manager, "status":"Active",
        "milestones":[], "completion_pct":0
    }
    duration = (end_date - start_date).days
    print(f"  [{pid}] {name} | {client} | Rs.{total_budget:,} | {duration} days | {manager}")
    return pid
def add_milestone(pid, title, planned_date, budget_allocation, dependencies=None):
    global _mid
    if pid not in projects: print("  Project not found."); return None
    mid = f"MS{_mid:04d}"; _mid += 1
    milestones[mid] = {
        "pid":pid, "title":title, "planned":planned_date,
        "budget":budget_allocation, "spent":0,
        "actual":None, "status":"Pending",
        "completion":0, "dependencies":dependencies or []
    }
    projects[pid]["milestones"].append(mid)
    print(f"  [{mid}] {title} | Planned:{planned_date} | Budget:Rs.{budget_allocation:,}")
    return mid
def update_milestone(mid, completion_pct, actual_date=None, amount_spent=0):
    if mid not in milestones: print("  Milestone not found."); return
    m = milestones[mid]
    m["completion"] = min(100, completion_pct)
    m["spent"]     += amount_spent
    if completion_pct >= 100:
        m["status"]  = "Completed"
        m["actual"]  = actual_date or date.today()
        projects[m["pid"]]["spent"] += m["spent"]
    elif completion_pct > 0:
        m["status"] = "In Progress"
    delay = ""
    if m["actual"] and m["actual"] > m["planned"]:
        days_late = (m["actual"] - m["planned"]).days
        delay = f" ⚠ {days_late}d late"
    print(f"  [{mid}] {m['title'][:35]} | {completion_pct}% | {m['status']}{delay}")
    recalc_project_completion(m["pid"])
def recalc_project_completion(pid):
    if pid not in projects: return
    p  = projects[pid]
    ms = [milestones[mid] for mid in p["milestones"] if mid in milestones]
    if not ms: return
    avg = round(sum(m["completion"] for m in ms) / len(ms), 1)
    p["completion_pct"] = avg
    if avg >= 100: p["status"] = "Completed"
def log_expense(pid, description, amount):
    if pid not in projects: return
    projects[pid]["spent"] += amount
    print(f"  [{pid}] Expense: {description} — Rs.{amount:,} | Total spent: Rs.{projects[pid]['spent']:,}")
def project_dashboard(pid):
    if pid not in projects: return
    p    = projects[pid]
    today= date.today()
    days_elapsed  = (today - p["start"]).days
    total_duration= (p["end"] - p["start"]).days
    time_pct = round(days_elapsed / total_duration * 100, 1) if total_duration else 0
    budget_pct = round(p["spent"] / p["budget"] * 100, 1) if p["budget"] else 0
    schedule_var = p["completion_pct"] - time_pct
    budget_var   = budget_pct - p["completion_pct"]
    print(f"\n{'='*54}")
    print(f"  PROJECT DASHBOARD — {p['name']} [{pid}]")
    print(f"{'='*54}")
    print(f"  Client     : {p['client']}  |  Manager: {p['manager']}")
    print(f"  Timeline   : {p['start']} → {p['end']}")
    print(f"  Completion : {p['completion_pct']}%  |  Time elapsed: {time_pct}%")
    sched_status = "✔ On Track" if schedule_var >= -5 else "⚠ Behind Schedule"
    print(f"  Schedule   : {sched_status} (variance: {schedule_var:+.1f}%)")
    budg_status  = "✔ Within Budget" if budget_var <= 5 else "⚠ Over Budget"
    print(f"  Budget     : Rs.{p['spent']:,} / Rs.{p['budget']:,} ({budget_pct}%) {budg_status}")
    print(f"\n  Milestones:")
    print(f"  {'ID':<8} {'Title':<28} {'Plan':<12} {'Done%':>6} {'Status'}")
    for mid in p["milestones"]:
        m = milestones[mid]
        actual_str = str(m["actual"]) if m["actual"] else "—"
        print(f"  {mid:<8} {m['title'][:28]:<28} {str(m['planned']):<12} {m['completion']:>5}% {m['status']}")
    print(f"{'='*54}")

def delay_report():
    today = date.today()
    print(f"\n--- Delay Report (as of {today}) ---")
    found = False
    for mid, m in milestones.items():
        if m["status"] == "Pending" and m["planned"] < today:
            days = (today - m["planned"]).days
            pname = projects[m["pid"]]["name"]
            print(f"  ⚠ [{mid}] {m['title'][:35]} | {days}d overdue | Project: {pname}")
            found = True
        elif m["status"] == "Completed" and m["actual"] and m["actual"] > m["planned"]:
            days = (m["actual"] - m["planned"]).days
            print(f"  ⚡[{mid}] {m['title'][:35]} | Completed {days}d late")
            found = True
    if not found: print("  No delays detected.")

def main():
    print("=== Construction Project Monitoring System ===")
    today = date.today()
    p1 = create_project("City Mall Phase 1",    "Urban Developers",  50000000,
                        today - timedelta(days=60), today + timedelta(days=240), "Mr. Sharma")
    p2 = create_project("Highway Bridge Repair","NHAI",             12000000,
                        today - timedelta(days=30), today + timedelta(days=90),  "Ms. Verma")
    m1 = add_milestone(p1, "Site Clearing & Levelling", today-timedelta(days=50), 2000000)
    m2 = add_milestone(p1, "Foundation Work",           today-timedelta(days=20), 8000000, [m1])
    m3 = add_milestone(p1, "Structural Steel Frame",    today+timedelta(days=30), 12000000,[m2])
    m4 = add_milestone(p1, "Concrete Slab — 1st Floor", today+timedelta(days=60), 6000000, [m3])
    m5 = add_milestone(p2, "Traffic Diversion Setup",   today-timedelta(days=25), 500000)
    m6 = add_milestone(p2, "Old Bridge Demolition",     today-timedelta(days=5),  2000000, [m5])
    m7 = add_milestone(p2, "New Pier Construction",     today+timedelta(days=30), 5000000, [m6])
    update_milestone(m1, 100, today-timedelta(days=45), 2100000)
    update_milestone(m2, 80,  amount_spent=6500000)
    update_milestone(m5, 100, today-timedelta(days=22), 480000)
    update_milestone(m6, 60,  amount_spent=1200000)
    log_expense(p1, "Equipment Hire", 350000)
    log_expense(p2, "Material Procurement", 800000)
    project_dashboard(p1)
    project_dashboard(p2)
    delay_report()

if __name__ == "__main__":
    main()
