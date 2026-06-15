# Service Center Management System with Repair Tracking

from datetime import date, timedelta

service_requests = {}
technicians      = {}
_rid = _tech_id  = 1

STAGES    = ["Received","Diagnosed","In Repair","Quality Check","Ready","Delivered"]
PRIORITIES= ["Low","Medium","High","Critical"]

def add_technician(name, specialization, experience_yrs):
    global _tech_id
    tid = f"TECH{_tech_id:03d}"; _tech_id += 1
    technicians[tid] = {"name":name,"spec":specialization,
                        "exp":experience_yrs,"assigned":[],"completed":0}
    print(f"  [{tid}] {name} | {specialization} | {experience_yrs} yrs exp")
    return tid

def register_request(customer, device, issue, priority="Medium", received_date=None):
    global _rid
    if priority not in PRIORITIES: print(f"  Invalid priority."); return None
    rid = f"SRV{_rid:05d}"; _rid += 1
    d   = received_date or date.today()
    eta_days = {"Low":7,"Medium":5,"High":3,"Critical":1}[priority]
    eta = d + timedelta(days=eta_days)
    service_requests[rid] = {
        "customer":customer, "device":device, "issue":issue,
        "priority":priority, "status":"Received", "stage_idx":0,
        "received":d, "eta":eta, "technician":None,
        "diagnosis":None, "repair_cost":None,
        "history":[("Received", str(d))]
    }
    print(f"  [{rid}] {customer} | {device} | {priority} | ETA: {eta}")
    return rid

def assign_technician(rid, tech_id):
    if rid not in service_requests or tech_id not in technicians:
        print("  Invalid IDs."); return
    service_requests[rid]["technician"] = tech_id
    technicians[tech_id]["assigned"].append(rid)
    tname = technicians[tech_id]["name"]
    print(f"  [{rid}] Assigned to {tname}")

def update_stage(rid, diagnosis=None, repair_cost=None):
    if rid not in service_requests: print("  Not found."); return
    sr = service_requests[rid]
    if sr["stage_idx"] >= len(STAGES) - 1:
        print(f"  [{rid}] Already at final stage."); return
    sr["stage_idx"] += 1
    sr["status"]     = STAGES[sr["stage_idx"]]
    if diagnosis: sr["diagnosis"]   = diagnosis
    if repair_cost is not None: sr["repair_cost"] = repair_cost
    sr["history"].append((sr["status"], str(date.today())))
    print(f"  [{rid}] → {sr['status']}" + (f" | Cost: Rs.{repair_cost}" if repair_cost else ""))
    if sr["status"] == "Delivered" and sr["technician"]:
        technicians[sr["technician"]]["completed"] += 1
        technicians[sr["technician"]]["assigned"].remove(rid)

def view_request(rid):
    if rid not in service_requests: return
    sr = service_requests[rid]
    tech_name = technicians[sr["technician"]]["name"] if sr["technician"] else "Unassigned"
    days_since = (date.today() - sr["received"]).days
    print(f"\n{'='*50}")
    print(f"  [{rid}] {sr['device']} — {sr['customer']}")
    print(f"  Issue     : {sr['issue']}")
    print(f"  Priority  : {sr['priority']} | Status: {sr['status']}")
    print(f"  Technician: {tech_name}")
    print(f"  Received  : {sr['received']} ({days_since}d ago) | ETA: {sr['eta']}")
    if sr["diagnosis"]:   print(f"  Diagnosis : {sr['diagnosis']}")
    if sr["repair_cost"]: print(f"  Cost      : Rs.{sr['repair_cost']}")
    print(f"  History   :")
    for stage, d in sr["history"]:
        print(f"    [{d}] {stage}")
    print(f"{'='*50}")

def overdue_requests():
    today = date.today()
    overdue = [(rid, sr) for rid, sr in service_requests.items()
               if sr["eta"] < today and sr["status"] not in ["Ready","Delivered"]]
    print(f"\n--- Overdue Requests ({len(overdue)}) ---")
    for rid, sr in sorted(overdue, key=lambda x: x[1]["eta"]):
        days_late = (today - sr["eta"]).days
        tech = technicians[sr["technician"]]["name"] if sr["technician"] else "Unassigned"
        print(f"  [{rid}] {sr['device']:<20} {sr['customer']:<15} {days_late}d overdue | {tech}")

def service_report():
    print(f"\n{'='*52}\n  SERVICE CENTER REPORT\n{'='*52}")
    stage_counts = {s:0 for s in STAGES}
    for sr in service_requests.values():
        stage_counts[sr["status"]] = stage_counts.get(sr["status"],0) + 1
    print("  Stage Breakdown:")
    for stage, count in stage_counts.items():
        if count: print(f"    {stage:<18}: {count}")
    total_rev = sum(sr["repair_cost"] for sr in service_requests.values()
                    if sr["repair_cost"] and sr["status"] in ["Ready","Delivered"])
    print(f"\n  Total Jobs    : {len(service_requests)}")
    print(f"  Revenue (done): Rs.{total_rev:,}")
    print("\n  Technician Performance:")
    for tid, t in technicians.items():
        print(f"  [{tid}] {t['name']:<18} Completed:{t['completed']} Active:{len(t['assigned'])}")
    print(f"{'='*52}")

def main():
    print("=== Service Center Management System ===")
    t1 = add_technician("Rajesh Kumar", "Mobile Phones",  5)
    t2 = add_technician("Sunita Rao",   "Laptops/PCs",    8)
    t3 = add_technician("Anil Sharma",  "Home Appliances",6)
    today = date.today()
    r1 = register_request("Amit Verma",  "iPhone 14",      "Screen cracked",        "High",     today)
    r2 = register_request("Priya Singh", "Dell Laptop",    "Not turning on",        "Critical", today)
    r3 = register_request("Rahul Nair",  "Samsung TV",     "No display",            "Medium",   today-timedelta(days=6))
    r4 = register_request("Sunita Patel","OnePlus Phone",  "Battery drains fast",   "Low",      today-timedelta(days=2))
    r5 = register_request("Kiran Das",   "Lenovo ThinkPad","Keyboard keys sticking","Medium",   today-timedelta(days=4))
    assign_technician(r1, t1); assign_technician(r2, t2)
    assign_technician(r3, t3); assign_technician(r4, t1); assign_technician(r5, t2)
    update_stage(r1, "Cracked display panel", 4500)
    update_stage(r1); update_stage(r1)
    update_stage(r2, "Faulty power IC", 3200)
    update_stage(r2)
    update_stage(r3, "Backlight issue", 2800)
    for _ in range(4): update_stage(r3)   # complete to Delivered
    view_request(r1)
    overdue_requests()
    service_report()

if __name__ == "__main__":
    main()
