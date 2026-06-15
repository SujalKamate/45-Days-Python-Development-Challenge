# Public Transport Pass Management System

from datetime import date, timedelta

PASS_TYPES = {
    "Monthly":   {"days": 30,  "price": 600,  "discount": 0.10},
    "Quarterly": {"days": 90,  "price": 1600, "discount": 0.15},
    "Annual":    {"days": 365, "price": 5500, "discount": 0.25},
}
ZONES = {"A": 1.0, "B": 0.85, "C": 0.70}
BASE_FARE = 25
passes = {}
_pid = 1

def issue_pass(passenger_name, pass_type, zone, issue_date=None):
    global _pid
    if pass_type not in PASS_TYPES:
        print(f"  Invalid pass type. Options: {list(PASS_TYPES.keys())}")
        return None
    if zone not in ZONES:
        print(f"  Invalid zone. Options: {list(ZONES.keys())}")
        return None
    issue = issue_date or date.today()
    info  = PASS_TYPES[pass_type]
    expiry = issue + timedelta(days=info["days"])
    price  = round(info["price"] * ZONES[zone], 2)
    pid = f"PAS{_pid:05d}"
    _pid += 1
    passes[pid] = {
        "passenger": passenger_name, "type": pass_type,
        "zone": zone, "issue_date": issue, "expiry_date": expiry,
        "price": price, "discount": info["discount"],
        "trips_used": 0, "active": True
    }
    print(f"  [{pid}] {passenger_name} | {pass_type} | Zone {zone} | Rs.{price} | Expires: {expiry}")
    return pid

def validate_pass(pid, check_date=None):
    if pid not in passes:
        print("  Pass not found.")
        return False
    p = passes[pid]
    ref = check_date or date.today()
    if not p["active"]:
        print(f"  [{pid}] Pass is deactivated.")
        return False
    if p["expiry_date"] < ref:
        p["active"] = False
        print(f"  [{pid}] Pass EXPIRED on {p['expiry_date']}.")
        return False
    days_left = (p["expiry_date"] - ref).days
    p["trips_used"] += 1
    print(f"  [{pid}] Valid ✔ | {p['passenger']} | Zone {p['zone']} | {days_left} day(s) left | Trip #{p['trips_used']}")
    return True

def calculate_fare(zone, pass_type=None):
    base = BASE_FARE * ZONES.get(zone, 1.0)
    if pass_type and pass_type in PASS_TYPES:
        discount = PASS_TYPES[pass_type]["discount"]
        discounted = round(base * (1 - discount), 2)
        print(f"  Zone {zone} Fare: Rs.{base:.2f} | With {pass_type} discount: Rs.{discounted:.2f}")
        return discounted
    print(f"  Zone {zone} Fare (no pass): Rs.{base:.2f}")
    return round(base, 2)

def renew_pass(pid):
    if pid not in passes:
        print("  Pass not found.")
        return
    p = passes[pid]
    info = PASS_TYPES[p["type"]]
    today = date.today()
    base = max(today, p["expiry_date"])
    p["expiry_date"] = base + timedelta(days=info["days"])
    p["active"] = True
    price = round(info["price"] * ZONES[p["zone"]], 2)
    print(f"  [{pid}] Renewed | {p['passenger']} | New Expiry: {p['expiry_date']} | Rs.{price}")

def passenger_pass_records():
    print(f"\n{'='*60}")
    print("  PASSENGER PASS RECORDS")
    print(f"{'='*60}")
    today = date.today()
    for pid, p in passes.items():
        days_left = (p["expiry_date"] - today).days
        status = "Active" if p["active"] and days_left >= 0 else "Expired"
        alert  = " ⚠RENEW" if 0 <= days_left <= 7 and p["active"] else ""
        print(f"  {pid} | {p['passenger']:<18} | {p['type']:<10} | Zone {p['zone']} | "
              f"Exp: {p['expiry_date']} | Trips: {p['trips_used']:>3} | {status}{alert}")
    active_count   = sum(1 for p in passes.values() if p["active"])
    total_revenue  = sum(p["price"] for p in passes.values())
    print(f"\n  Total Passes  : {len(passes)}")
    print(f"  Active        : {active_count}")
    print(f"  Total Revenue : Rs.{total_revenue:.2f}")
    print(f"{'='*60}")

def main():
    print("=== Public Transport Pass Management System ===")
    today = date.today()
    p1 = issue_pass("Amit Kumar",   "Monthly",   "A")
    p2 = issue_pass("Priya Nair",   "Quarterly", "B")
    p3 = issue_pass("Rahul Sharma", "Annual",    "A")
    p4 = issue_pass("Sunita Rao",   "Monthly",   "C", today - timedelta(days=28))
    p5 = issue_pass("Kiran Das",    "Monthly",   "B", today - timedelta(days=32))
    print("\n--- Validating Passes ---")
    validate_pass(p1); validate_pass(p1)
    validate_pass(p4)
    validate_pass(p5)
    print("\n--- Fare Calculation ---")
    calculate_fare("A", "Annual")
    calculate_fare("B", "Monthly")
    calculate_fare("C")
    print("\n--- Renewing Expired Pass ---")
    renew_pass(p5)
    passenger_pass_records()

if __name__ == "__main__":
    main()
