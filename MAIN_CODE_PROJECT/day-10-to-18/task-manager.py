"""
Full-Featured CLI Task Manager with Projects, Priorities, Tags and Weekly Report
Supports projects/tasks/subtasks, priorities, deadlines, tags, CRUD, search,
JSON persistence, and weekly progress report generation.
"""

import json
import os
from datetime import datetime, date, timedelta
from collections import defaultdict

DATA_FILE = "taskmanager.json"


# ── Data helpers ───────────────────────────────────────────────────────────────
def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def today_str():
    return str(date.today())


def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {"projects": {}, "tasks": {}, "_id_counter": 1}


def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)


def next_id(data):
    nid = data["_id_counter"]
    data["_id_counter"] += 1
    return str(nid)


# ── Project operations ─────────────────────────────────────────────────────────
def add_project(data, name, description="", color="🔵"):
    pid = next_id(data)
    data["projects"][pid] = {
        "id":          pid,
        "name":        name,
        "description": description,
        "color":       color,
        "created":     now_str(),
        "status":      "active",
    }
    save_data(data)
    print(f"  ✓ Project [{pid}] '{name}' created.")
    return pid


def list_projects(data):
    projects = data["projects"]
    if not projects:
        print("  No projects yet."); return
    print(f"\n  {'─'*55}")
    print(f"  {'ID':<5} {'Name':<25} {'Tasks':>6}  {'Status'}")
    print(f"  {'─'*55}")
    for p in projects.values():
        task_count = sum(1 for t in data["tasks"].values() if t.get("project_id") == p["id"])
        print(f"  {p['id']:<5} {p['color']} {p['name']:<23} {task_count:>6}  {p['status']}")
    print(f"  {'─'*55}\n")


# ── Task operations ────────────────────────────────────────────────────────────
def add_task(data, title, project_id=None, priority="medium",
             deadline=None, tags=None, parent_id=None, description=""):
    tid = next_id(data)
    task = {
        "id":          tid,
        "title":       title,
        "description": description,
        "project_id":  project_id,
        "parent_id":   parent_id,
        "priority":    priority,
        "deadline":    deadline,
        "tags":        tags or [],
        "status":      "pending",
        "created":     now_str(),
        "updated":     now_str(),
        "completed":   None,
        "subtasks":    [],
    }
    data["tasks"][tid] = task
    if parent_id and parent_id in data["tasks"]:
        data["tasks"][parent_id]["subtasks"].append(tid)
    save_data(data)
    print(f"  ✓ Task [{tid}] '{title}' added. Priority={priority}  Deadline={deadline or 'none'}")
    return tid


def update_task(data, tid, **kwargs):
    if tid not in data["tasks"]:
        print(f"  ✗ Task [{tid}] not found."); return
    task = data["tasks"][tid]
    for k, v in kwargs.items():
        if k in task:
            task[k] = v
    task["updated"] = now_str()
    save_data(data)
    print(f"  ✓ Task [{tid}] updated.")


def complete_task(data, tid):
    if tid not in data["tasks"]:
        print(f"  ✗ Task [{tid}] not found."); return
    task = data["tasks"][tid]
    task["status"]    = "done"
    task["completed"] = now_str()
    task["updated"]   = now_str()
    # Auto-complete subtasks
    for stid in task.get("subtasks", []):
        if stid in data["tasks"] and data["tasks"][stid]["status"] != "done":
            data["tasks"][stid]["status"]    = "done"
            data["tasks"][stid]["completed"] = now_str()
    save_data(data)
    print(f"  ✓ Task [{tid}] '{task['title']}' marked done.")


def delete_task(data, tid):
    if tid not in data["tasks"]:
        print(f"  ✗ Task [{tid}] not found."); return
    title = data["tasks"][tid]["title"]
    # Remove from parent's subtask list
    parent_id = data["tasks"][tid].get("parent_id")
    if parent_id and parent_id in data["tasks"]:
        data["tasks"][parent_id]["subtasks"] = [
            s for s in data["tasks"][parent_id]["subtasks"] if s != tid
        ]
    del data["tasks"][tid]
    save_data(data)
    print(f"  ✓ Task [{tid}] '{title}' deleted.")


# ── Search & Filter ────────────────────────────────────────────────────────────
def search_tasks(data, query="", status=None, priority=None, tag=None, project_id=None):
    results = []
    for task in data["tasks"].values():
        if task.get("parent_id"):   # skip subtasks in main listing
            continue
        if status and task["status"] != status:
            continue
        if priority and task["priority"] != priority:
            continue
        if tag and tag not in task.get("tags", []):
            continue
        if project_id and task.get("project_id") != project_id:
            continue
        if query and query.lower() not in task["title"].lower() \
                 and query.lower() not in task.get("description","").lower():
            continue
        results.append(task)
    return results


def is_overdue(task):
    if task["status"] == "done":
        return False
    dl = task.get("deadline")
    if not dl:
        return False
    try:
        return date.fromisoformat(dl) < date.today()
    except ValueError:
        return False


def days_until(deadline_str):
    try:
        dl = date.fromisoformat(deadline_str)
        delta = (dl - date.today()).days
        return delta
    except Exception:
        return None


PRIORITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}
PRIORITY_ICON  = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}
STATUS_ICON    = {"pending": "○", "in_progress": "◑", "done": "✓", "cancelled": "✗"}


def list_tasks(data, tasks=None, title="Tasks"):
    if tasks is None:
        tasks = [t for t in data["tasks"].values() if not t.get("parent_id")]

    if not tasks:
        print(f"  No tasks found."); return

    tasks = sorted(tasks, key=lambda t: (
        PRIORITY_ORDER.get(t["priority"], 9),
        t.get("deadline") or "9999",
        t["created"]
    ))

    print(f"\n  {'─'*72}")
    print(f"  {title} ({len(tasks)})")
    print(f"  {'─'*72}")
    print(f"  {'ID':<5} {'P':>2} {'S':>2}  {'Title':<28}  {'Deadline':<12}  {'Tags'}")
    print(f"  {'─'*72}")

    for t in tasks:
        p_icon = PRIORITY_ICON.get(t["priority"], "·")
        s_icon = STATUS_ICON.get(t["status"], "?")
        dl     = t.get("deadline", "")[:10]
        tags   = ", ".join(t.get("tags", []))[:14]
        overdue = " ⚠" if is_overdue(t) else ""
        subs   = f" ({len(t['subtasks'])}↓)" if t.get("subtasks") else ""
        proj   = ""
        if t.get("project_id") and t["project_id"] in data["projects"]:
            proj = f" [{data['projects'][t['project_id']]['name'][:8]}]"
        print(f"  {t['id']:<5} {p_icon:>2} {s_icon:>2}  {t['title'][:28]:<28}  {dl:<12}  {tags}{overdue}{subs}{proj}")

        # Show subtasks indented
        for stid in t.get("subtasks", []):
            if stid in data["tasks"]:
                st = data["tasks"][stid]
                s2 = STATUS_ICON.get(st["status"], "?")
                print(f"  {'':5}  {'':2} {s2:>2}    └─ {st['title'][:25]}")

    print(f"  {'─'*72}\n")


# ── Weekly Report ──────────────────────────────────────────────────────────────
def weekly_report(data):
    today     = date.today()
    week_ago  = today - timedelta(days=7)
    next_week = today + timedelta(days=7)

    all_tasks = list(data["tasks"].values())

    completed_this_week = [
        t for t in all_tasks
        if t.get("completed") and
        date.fromisoformat(t["completed"][:10]) >= week_ago
    ]

    created_this_week = [
        t for t in all_tasks
        if date.fromisoformat(t["created"][:10]) >= week_ago
    ]

    due_next_week = [
        t for t in all_tasks
        if t["status"] not in ("done", "cancelled") and
        t.get("deadline") and
        today <= date.fromisoformat(t["deadline"]) <= next_week
    ]

    overdue = [t for t in all_tasks if is_overdue(t)]

    pending   = [t for t in all_tasks if t["status"] == "pending"]
    in_prog   = [t for t in all_tasks if t["status"] == "in_progress"]
    done_all  = [t for t in all_tasks if t["status"] == "done"]

    print(f"\n  {'═'*60}")
    print(f"  WEEKLY PROGRESS REPORT — {today}")
    print(f"  {'═'*60}")

    print(f"\n  📊 Overview:")
    print(f"    Total tasks       : {len(all_tasks)}")
    print(f"    Pending           : {len(pending)}")
    print(f"    In Progress       : {len(in_prog)}")
    print(f"    Completed (total) : {len(done_all)}")
    print(f"    Overdue           : {len(overdue)}")

    completion_rate = len(done_all) / max(len(all_tasks), 1) * 100
    print(f"    Completion rate   : {completion_rate:.1f}%")

    print(f"\n  ✅ Completed This Week ({len(completed_this_week)}):")
    if completed_this_week:
        for t in completed_this_week[:8]:
            print(f"    [{t['id']:>3}] {t['title'][:40]}  ({t['completed'][:10]})")
    else:
        print("    None")

    print(f"\n  ⏰ Due Next 7 Days ({len(due_next_week)}):")
    if due_next_week:
        for t in sorted(due_next_week, key=lambda x: x["deadline"]):
            d = days_until(t["deadline"])
            urgency = "TODAY!" if d == 0 else f"in {d}d"
            print(f"    [{t['id']:>3}] {t['title'][:35]}  — {urgency} ({t['deadline']})")
    else:
        print("    Nothing due soon!")

    if overdue:
        print(f"\n  ⚠  Overdue Tasks ({len(overdue)}):")
        for t in overdue:
            d = -days_until(t["deadline"]) if t.get("deadline") else 0
            print(f"    [{t['id']:>3}] {t['title'][:35]}  — {d}d overdue  [{t['priority']}]")

    print(f"\n  🏷  By Priority (pending/in-progress):")
    active = [t for t in all_tasks if t["status"] not in ("done", "cancelled")]
    by_prio = defaultdict(list)
    for t in active:
        by_prio[t["priority"]].append(t)
    for p in ["critical", "high", "medium", "low"]:
        count = len(by_prio[p])
        if count:
            bar = "▇" * min(count, 15)
            print(f"    {PRIORITY_ICON[p]} {p:<10} {count:>3}  {bar}")

    print(f"\n  📂 By Project:")
    by_proj = defaultdict(lambda: {"done": 0, "active": 0})
    for t in all_tasks:
        pid = t.get("project_id")
        if pid and pid in data["projects"]:
            pname = data["projects"][pid]["name"]
            if t["status"] == "done":
                by_proj[pname]["done"] += 1
            else:
                by_proj[pname]["active"] += 1
    for pname, counts in by_proj.items():
        total = counts["done"] + counts["active"]
        pct   = counts["done"] / total * 100 if total else 0
        bar   = "█" * int(pct / 10) + "░" * (10 - int(pct / 10))
        print(f"    {pname:<22} [{bar}] {pct:.0f}%  ({counts['done']}/{total})")

    print(f"\n  {'═'*60}\n")


# ── Seed demo data ─────────────────────────────────────────────────────────────
def seed_demo(data):
    p1 = add_project(data, "Website Redesign",  "New company website",      "🌐")
    p2 = add_project(data, "ML Research",       "Machine learning project", "🤖")
    p3 = add_project(data, "Personal",          "Personal tasks",           "🏠")

    t1 = add_task(data, "Set up dev environment", p1, "high",     str(date.today() + timedelta(days=2)),  ["setup"])
    t2 = add_task(data, "Design UI mockups",       p1, "medium",   str(date.today() + timedelta(days=5)),  ["design"])
    t3 = add_task(data, "Implement login page",    p1, "high",     str(date.today() + timedelta(days=7)),  ["backend", "auth"])
    t4 = add_task(data, "Write unit tests",        p1, "medium",   str(date.today() + timedelta(days=10)), ["testing"])
    t5 = add_task(data, "Collect training data",   p2, "critical", str(date.today() - timedelta(days=2)),  ["data"])
    t6 = add_task(data, "Train baseline model",    p2, "high",     str(date.today() + timedelta(days=14)), ["ml"])
    t7 = add_task(data, "Evaluate model metrics",  p2, "medium",   str(date.today() + timedelta(days=20)), ["ml"])
    t8 = add_task(data, "Buy groceries",           p3, "low",      str(date.today() + timedelta(days=1)),  ["errands"])
    t9 = add_task(data, "Read Python book",        p3, "low",      None,                                   ["learning"])

    # Add subtasks
    add_task(data, "Install Python 3.12", p1, "high", None, ["setup"], parent_id=t1)
    add_task(data, "Configure VSCode",    p1, "high", None, ["setup"], parent_id=t1)
    add_task(data, "Scrape web sources",  p2, "high", None, ["data"],  parent_id=t5)
    add_task(data, "Clean & preprocess",  p2, "high", None, ["data"],  parent_id=t5)

    # Complete some tasks
    complete_task(data, t8)
    update_task(data, t1, status="in_progress")
    update_task(data, t5, status="in_progress")


def interactive(data):
    while True:
        print("\n  ── Menu ──")
        options = [
            "1. List all tasks",      "2. List by priority/status",
            "3. Add task",            "4. Complete task",
            "5. Delete task",         "6. Search tasks",
            "7. List projects",       "8. Add project",
            "9. Weekly report",       "0. Quit",
        ]
        for o in options:
            print(f"  {o}")
        choice = input("  Choice: ").strip()

        if choice == "0":
            break
        elif choice == "1":
            list_tasks(data, title="All Tasks")
        elif choice == "2":
            s = input("  Status (pending/done/in_progress/all): ").strip() or None
            p = input("  Priority (low/medium/high/critical/all): ").strip() or None
            tasks = search_tasks(data, status=s if s != "all" else None,
                                       priority=p if p != "all" else None)
            list_tasks(data, tasks)
        elif choice == "3":
            title    = input("  Title: ").strip()
            priority = input("  Priority (low/medium/high/critical) [medium]: ").strip() or "medium"
            deadline = input("  Deadline (YYYY-MM-DD or blank): ").strip() or None
            tag_str  = input("  Tags (comma-separated, or blank): ").strip()
            tags     = [t.strip() for t in tag_str.split(",") if t.strip()]
            list_projects(data)
            pid      = input("  Project ID (or blank): ").strip() or None
            add_task(data, title, pid, priority, deadline, tags)
        elif choice == "4":
            tid = input("  Task ID to complete: ").strip()
            complete_task(data, tid)
        elif choice == "5":
            tid = input("  Task ID to delete: ").strip()
            delete_task(data, tid)
        elif choice == "6":
            q = input("  Search query: ").strip()
            tasks = search_tasks(data, query=q)
            list_tasks(data, tasks, f"Search: '{q}'")
        elif choice == "7":
            list_projects(data)
        elif choice == "8":
            name = input("  Project name: ").strip()
            desc = input("  Description: ").strip()
            add_project(data, name, desc)
        elif choice == "9":
            weekly_report(data)
        else:
            print("  Invalid choice.")


def main():
    print("╔══════════════════════════════════════════╗")
    print("║   Full-Featured Task Manager v1.0       ║")
    print("╚══════════════════════════════════════════╝")

    data = load_data()

    if not data["projects"]:
        print("\n  Loading demo data...")
        seed_demo(data)

    list_projects(data)
    list_tasks(data, title="All Tasks (sorted by priority + deadline)")
    weekly_report(data)
    interactive(data)

    if os.path.exists(DATA_FILE):
        os.remove(DATA_FILE)
    print("  Goodbye! Stay productive.")


if __name__ == "__main__":
    main()
