# Call Center Ticketing System with Resolution Analytics
from datetime import datetime, date
tickets     = {}
agents      = {}
_tid = _aid = 1
PRIORITIES  = ["Low","Medium","High","Critical"]
CATEGORIES  = ["Technical","Billing","Account","Product","General"]
STATUSES    = ["Open","Assigned","In Progress","Pending Customer","Resolved","Closed"]
def add_agent(name, department, skills):
    global _aid
    aid = f"AGT{_aid:03d}"; _aid += 1
    agents[aid] = {"name":name,"dept":department,"skills":skills,
                   "active_tickets":[],"resolved":0,"avg_handle_min":0}
    print(f"  [{aid}] {name} | {department} | Skills:{skills}")
    return aid
def create_ticket(customer, issue, category, priority, channel="Phone"):
    global _tid
    if category not in CATEGORIES: print(f"  Invalid category."); return None
    if priority not in PRIORITIES:  print(f"  Invalid priority.");  return None
    tid    = f"TKT{_tid:06d}"; _tid += 1
    now    = datetime.now().strftime("%Y-%m-%d %H:%M")
    sla    = {"Low":48,"Medium":24,"High":8,"Critical":2}[priority]
    tickets[tid] = {
        "customer":customer, "issue":issue, "category":category,
        "priority":priority, "channel":channel, "status":"Open",
        "agent":None, "created":now, "updated":now,
        "resolved_at":None, "handle_time":None,
        "sla_hours":sla, "history":[(now,"Open","Ticket created")]
    }
    print(f"  [{tid}] {customer} | {category} | {priority} | SLA:{sla}h | {channel}")
    return tid
def assign_ticket(tid, aid):
    if tid not in tickets or aid not in agents:
        print("  Invalid IDs."); return
    t = tickets[tid]; a = agents[aid]
    t["agent"]   = aid
    t["status"]  = "Assigned"
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    t["updated"] = now
    t["history"].append((now,"Assigned",f"Assigned to {a['name']}"))
    a["active_tickets"].append(tid)
    print(f"  [{tid}] Assigned to {a['name']}")
def update_ticket_status(tid, new_status, note=""):
    if tid not in tickets: print("  Not found."); return
    if new_status not in STATUSES: print("  Invalid status."); return
    t   = tickets[tid]
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    t["status"]  = new_status
    t["updated"] = now
    t["history"].append((now, new_status, note or f"Status changed to {new_status}"))
    if new_status in ("Resolved","Closed"):
        t["resolved_at"] = now
        if t["agent"] and t["agent"] in agents:
            aid = t["agent"]
            agents[aid]["resolved"] += 1
            if tid in agents[aid]["active_tickets"]:
                agents[aid]["active_tickets"].remove(tid)
    print(f"  [{tid}] → {new_status}" + (f": {note}" if note else ""))
def view_ticket(tid):
    if tid not in tickets: return
    t = tickets[tid]
    agent_name = agents[t["agent"]]["name"] if t["agent"] else "Unassigned"
    print(f"\n{'='*52}")
    print(f"  [{tid}] {t['customer']} | {t['category']} | {t['priority']}")
    print(f"  Issue  : {t['issue']}")
    print(f"  Status : {t['status']} | Agent: {agent_name}")
    print(f"  Created: {t['created']} | Updated: {t['updated']}")
    print(f"  SLA    : {t['sla_hours']}h | Channel: {t['channel']}")
    print(f"  History:")
    for ts, status, note in t["history"]:
        print(f"    [{ts}] {status}: {note}")
    print(f"{'='*52}")
def agent_performance():
    print(f"\n--- Agent Performance ---")
    for aid, a in agents.items():
        active = len(a["active_tickets"])
        print(f"  [{aid}] {a['name']:<18} Active:{active:>3} | Resolved:{a['resolved']:>4}")
def sla_compliance_report():
    print(f"\n--- SLA Compliance ---")
    breached = 0
    for tid, t in tickets.items():
        if t["status"] in ("Open","Assigned","In Progress","Pending Customer"):
            print(f"  [OPEN]  [{tid}] {t['priority']:<10} {t['customer']:<18} SLA:{t['sla_hours']}h")
        else:
            print(f"  [DONE]  [{tid}] {t['priority']:<10} {t['customer']:<18} {t['status']}")

def analytics_report():
    print(f"\n{'='*52}\n  CALL CENTER ANALYTICS REPORT\n{'='*52}")
    total  = len(tickets)
    open_  = sum(1 for t in tickets.values() if t["status"] in ("Open","Assigned","In Progress"))
    closed = sum(1 for t in tickets.values() if t["status"] in ("Resolved","Closed"))
    cat_counts = {c:0 for c in CATEGORIES}
    pri_counts = {p:0 for p in PRIORITIES}
    for t in tickets.values():
        cat_counts[t["category"]] += 1
        pri_counts[t["priority"]] += 1
    print(f"  Total Tickets : {total} | Open: {open_} | Closed: {closed}")
    print(f"\n  By Priority:")
    for p, cnt in pri_counts.items():
        if cnt: print(f"    {p:<12}: {cnt}")
    print(f"\n  By Category:")
    for c, cnt in cat_counts.items():
        if cnt: print(f"    {c:<15}: {cnt}")
    agent_performance()
    print(f"{'='*52}")

def main():
    print("=== Call Center Ticketing System ===")
    a1 = add_agent("Rohit Sharma",  "Technical",  ["Linux","Networking","Python"])
    a2 = add_agent("Priya Singh",   "Billing",    ["Finance","Accounts","Excel"])
    a3 = add_agent("Ankit Kumar",   "Product",    ["CRM","Product","Training"])
    t1 = create_ticket("Amit Verma",   "Cannot login to account",      "Technical","High",   "Phone")
    t2 = create_ticket("Meena Patel",  "Overcharged on last invoice",  "Billing",  "Medium", "Email")
    t3 = create_ticket("Ravi Nair",    "Feature request for export",   "Product",  "Low",    "Chat")
    t4 = create_ticket("Sunita Rao",   "Server down since morning",    "Technical","Critical","Phone")
    t5 = create_ticket("Kiran Das",    "Password reset not working",   "Account",  "High",   "App")
    assign_ticket(t1, a1); assign_ticket(t2, a2)
    assign_ticket(t3, a3); assign_ticket(t4, a1); assign_ticket(t5, a3)
    update_ticket_status(t1,"In Progress","Investigating login issue")
    update_ticket_status(t4,"In Progress","Server restart in progress")
    update_ticket_status(t4,"Resolved","Server restored after hardware fix")
    update_ticket_status(t2,"Resolved","Refund of Rs.500 processed")
    update_ticket_status(t1,"Pending Customer","Awaiting logs from customer")
    view_ticket(t4)
    sla_compliance_report()
    analytics_report()

if __name__ == "__main__":
    main()
