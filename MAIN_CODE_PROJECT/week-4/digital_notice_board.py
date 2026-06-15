# Digital Notice Board with Scheduled Announcements

from datetime import date, timedelta

notices  = {}
archived = {}
_nid = 1

CATEGORIES = ["Academic","Administrative","Event","Emergency","General","Sports"]

def post_notice(title, content, category, author, start_date=None, end_date=None):
    global _nid
    if category not in CATEGORIES:
        print(f"  Invalid category. Options: {CATEGORIES}"); return None
    nid   = f"NOT{_nid:05d}"; _nid += 1
    start = start_date or date.today()
    end   = end_date   or (start + timedelta(days=7))
    notices[nid] = {
        "title":title, "content":content, "category":category,
        "author":author, "start":start, "end":end,
        "pinned":False, "views":0, "posted_on":date.today()
    }
    status = "Scheduled" if start > date.today() else "Active"
    print(f"  [{nid}] {title[:40]} | {category} | {start} → {end} | {status}")
    return nid

def pin_notice(nid):
    if nid not in notices: print("  Notice not found."); return
    notices[nid]["pinned"] = True
    print(f"  [{nid}] '{notices[nid]['title']}' pinned.")

def view_notice(nid):
    if nid not in notices and nid not in archived:
        print("  Notice not found."); return
    n = notices.get(nid) or archived.get(nid)
    if nid in notices: notices[nid]["views"] += 1
    today = date.today()
    status = "Archived" if nid in archived else ("Active" if n["start"] <= today <= n["end"] else "Scheduled")
    print(f"\n{'='*52}")
    print(f"  [{nid}] {'📌 ' if n['pinned'] else ''}{n['title']}")
    print(f"  Category : {n['category']}  |  Author: {n['author']}")
    print(f"  Valid    : {n['start']} to {n['end']}  |  Status: {status}")
    print(f"  Views    : {n['views']}")
    print(f"\n  {n['content']}")
    print(f"{'='*52}")

def display_active_notices(ref_date=None):
    today = ref_date or date.today()
    active = {nid:n for nid,n in notices.items() if n["start"] <= today <= n["end"]}
    pinned = {nid:n for nid,n in active.items() if n["pinned"]}
    normal = {nid:n for nid,n in active.items() if not n["pinned"]}
    print(f"\n{'='*52}\n  NOTICE BOARD  ({today})\n{'='*52}")
    if pinned:
        print("  📌 PINNED NOTICES:")
        for nid, n in pinned.items():
            print(f"  [{nid}] {n['title']:<40} [{n['category']}]")
    print("\n  ACTIVE NOTICES:")
    if not normal:
        print("  (None)")
    for nid, n in sorted(normal.items(), key=lambda x: -x[1]["start"].toordinal()):
        print(f"  [{nid}] {n['title']:<40} [{n['category']}]  Expires: {n['end']}")
    upcoming = {nid:n for nid,n in notices.items() if n["start"] > today}
    if upcoming:
        print(f"\n  UPCOMING ({len(upcoming)}):")
        for nid, n in sorted(upcoming.items(), key=lambda x: x[1]["start"]):
            print(f"  [{nid}] {n['title']:<40} Starts: {n['start']}")
    print(f"{'='*52}")

def archive_expired(ref_date=None):
    today = ref_date or date.today()
    expired_ids = [nid for nid,n in notices.items() if n["end"] < today]
    for nid in expired_ids:
        archived[nid] = notices.pop(nid)
        print(f"  [{nid}] '{archived[nid]['title']}' archived.")
    if not expired_ids: print("  No notices to archive.")
    return len(expired_ids)

def search_notices(keyword, search_archived=False):
    kw = keyword.lower()
    pool = {**notices, **(archived if search_archived else {})}
    results = [(nid, n) for nid,n in pool.items()
               if kw in n["title"].lower() or kw in n["content"].lower()]
    print(f"\n  Search '{keyword}': {len(results)} result(s)")
    for nid, n in results:
        loc = "Archive" if nid in archived else "Board"
        print(f"  [{nid}] [{loc}] {n['title']}")

def notice_stats():
    print(f"\n{'='*50}\n  NOTICE BOARD STATISTICS\n{'='*50}")
    today = date.today()
    active = sum(1 for n in notices.values() if n["start"] <= today <= n["end"])
    sched  = sum(1 for n in notices.values() if n["start"] > today)
    total_views = sum(n["views"] for n in {**notices,**archived}.values())
    cat_counts  = {}
    for n in {**notices,**archived}.values():
        cat_counts[n["category"]] = cat_counts.get(n["category"],0) + 1
    print(f"  Active   : {active}  Scheduled: {sched}  Archived: {len(archived)}")
    print(f"  Total Views: {total_views}")
    print("  By Category:")
    for cat, cnt in sorted(cat_counts.items(), key=lambda x: -x[1]):
        print(f"    {cat:<18}: {cnt}")
    print(f"{'='*50}")

def main():
    print("=== Digital Notice Board ===")
    today = date.today()
    n1 = post_notice("Semester Exam Schedule",
                     "End semester exams start from Dec 1. Check timetable on portal.",
                     "Academic","Principal", today, today+timedelta(days=14))
    n2 = post_notice("Annual Sports Day",
                     "Annual sports day on Nov 30. Register at sports office by Nov 25.",
                     "Sports","Sports Dept", today, today+timedelta(days=10))
    n3 = post_notice("Library Closed for Maintenance",
                     "Library will remain closed on Nov 28-29 for annual maintenance.",
                     "Administrative","Librarian", today+timedelta(days=2), today+timedelta(days=4))
    n4 = post_notice("Fire Drill Notice",
                     "Mandatory fire drill on Nov 27 at 10 AM. All to assemble at ground.",
                     "Emergency","Safety Officer", today, today+timedelta(days=3))
    n5 = post_notice("Old Notice — Expired",
                     "This notice has expired already.",
                     "General","Admin", today-timedelta(days=10), today-timedelta(days=2))
    pin_notice(n1); pin_notice(n4)
    display_active_notices(today)
    view_notice(n1); view_notice(n1)
    archive_expired(today)
    search_notices("exam")
    notice_stats()

if __name__ == "__main__":
    main()
