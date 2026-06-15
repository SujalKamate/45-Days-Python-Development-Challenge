# Complaint Management Portal with Resolution Tracking

from datetime import datetime

CATEGORIES = ["Billing", "Technical", "Delivery", "Product Quality", "Customer Service", "Other"]
PRIORITIES  = {"Billing": "High", "Technical": "Medium", "Delivery": "High",
               "Product Quality": "Medium", "Customer Service": "Low", "Other": "Low"}
complaints = {}
_cid = 1

def register_complaint(customer, category, description, contact):
    global _cid
    if category not in CATEGORIES:
        print(f"  Invalid category. Choose: {CATEGORIES}")
        return None
    cid = f"CMP{_cid:05d}"
    _cid += 1
    priority = PRIORITIES.get(category, "Low")
    complaints[cid] = {
        "customer": customer, "contact": contact,
        "category": category, "description": description,
        "priority": priority, "status": "Registered",
        "assigned_to": None, "resolution": None,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "history": [("Registered", datetime.now().strftime("%Y-%m-%d %H:%M"))]
    }
    print(f"  [{cid}] Complaint registered | {customer} | {category} | Priority: {priority}")
    return cid

def assign_complaint(cid, agent):
    if cid not in complaints:
        print("  Complaint not found.")
        return
    complaints[cid]["assigned_to"] = agent
    complaints[cid]["status"] = "In Progress"
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    complaints[cid]["updated_at"] = ts
    complaints[cid]["history"].append((f"Assigned to {agent}", ts))
    print(f"  [{cid}] Assigned to {agent}")

def update_status(cid, new_status, note=""):
    valid = ["Registered", "In Progress", "Pending Customer", "Resolved", "Closed"]
    if cid not in complaints:
        print("  Complaint not found.")
        return
    if new_status not in valid:
        print(f"  Invalid status. Options: {valid}")
        return
    complaints[cid]["status"] = new_status
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    complaints[cid]["updated_at"] = ts
    complaints[cid]["history"].append((f"{new_status}" + (f": {note}" if note else ""), ts))
    print(f"  [{cid}] Status → {new_status}")

def resolve_complaint(cid, resolution_note):
    if cid not in complaints:
        print("  Complaint not found.")
        return
    complaints[cid]["resolution"] = resolution_note
    update_status(cid, "Resolved", resolution_note)

def view_complaint(cid):
    if cid not in complaints:
        print("  Complaint not found.")
        return
    c = complaints[cid]
    print(f"\n{'='*48}")
    print(f"  Complaint ID : {cid}")
    print(f"  Customer     : {c['customer']} ({c['contact']})")
    print(f"  Category     : {c['category']} | Priority: {c['priority']}")
    print(f"  Status       : {c['status']}")
    print(f"  Assigned To  : {c['assigned_to'] or 'Unassigned'}")
    print(f"  Description  : {c['description']}")
    if c["resolution"]:
        print(f"  Resolution   : {c['resolution']}")
    print(f"  History:")
    for step, ts in c["history"]:
        print(f"    [{ts}] {step}")
    print(f"{'='*48}")

def complaint_statistics():
    print(f"\n{'='*48}")
    print("  COMPLAINT STATISTICS")
    print(f"{'='*48}")
    status_count = {}
    cat_count = {}
    priority_count = {}
    for c in complaints.values():
        status_count[c["status"]] = status_count.get(c["status"], 0) + 1
        cat_count[c["category"]] = cat_count.get(c["category"], 0) + 1
        priority_count[c["priority"]] = priority_count.get(c["priority"], 0) + 1
    print("  By Status:")
    for s, n in status_count.items():
        print(f"    {s:<22}: {n}")
    print("  By Category:")
    for cat, n in sorted(cat_count.items(), key=lambda x: -x[1]):
        print(f"    {cat:<22}: {n}")
    print("  By Priority:")
    for p, n in priority_count.items():
        print(f"    {p:<22}: {n}")
    resolved = sum(1 for c in complaints.values() if c["status"] in ["Resolved","Closed"])
    rate = (resolved / len(complaints) * 100) if complaints else 0
    print(f"\n  Total: {len(complaints)} | Resolved: {resolved} | Rate: {rate:.1f}%")
    print(f"{'='*48}")

def main():
    print("=== Complaint Management Portal ===")
    c1 = register_complaint("Arun Kumar",  "Billing",          "Overcharged on invoice", "9876543210")
    c2 = register_complaint("Meena Patel", "Delivery",         "Package not received",    "9123456780")
    c3 = register_complaint("Ravi Singh",  "Technical",        "App keeps crashing",      "9011223344")
    c4 = register_complaint("Sunita Rao",  "Product Quality",  "Item broken on arrival",  "9988776655")
    c5 = register_complaint("Vikram Das",  "Customer Service", "Rude staff behaviour",    "9001122334")
    assign_complaint(c1, "Agent Priya")
    assign_complaint(c2, "Agent Rohit")
    assign_complaint(c3, "Agent Ankit")
    resolve_complaint(c1, "Refund of Rs.500 issued.")
    resolve_complaint(c2, "Replacement dispatched, tracking #XYZ123.")
    update_status(c3, "Pending Customer", "Awaiting app version info from customer.")
    view_complaint(c1)
    view_complaint(c3)
    complaint_statistics()

if __name__ == "__main__":
    main()
