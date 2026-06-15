# Gym Membership Management System with Renewal Alerts

from datetime import date, timedelta

PLANS = {
    "Basic":    {"days": 30,  "price": 500},
    "Standard": {"days": 90,  "price": 1300},
    "Premium":  {"days": 365, "price": 4500},
}
ALERT_THRESHOLD = 7
members = {}
_mid = 1

def register_member(name, plan, join_date=None):
    global _mid
    if plan not in PLANS:
        print(f"  Plan '{plan}' not available.")
        return None
    join = join_date or date.today()
    expiry = join + timedelta(days=PLANS[plan]["days"])
    mid = f"GYM{_mid:04d}"
    _mid += 1
    members[mid] = {
        "name": name, "plan": plan,
        "join": join, "expiry": expiry, "active": True,
        "renewals": 0
    }
    print(f"  [{mid}] {name} | Plan: {plan} | Joined: {join} | Expires: {expiry}")
    return mid

def check_renewals(ref_date=None):
    ref = ref_date or date.today()
    print(f"\n--- Renewal Alerts (next {ALERT_THRESHOLD} days from {ref}) ---")
    found = False
    for mid, m in members.items():
        days_left = (m["expiry"] - ref).days
        if m["active"] and 0 <= days_left <= ALERT_THRESHOLD:
            print(f"  ⚠ [{mid}] {m['name']} — expires in {days_left} day(s) on {m['expiry']}")
            found = True
    if not found:
        print("  No upcoming renewals in alert window.")

def check_expired(ref_date=None):
    ref = ref_date or date.today()
    print(f"\n--- Expired Memberships (as of {ref}) ---")
    found = False
    for mid, m in members.items():
        if m["active"] and m["expiry"] < ref:
            m["active"] = False
            print(f"  [EXPIRED] [{mid}] {m['name']} — expired on {m['expiry']}")
            found = True
    if not found:
        print("  No expired memberships found.")

def renew_membership(mid, new_plan=None):
    if mid not in members:
        print("  Member not found.")
        return
    m = members[mid]
    plan = new_plan or m["plan"]
    if plan not in PLANS:
        print("  Invalid plan.")
        return
    today = date.today()
    base = max(today, m["expiry"])
    m["expiry"] = base + timedelta(days=PLANS[plan]["days"])
    m["plan"] = plan
    m["active"] = True
    m["renewals"] += 1
    print(f"  [{mid}] {m['name']} renewed | Plan: {plan} | New Expiry: {m['expiry']} | Total Renewals: {m['renewals']}")

def generate_report():
    print(f"\n{'='*45}")
    print("  GYM MEMBERSHIP REPORT")
    print(f"{'='*45}")
    active_count = sum(1 for m in members.values() if m["active"])
    plan_totals = {p: 0 for p in PLANS}
    revenue = 0
    for m in members.values():
        plan_totals[m["plan"]] += 1
        revenue += PLANS[m["plan"]]["price"] * (m["renewals"] + 1)
    print(f"  Total Members  : {len(members)}")
    print(f"  Active         : {active_count}")
    print(f"  Inactive       : {len(members) - active_count}")
    print(f"  Est. Revenue   : Rs.{revenue}")
    print("\n  Plan Breakdown:")
    for plan, count in plan_totals.items():
        print(f"    {plan:<10}: {count} member(s)  Rs.{PLANS[plan]['price']}/cycle")
    print(f"{'='*45}")

def list_members():
    print("\n--- Member List ---")
    for mid, m in members.items():
        status = "✔ Active" if m["active"] else "✘ Inactive"
        print(f"  {mid} | {m['name']:<20} | {m['plan']:<10} | Exp: {m['expiry']} | {status}")

def main():
    print("=== Gym Membership Management System ===")
    today = date.today()
    register_member("Arjun Kapoor",  "Basic",    today - timedelta(days=25))
    register_member("Divya Mehta",   "Standard", today - timedelta(days=5))
    register_member("Rakesh Nair",   "Premium",  today - timedelta(days=360))
    register_member("Sunita Rao",    "Basic",    today - timedelta(days=28))
    register_member("Kiran Sharma",  "Standard")
    list_members()
    check_renewals(today)
    check_expired(today)
    print("\n--- Renewing GYM0001 to Standard ---")
    renew_membership("GYM0001", "Standard")
    generate_report()

if __name__ == "__main__":
    main()
