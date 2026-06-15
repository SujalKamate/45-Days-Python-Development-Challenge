# School Fee Collection System with Payment History

from datetime import date

FEE_STRUCTURE = {
    "Grade 1-5":  {"Tuition": 3000, "Lab": 500,  "Sports": 300, "Library": 200},
    "Grade 6-8":  {"Tuition": 4000, "Lab": 700,  "Sports": 400, "Library": 250},
    "Grade 9-10": {"Tuition": 5000, "Lab": 1000, "Sports": 500, "Library": 300},
    "Grade 11-12":{"Tuition": 6000, "Lab": 1200, "Sports": 500, "Library": 350},
}
students = {}
payments = []
_sid = _rid = 1

def enroll_student(name, grade_group, parent_name, contact):
    global _sid
    if grade_group not in FEE_STRUCTURE:
        print(f"  Invalid grade group."); return None
    sid = f"STU{_sid:04d}"; _sid += 1
    annual_fee = sum(FEE_STRUCTURE[grade_group].values()) * 12
    students[sid] = {"name": name, "grade_group": grade_group, "parent": parent_name,
                     "contact": contact, "total_due": annual_fee, "total_paid": 0, "payment_ids": []}
    print(f"  [{sid}] {name} | {grade_group} | Annual Fee: Rs.{annual_fee:,}")
    return sid

def record_payment(sid, amount, fee_heads, mode="Cash", pay_date=None):
    global _rid
    if sid not in students: print("  Student not found."); return None
    s = students[sid]; d = pay_date or date.today()
    rid = f"RCP{_rid:05d}"; _rid += 1
    s["total_paid"] += amount; s["payment_ids"].append(rid)
    payments.append({"receipt_id": rid, "sid": sid, "name": s["name"],
                     "amount": amount, "fee_heads": fee_heads, "mode": mode, "date": d})
    balance = s["total_due"] - s["total_paid"]
    print(f"  [{rid}] {s['name']} | Rs.{amount} | {mode} | Balance: Rs.{balance:,}")
    return rid

def print_receipt(rid):
    rec = next((p for p in payments if p["receipt_id"] == rid), None)
    if not rec: print("  Receipt not found."); return
    s = students[rec["sid"]]
    print(f"\n{'='*44}\n  OFFICIAL FEE RECEIPT   Receipt: {rid}")
    print(f"  Student : {rec['name']}  |  Parent: {s['parent']}")
    print(f"  Grade   : {s['grade_group']}  |  Date: {rec['date']}")
    for head, amt in rec["fee_heads"].items():
        print(f"  {head:<18} Rs.{amt:,}")
    print(f"  {'TOTAL PAID':<18} Rs.{rec['amount']:,}  ({rec['mode']})")
    print(f"  Outstanding: Rs.{s['total_due']-s['total_paid']:,}\n{'='*44}")

def student_ledger(sid):
    if sid not in students: print("  Not found."); return
    s = students[sid]
    s_pmts = [p for p in payments if p["sid"] == sid]
    print(f"\n  Ledger: {s['name']} [{sid}]")
    print(f"  Annual: Rs.{s['total_due']:,} | Paid: Rs.{s['total_paid']:,} | Due: Rs.{s['total_due']-s['total_paid']:,}")
    for p in s_pmts:
        print(f"    [{p['receipt_id']}] {p['date']}  Rs.{p['amount']:,}  {p['mode']}")

def defaulters_list():
    print("\n--- Outstanding Fee Defaulters ---")
    for sid, s in sorted(students.items(), key=lambda x: -(x[1]["total_due"]-x[1]["total_paid"])):
        outstanding = s["total_due"] - s["total_paid"]
        if outstanding > 0:
            pct = s["total_paid"] / s["total_due"] * 100
            print(f"  [{sid}] {s['name']:<20} Due: Rs.{outstanding:,} | Paid: {pct:.0f}%")

def collection_report():
    total_due  = sum(s["total_due"]  for s in students.values())
    total_paid = sum(s["total_paid"] for s in students.values())
    mode_totals = {}
    for p in payments:
        mode_totals[p["mode"]] = mode_totals.get(p["mode"], 0) + p["amount"]
    print(f"\n{'='*48}\n  FEE COLLECTION REPORT\n{'='*48}")
    print(f"  Students: {len(students)} | Collected: Rs.{total_paid:,} / Rs.{total_due:,}")
    print(f"  Rate    : {total_paid/total_due*100:.1f}% | Outstanding: Rs.{total_due-total_paid:,}")
    print("  Payment Modes:")
    for mode, amt in mode_totals.items():
        print(f"    {mode:<12}: Rs.{amt:,}")
    print(f"{'='*48}")

def main():
    print("=== School Fee Collection System ===")
    s1 = enroll_student("Aarav Mehta",  "Grade 6-8",   "Suresh Mehta", "9876543210")
    s2 = enroll_student("Bhavna Rao",   "Grade 9-10",  "Ravi Rao",     "9123456789")
    s3 = enroll_student("Chetan Singh", "Grade 11-12", "Harish Singh", "9011223344")
    s4 = enroll_student("Divya Nair",   "Grade 1-5",   "Priya Nair",   "9988776655")
    r1 = record_payment(s1, 5400, {"Tuition":4000,"Lab":700,"Sports":400,"Library":300}, "Online")
    r2 = record_payment(s2, 6800, {"Tuition":5000,"Lab":1000,"Sports":500,"Library":300}, "Cheque")
    r3 = record_payment(s3, 6000, {"Tuition":6000}, "Cash")
    r4 = record_payment(s4, 4000, {"Tuition":3000,"Lab":500,"Sports":300,"Library":200}, "UPI")
    r5 = record_payment(s3, 2050, {"Lab":1200,"Sports":500,"Library":350}, "UPI")
    print_receipt(r1)
    student_ledger(s2)
    defaulters_list()
    collection_report()

if __name__ == "__main__":
    main()
