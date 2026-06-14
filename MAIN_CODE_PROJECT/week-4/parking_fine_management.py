# Parking Fine Management System with Violation Reports

from datetime import date

VIOLATION_TYPES = {
    "No Parking Zone":      1500,
    "Double Parking":       1000,
    "Expired Meter":         500,
    "Blocking Driveway":    2000,
    "Disabled Bay Misuse":  3000,
    "Wrong Direction":       800,
    "Obstructing Traffic":  2500,
}
violations = {}
_vid = 1

def record_violation(vehicle_no, owner_name, violation_type, location, officer, vio_date=None):
    global _vid
    if violation_type not in VIOLATION_TYPES:
        print(f"  Unknown violation. Options: {list(VIOLATION_TYPES.keys())}"); return None
    vid  = f"VIO{_vid:05d}"; _vid += 1
    d    = vio_date or date.today()
    fine = VIOLATION_TYPES[violation_type]
    violations[vid] = {
        "vehicle":vehicle_no, "owner":owner_name, "type":violation_type,
        "location":location, "officer":officer, "date":d,
        "fine":fine, "paid":False, "payment_date":None, "disputed":False
    }
    print(f"  [{vid}] {vehicle_no} | {violation_type} | Rs.{fine} | {location}")
    return vid

def pay_fine(vid, pay_date=None):
    if vid not in violations: print("  Violation not found."); return False
    v = violations[vid]
    if v["paid"]: print(f"  [{vid}] Already paid."); return False
    if v["disputed"]: print(f"  [{vid}] Under dispute — cannot pay now."); return False
    v["paid"] = True
    v["payment_date"] = pay_date or date.today()
    print(f"  [{vid}] Fine of Rs.{v['fine']} paid by {v['owner']} on {v['payment_date']}")
    return True

def dispute_violation(vid, reason):
    if vid not in violations: print("  Not found."); return
    v = violations[vid]
    if v["paid"]: print("  Already paid — cannot dispute."); return
    v["disputed"] = True
    print(f"  [{vid}] Dispute filed: {reason}")

def resolve_dispute(vid, outcome="upheld"):
    if vid not in violations: return
    v = violations[vid]
    if not v["disputed"]: print("  No dispute on this violation."); return
    v["disputed"] = False
    if outcome == "dismissed":
        v["fine"]  = 0
        v["paid"]  = True
        print(f"  [{vid}] Dispute DISMISSED — fine waived.")
    else:
        print(f"  [{vid}] Dispute UPHELD — original fine Rs.{v['fine']} stands.")

def vehicle_history(vehicle_no):
    v_violations = [(vid, v) for vid, v in violations.items() if v["vehicle"] == vehicle_no]
    print(f"\n  Violation History: {vehicle_no}")
    if not v_violations: print("  No violations found."); return
    total = sum(v["fine"] for _, v in v_violations)
    paid  = sum(v["fine"] for _, v in v_violations if v["paid"])
    for vid, v in sorted(v_violations, key=lambda x: x[1]["date"]):
        status = "Paid" if v["paid"] else ("Disputed" if v["disputed"] else "Unpaid")
        print(f"  [{vid}] {v['date']} | {v['type']:<25} Rs.{v['fine']:,} | {status}")
    print(f"  Total Fines: Rs.{total:,} | Paid: Rs.{paid:,} | Due: Rs.{total-paid:,}")

def officer_report(officer_name):
    o_violations = [(vid, v) for vid, v in violations.items() if v["officer"] == officer_name]
    total_fines  = sum(v["fine"] for _, v in o_violations)
    print(f"\n  Officer Report: {officer_name}")
    print(f"  Violations issued: {len(o_violations)} | Total fines: Rs.{total_fines:,}")
    type_count = {}
    for _, v in o_violations:
        type_count[v["type"]] = type_count.get(v["type"], 0) + 1
    for vtype, cnt in sorted(type_count.items(), key=lambda x: -x[1]):
        print(f"    {vtype:<30}: {cnt}")

def enforcement_report():
    print(f"\n{'='*54}\n  PARKING ENFORCEMENT REPORT\n{'='*54}")
    total_fines  = sum(v["fine"]  for v in violations.values())
    total_paid   = sum(v["fine"]  for v in violations.values() if v["paid"])
    total_unpaid = total_fines - total_paid
    disputed     = sum(1 for v in violations.values() if v["disputed"])
    print(f"  Total Violations : {len(violations)}")
    print(f"  Total Fines      : Rs.{total_fines:,}")
    print(f"  Collected        : Rs.{total_paid:,}")
    print(f"  Outstanding      : Rs.{total_unpaid:,}")
    print(f"  Disputed         : {disputed}")
    vtype_totals = {}
    for v in violations.values():
        vtype_totals[v["type"]] = vtype_totals.get(v["type"],0) + 1
    print("\n  By Violation Type:")
    for vtype, cnt in sorted(vtype_totals.items(), key=lambda x: -x[1]):
        fine = VIOLATION_TYPES[vtype]
        print(f"  {vtype:<30}: {cnt:>3} cases | Fine: Rs.{fine:,}")
    print(f"{'='*54}")

def main():
    print("=== Parking Fine Management System ===")
    today = date.today()
    v1 = record_violation("DL05AB1234","Rohit Sharma",  "No Parking Zone",    "MG Road Sector 4",  "Off. Gupta")
    v2 = record_violation("MH12CD5678","Priya Nair",    "Double Parking",     "Central Market",    "Off. Sharma")
    v3 = record_violation("KA03EF9012","Amit Kumar",    "Disabled Bay Misuse","City Hospital",     "Off. Gupta")
    v4 = record_violation("UP32GH3456","Sunita Rao",    "Expired Meter",      "Railway Station",   "Off. Verma")
    v5 = record_violation("TN22IJ7890","Kiran Das",     "Blocking Driveway",  "Shivaji Nagar",     "Off. Sharma")
    v6 = record_violation("GJ07KL2345","Meera Iyer",    "Wrong Direction",    "Ring Road",         "Off. Gupta")
    pay_fine(v1); pay_fine(v2); pay_fine(v4)
    dispute_violation(v3, "Disabled permit displayed — officer missed it")
    resolve_dispute(v3, outcome="dismissed")
    vehicle_history("DL05AB1234")
    officer_report("Off. Gupta")
    enforcement_report()

if __name__ == "__main__":
    main()
