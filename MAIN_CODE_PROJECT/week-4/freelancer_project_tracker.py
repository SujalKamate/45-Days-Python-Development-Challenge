# Freelancer Project Tracker with Earnings Dashboard
from datetime import date, timedelta
projects  = {}
clients   = {}
invoices  = []
_pid = _cid = _inv = 1
def add_client(name, company, email, currency="INR"):
    global _cid
    cid = f"CLT{_cid:04d}"; _cid += 1
    clients[cid] = {"name":name,"company":company,"email":email,"currency":currency,"projects":[]}
    print(f"  [{cid}] {name} | {company} | {email}")
    return cid
def add_project(title, client_id, rate, rate_type, deadline, estimated_hours=0):
    global _pid
    if client_id not in clients: print("  Client not found."); return None
    if rate_type not in ("hourly","fixed"): print("  rate_type must be 'hourly' or 'fixed'"); return None
    pid = f"PRJ{_pid:04d}"; _pid += 1
    projects[pid] = {
        "title":title, "client":client_id, "rate":rate, "rate_type":rate_type,
        "deadline":deadline, "estimated_hours":estimated_hours,
        "hours_logged":0, "status":"Active", "invoiced":0,
        "tasks":[], "started":date.today()
    }
    clients[client_id]["projects"].append(pid)
    earnings = rate if rate_type == "fixed" else rate * estimated_hours
    print(f"  [{pid}] {title} | {rate_type} Rs.{rate} | Deadline: {deadline} | Est. Rs.{earnings:,.0f}")
    return pid

def log_hours(pid, hours, description="Work done"):
    if pid not in projects: print("  Project not found."); return
    projects[pid]["hours_logged"] += hours
    projects[pid]["tasks"].append({"hours":hours,"desc":description,"date":str(date.today())})
    total = projects[pid]["hours_logged"]
    print(f"  [{pid}] +{hours}h ({description}) | Total: {total}h")

def mark_complete(pid):
    if pid not in projects: return
    projects[pid]["status"] = "Completed"
    p = projects[pid]
    earnings = p["rate"] if p["rate_type"] == "fixed" else round(p["rate"] * p["hours_logged"], 2)
    print(f"  [{pid}] '{p['title']}' COMPLETED | Earnings: Rs.{earnings:,}")

def generate_invoice(pid):
    global _inv
    if pid not in projects: print("  Project not found."); return None
    p  = projects[pid]
    c  = clients[p["client"]]
    amount = p["rate"] if p["rate_type"] == "fixed" else round(p["rate"] * p["hours_logged"], 2)
    amount -= p["invoiced"]
    if amount <= 0: print(f"  [{pid}] Nothing to invoice."); return None
    inv_id = f"INV{_inv:05d}"; _inv += 1
    gst    = round(amount * 0.18, 2)
    total  = round(amount + gst, 2)
    invoices.append({"inv_id":inv_id,"pid":pid,"client":c["name"],"amount":amount,
                     "gst":gst,"total":total,"date":str(date.today()),"paid":False})
    projects[pid]["invoiced"] += amount
    print(f"  [{inv_id}] {c['name']} | {p['title']} | Rs.{amount} + GST Rs.{gst} = Rs.{total}")
    return inv_id

def mark_invoice_paid(inv_id):
    inv = next((i for i in invoices if i["inv_id"] == inv_id), None)
    if not inv: print("  Invoice not found."); return
    inv["paid"] = True
    print(f"  [{inv_id}] Marked as PAID | Rs.{inv['total']}")

def project_detail(pid):
    if pid not in projects: return
    p = projects[pid]
    c = clients[p["client"]]
    earnings = p["rate"] if p["rate_type"] == "fixed" else round(p["rate"] * p["hours_logged"], 2)
    today = date.today()
    days_left = (p["deadline"] - today).days
    print(f"\n  Project [{pid}]: {p['title']}")
    print(f"  Client  : {c['name']} ({c['company']})")
    print(f"  Rate    : {p['rate_type']} Rs.{p['rate']} | Hours: {p['hours_logged']}")
    print(f"  Deadline: {p['deadline']} ({'OVERDUE' if days_left < 0 else f'{days_left} days left'})")
    print(f"  Status  : {p['status']} | Est. Earnings: Rs.{earnings:,}")

def earnings_dashboard():
    print(f"\n{'='*52}\n  FREELANCER EARNINGS DASHBOARD\n{'='*52}")
    total_earnings = 0
    for pid, p in projects.items():
        earn = p["rate"] if p["rate_type"] == "fixed" else round(p["rate"] * p["hours_logged"], 2)
        total_earnings += earn
    total_invoiced = sum(i["amount"] for i in invoices)
    total_received = sum(i["total"] for i in invoices if i["paid"])
    pending        = sum(i["total"] for i in invoices if not i["paid"])
    total_hours    = sum(p["hours_logged"] for p in projects.values())
    active = sum(1 for p in projects.values() if p["status"] == "Active")
    done   = sum(1 for p in projects.values() if p["status"] == "Completed")
    print(f"  Total Projects  : {len(projects)} ({active} active, {done} completed)")
    print(f"  Total Hours     : {total_hours}")
    print(f"  Total Earnings  : Rs.{total_earnings:,}")
    print(f"  Total Invoiced  : Rs.{total_invoiced:,}")
    print(f"  Total Received  : Rs.{total_received:,}")
    print(f"  Pending Payment : Rs.{pending:,}")
    print(f"\n  Client Breakdown:")
    for cid, c in clients.items():
        c_projects = [projects[pid] for pid in c["projects"] if pid in projects]
        c_earn = sum((p["rate"] if p["rate_type"]=="fixed" else p["rate"]*p["hours_logged"]) for p in c_projects)
        print(f"    {c['name']:<20}: {len(c_projects)} project(s) | Rs.{c_earn:,}")
    print(f"{'='*52}")

def main():
    print("=== Freelancer Project Tracker ===")
    c1 = add_client("TechCorp Ltd",   "TechCorp",  "pm@techcorp.com")
    c2 = add_client("StartupXYZ",     "StartupXYZ","ceo@xyz.com")
    c3 = add_client("GlobalMedia Inc","GlobalMedia","projects@global.com")
    today = date.today()
    p1 = add_project("E-commerce Website",  c1, 150, "hourly", today+timedelta(days=30), 80)
    p2 = add_project("Mobile App Design",   c2, 50000, "fixed", today+timedelta(days=45))
    p3 = add_project("Data Dashboard",      c1, 120,   "hourly",today+timedelta(days=20), 40)
    p4 = add_project("Brand Identity Pack", c3, 30000, "fixed", today-timedelta(days=2))
    log_hours(p1, 20, "Frontend development")
    log_hours(p1, 15, "Backend API integration")
    log_hours(p3, 18, "Data visualizations")
    log_hours(p3, 12, "Dashboard layout")
    mark_complete(p4)
    inv1 = generate_invoice(p1)
    inv2 = generate_invoice(p3)
    inv3 = generate_invoice(p4)
    mark_invoice_paid(inv1)
    project_detail(p1)
    project_detail(p4)
    earnings_dashboard()

if __name__ == "__main__":
    main()
