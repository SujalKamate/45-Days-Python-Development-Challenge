"""
Full-Featured Command-Line Argument Parser with Subcommands and Help Docs
Uses argparse to build a task-management CLI with add/remove/list subcommands.
"""

import argparse
import json
import os
import sys
from datetime import datetime

DATA_FILE = "cli_tasks.json"


# ── Data layer ────────────────────────────────────────────────────────────────
def load_tasks():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return []


def save_tasks(tasks):
    with open(DATA_FILE, "w") as f:
        json.dump(tasks, f, indent=2)


def next_id(tasks):
    return max((t["id"] for t in tasks), default=0) + 1


# ── Subcommand handlers ───────────────────────────────────────────────────────
def cmd_add(args):
    tasks = load_tasks()
    task = {
        "id":       next_id(tasks),
        "title":    args.title,
        "priority": args.priority,
        "tags":     args.tags or [],
        "due":      args.due or "",
        "status":   "pending",
        "created":  datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    tasks.append(task)
    save_tasks(tasks)
    tags_str = ", ".join(task["tags"]) if task["tags"] else "none"
    print(f"  ✓ Added task #{task['id']}: '{task['title']}' "
          f"[priority={task['priority']}, tags={tags_str}]")


def cmd_list(args):
    tasks = load_tasks()
    if not tasks:
        print("  No tasks found."); return

    # Filter
    if args.status:
        tasks = [t for t in tasks if t["status"] == args.status]
    if args.priority:
        tasks = [t for t in tasks if t["priority"] == args.priority]
    if args.tag:
        tasks = [t for t in tasks if args.tag in t.get("tags", [])]

    if not tasks:
        print("  No tasks match the filters."); return

    # Sort
    sort_key = args.sort or "id"
    reverse = args.desc
    try:
        tasks.sort(key=lambda t: t.get(sort_key, ""), reverse=reverse)
    except Exception:
        pass

    # Output
    if args.json:
        print(json.dumps(tasks, indent=2))
        return

    priority_icons = {"high": "🔴", "medium": "🟡", "low": "🟢"}
    status_icons   = {"pending": "○", "done": "✓", "cancelled": "✗"}

    print(f"\n  {'─'*70}")
    print(f"  {'ID':>4}  {'S':>2}  {'P':>2}  {'Title':<30}  {'Due':<12}  {'Tags'}")
    print(f"  {'─'*70}")
    for t in tasks:
        s   = status_icons.get(t["status"], "?")
        p   = priority_icons.get(t["priority"], "·")
        tags = ", ".join(t.get("tags", []))[:15]
        due  = t.get("due", "")[:10]
        print(f"  {t['id']:>4}  {s:>2}  {p:>2}  {t['title'][:30]:<30}  {due:<12}  {tags}")
    print(f"  {'─'*70}")
    print(f"  Total: {len(tasks)} task(s)")


def cmd_done(args):
    tasks = load_tasks()
    updated = 0
    for t in tasks:
        if t["id"] in args.ids:
            t["status"] = "done"
            t["completed"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            updated += 1
            print(f"  ✓ Task #{t['id']} '{t['title']}' marked done.")
    if updated == 0:
        print(f"  ✗ No matching task IDs: {args.ids}")
    save_tasks(tasks)


def cmd_remove(args):
    tasks = load_tasks()
    before = len(tasks)
    tasks = [t for t in tasks if t["id"] not in args.ids]
    removed = before - len(tasks)
    save_tasks(tasks)
    print(f"  ✓ Removed {removed} task(s).")


def cmd_edit(args):
    tasks = load_tasks()
    for t in tasks:
        if t["id"] == args.id:
            if args.title:    t["title"]    = args.title
            if args.priority: t["priority"] = args.priority
            if args.due:      t["due"]      = args.due
            if args.tags:     t["tags"]     = args.tags
            t["updated"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            save_tasks(tasks)
            print(f"  ✓ Task #{t['id']} updated.")
            return
    print(f"  ✗ Task #{args.id} not found.")


def cmd_stats(args):
    tasks = load_tasks()
    if not tasks:
        print("  No tasks."); return
    from collections import Counter
    status_count   = Counter(t["status"]   for t in tasks)
    priority_count = Counter(t["priority"] for t in tasks)

    print(f"\n  Task Statistics ({len(tasks)} total)")
    print(f"  {'─'*30}")
    print(f"  By Status:")
    for k, v in status_count.items():
        bar = "▇" * v
        print(f"    {k:<12}: {v:>3}  {bar}")
    print(f"  By Priority:")
    for k, v in priority_count.items():
        bar = "▇" * v
        print(f"    {k:<12}: {v:>3}  {bar}")

    all_tags = []
    for t in tasks:
        all_tags.extend(t.get("tags", []))
    if all_tags:
        tag_count = Counter(all_tags)
        print(f"  Top Tags: {dict(tag_count.most_common(5))}")


def cmd_clear(args):
    if args.confirm:
        save_tasks([])
        print("  ✓ All tasks cleared.")
    else:
        print("  Use --confirm to actually clear all tasks.")


# ── Parser builder ────────────────────────────────────────────────────────────
def build_parser():
    parser = argparse.ArgumentParser(
        prog="taskman",
        description="Full-featured CLI Task Manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  taskman add "Buy groceries" --priority high --tags shopping,personal
  taskman list --status pending --sort priority
  taskman done 1 3 5
  taskman edit 2 --title "Updated title" --due 2024-12-01
  taskman remove 4
  taskman stats
  taskman clear --confirm
        """
    )

    parser.add_argument("--version", action="version", version="%(prog)s 1.0.0")
    parser.add_argument("--data-file", default=DATA_FILE,
                        help="Path to JSON data file")

    sub = parser.add_subparsers(dest="command", title="subcommands")
    sub.required = True

    # add
    p_add = sub.add_parser("add", help="Add a new task")
    p_add.add_argument("title", help="Task title")
    p_add.add_argument("-p", "--priority", choices=["high", "medium", "low"],
                       default="medium", help="Task priority (default: medium)")
    p_add.add_argument("-t", "--tags", nargs="+", metavar="TAG", help="Tags")
    p_add.add_argument("-d", "--due", metavar="DATE", help="Due date (YYYY-MM-DD)")
    p_add.set_defaults(func=cmd_add)

    # list
    p_list = sub.add_parser("list", aliases=["ls"], help="List tasks")
    p_list.add_argument("--status",   choices=["pending", "done", "cancelled"], help="Filter by status")
    p_list.add_argument("--priority", choices=["high", "medium", "low"],        help="Filter by priority")
    p_list.add_argument("--tag",      help="Filter by tag")
    p_list.add_argument("--sort",     choices=["id", "priority", "due", "title"], help="Sort field")
    p_list.add_argument("--desc",     action="store_true", help="Sort descending")
    p_list.add_argument("--json",     action="store_true", help="Output as JSON")
    p_list.set_defaults(func=cmd_list)

    # done
    p_done = sub.add_parser("done", help="Mark tasks as done")
    p_done.add_argument("ids", nargs="+", type=int, metavar="ID", help="Task IDs")
    p_done.set_defaults(func=cmd_done)

    # remove
    p_rm = sub.add_parser("remove", aliases=["rm", "delete"], help="Remove tasks")
    p_rm.add_argument("ids", nargs="+", type=int, metavar="ID", help="Task IDs")
    p_rm.set_defaults(func=cmd_remove)

    # edit
    p_edit = sub.add_parser("edit", help="Edit an existing task")
    p_edit.add_argument("id", type=int, help="Task ID to edit")
    p_edit.add_argument("-t", "--title",    help="New title")
    p_edit.add_argument("-p", "--priority", choices=["high", "medium", "low"])
    p_edit.add_argument("-d", "--due",      metavar="DATE")
    p_edit.add_argument("--tags",           nargs="+", metavar="TAG")
    p_edit.set_defaults(func=cmd_edit)

    # stats
    p_stat = sub.add_parser("stats", help="Show task statistics")
    p_stat.set_defaults(func=cmd_stats)

    # clear
    p_clr = sub.add_parser("clear", help="Remove all tasks")
    p_clr.add_argument("--confirm", action="store_true", help="Confirm deletion")
    p_clr.set_defaults(func=cmd_clear)

    return parser


def simulate(argv):
    parser = build_parser()
    print(f"\n  $ taskman {' '.join(argv)}")
    print(f"  {'─'*50}")
    try:
        args = parser.parse_args(argv)
        args.func(args)
    except SystemExit:
        pass


def main():
    print("╔══════════════════════════════════════════╗")
    print("║   CLI Task Manager (argparse) v1.0      ║")
    print("╚══════════════════════════════════════════╝")

    print("\n  Running demo commands...\n")

    demo_commands = [
        ["add", "Buy groceries",        "--priority", "high",   "--tags", "shopping", "--due", "2024-12-01"],
        ["add", "Finish Python project","--priority", "high",   "--tags", "coding",   "work"],
        ["add", "Read clean code book", "--priority", "medium", "--tags", "reading"],
        ["add", "Morning workout",      "--priority", "low",    "--tags", "health"],
        ["add", "Write unit tests",     "--priority", "high",   "--tags", "coding",   "work"],
        ["list"],
        ["list", "--priority", "high"],
        ["list", "--tag", "coding"],
        ["list", "--sort", "priority"],
        ["done", "1", "3"],
        ["list", "--status", "pending"],
        ["edit", "2", "--title", "Complete Python project", "--priority", "high"],
        ["stats"],
        ["remove", "4"],
        ["list"],
    ]

    for cmd in demo_commands:
        simulate(cmd)

    print("\n  ── Interactive Mode ──")
    print("  Type argparse-style commands or 'help' / 'quit'")
    parser = build_parser()
    while True:
        try:
            raw = input("\n  taskman> ").strip()
            if not raw or raw == "quit":
                break
            if raw == "help":
                parser.print_help()
                continue
            parts = raw.split()
            args = parser.parse_args(parts)
            args.func(args)
        except SystemExit:
            pass
        except KeyboardInterrupt:
            break

    if os.path.exists(DATA_FILE):
        os.remove(DATA_FILE)
    print("\n  Goodbye!")


if __name__ == "__main__":
    main()
