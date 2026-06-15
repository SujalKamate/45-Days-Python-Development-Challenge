# Employee Leave Management System with Approval Workflow

from datetime import date, timedelta

LEAVE_QUOTA = {"Casual": 12, "Sick": 10, "Earned": 15}

employees = {}
leave_requests = {}
_eid = 1
_lid = 1

def add_employee(name, department):
    global _eid
    eid = f"EMP{_eid:04d}"
    _eid += 1
    employees[eid] = {
        "name": name, "department": department,
        "balance": dict(LEAVE_QUOTA),
        "approved_days": 0
    }
    print(f"  [{eid}] {name} — {department} | Leave: {LEAVE_QUOTA}")
    return eid

def submit_leave(eid, leave_type, start_str, end_str, reason):
    global _lid
    if eid not in employees:
        print("  Employee not found.")
        return None
    if leave_type not in LEAVE_QUOTA:
        print(f"  Invalid leave type. Choose from {list(LEAVE_QUOTA.keys())}")
        return None
    start = date.fromisoformat(start_str)
    end   = date.fromisoformat(end_str)
    days  = (end - start).days + 1
    if days <= 0:
        print("  End date must be after start date.")
        return None
    if employees[eid]["balance"][leave_type] < days:
        print(f"  Insufficient {leave_type} leave balance (available: {employees[eid]['balance'][leave_type]})")
        return None
    lid = f"LR{_lid:04d}"
    _lid += 1
    leave_requests[lid] = {
        "eid": eid, "type": leave_type, "start": start, "end": end,
        "days": days, "reason": reason, "status": "Pending"
    }
    print(f"  Leave request [{lid}] submitted by {employees[eid]['name']} ({days} days, {leave_type})")
    return lid

def approve_leave(lid, manager="Manager"):
    if lid not in leave_requests:
        print("  Leave request not found.")
        return
    lr = leave_requests[lid]
    if lr["status"] != "Pending":
        print(f"  Request already {lr['status']}.")
        return
    lr["status"] = "Approved"
    eid = lr["eid"]
    employees[eid]["balance"][lr["type"]] -= lr["days"]
    employees[eid]["approved_days"] += lr["days"]
    print(f"  [{lid}] Approved by {manager} | {employees[eid]['name']} | {lr['days']} day(s) {lr['type']}")

def reject_leave(lid, reason="No reason", manager="Manager"):
    if lid not in leave_requests:
        print("  Leave request not found.")
        return
    lr = leave_requests[lid]
    if lr["status"] != "Pending":
        print(f"  Request already {lr['status']}.")
        return
    lr["status"] = "Rejected"
    lr["reject_reason"] = reason
    print(f"  [{lid}] Rejected by {manager}: {reason}")

def employee_balance(eid):
    if eid not in employees:
        print("  Employee not found.")
        return
    e = employees[eid]
    print(f"\n  Leave Balance — {e['name']} ({eid})")
    for ltype, bal in e["balance"].items():
        used = LEAVE_QUOTA[ltype] - bal
        print(f"    {ltype:<10}: {bal:>3} remaining  ({used} used)")
    print(f"    Approved Days This Year: {e['approved_days']}")

def utilization_report():
    print(f"\n{'='*50}")
    print("  LEAVE UTILIZATION REPORT")
    print(f"{'='*50}")
    for eid, e in employees.items():
        total_quota = sum(LEAVE_QUOTA.values())
        total_used  = sum(LEAVE_QUOTA[t] - b for t, b in e["balance"].items())
        pct = (total_used / total_quota * 100) if total_quota else 0
        bar = "█" * int(pct // 5)
        print(f"  {e['name']:<18} {total_used:>3}/{total_quota} days  {pct:5.1f}%  {bar}")
    pending = sum(1 for lr in leave_requests.values() if lr["status"] == "Pending")
    approved = sum(1 for lr in leave_requests.values() if lr["status"] == "Approved")
    print(f"\n  Total Requests: {len(leave_requests)} | Pending: {pending} | Approved: {approved}")
    print(f"{'='*50}")

def main():
    print("=== Employee Leave Management System ===")
    add_employee("Rohit Sharma", "Engineering")
    add_employee("Priya Singh",  "HR")
    add_employee("Amit Patel",   "Finance")
    today = date.today()
    submit_leave("EMP0001", "Casual", str(today + timedelta(days=3)),
                 str(today + timedelta(days=5)), "Family trip")
    submit_leave("EMP0002", "Sick",   str(today + timedelta(days=1)),
                 str(today + timedelta(days=2)), "Fever")
    submit_leave("EMP0003", "Earned", str(today + timedelta(days=10)),
                 str(today + timedelta(days=14)), "Annual leave")
    submit_leave("EMP0001", "Casual", str(today + timedelta(days=6)),
                 str(today + timedelta(days=4)), "Invalid dates")
    approve_leave("LR0001", "HR Manager")
    approve_leave("LR0002", "HR Manager")
    reject_leave("LR0003",  "Insufficient coverage", "HR Manager")
    approve_leave("LR0002")  # already processed
    for eid in employees:
        employee_balance(eid)
    utilization_report()

if __name__ == "__main__":
    main()
