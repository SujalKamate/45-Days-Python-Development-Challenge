# Charity Fund Management System with Allocation Reports

from datetime import date

funds   = {}
projects= {}
donations_log = []
expenditures  = []
_fid = _proj_id = _don_id = 1

def create_fund(name, description, target_amount):
    global _fid
    fid = f"FND{_fid:03d}"; _fid += 1
    funds[fid] = {"name":name,"desc":description,"target":target_amount,
                  "raised":0,"allocated":0,"projects":[]}
    print(f"  [{fid}] {name} | Target: Rs.{target_amount:,}")
    return fid

def create_project(title, fid, budget, beneficiaries, start_date=None):
    global _proj_id
    if fid not in funds: print("  Fund not found."); return None
    pid = f"PRJ{_proj_id:03d}"; _proj_id += 1
    projects[pid] = {"title":title,"fund":fid,"budget":budget,"spent":0,
                     "beneficiaries":beneficiaries,"status":"Active","start":start_date or date.today()}
    funds[fid]["allocated"] += budget
    funds[fid]["projects"].append(pid)
    print(f"  [{pid}] {title} | Budget: Rs.{budget:,} | Beneficiaries: {beneficiaries}")
    return pid

def record_donation(fid, donor_name, amount, method="Online", don_date=None):
    global _don_id
    if fid not in funds: print("  Fund not found."); return None
    did = f"DON{_don_id:05d}"; _don_id += 1
    d   = don_date or date.today()
    funds[fid]["raised"] += amount
    donations_log.append({"id":did,"fund":fid,"donor":donor_name,"amount":amount,"method":method,"date":d})
    avail = funds[fid]["raised"] - funds[fid]["allocated"]
    print(f"  [{did}] {donor_name} → [{fid}] Rs.{amount:,} via {method} | Available: Rs.{avail:,}")
    return did

def record_expenditure(pid, description, amount, exp_date=None):
    if pid not in projects: print("  Project not found."); return
    p = projects[pid]
    if p["spent"] + amount > p["budget"]:
        print(f"  ⚠ Exceeds budget by Rs.{p['spent']+amount-p['budget']:,}. Proceed? Recording anyway.")
    d = exp_date or date.today()
    p["spent"] += amount
    expenditures.append({"pid":pid,"desc":description,"amount":amount,"date":d})
    print(f"  [{pid}] Expense: {description} Rs.{amount:,} | Spent: {p['spent']:,}/{p['budget']:,}")

def fund_utilization(fid):
    if fid not in funds: return
    f = funds[fid]
    avail = f["raised"] - f["allocated"]
    raised_pct = f["raised"] / f["target"] * 100 if f["target"] else 0
    print(f"\n  Fund [{fid}]: {f['name']}")
    print(f"  Target   : Rs.{f['target']:,}")
    print(f"  Raised   : Rs.{f['raised']:,} ({raised_pct:.1f}% of target)")
    print(f"  Allocated: Rs.{f['allocated']:,}")
    print(f"  Available: Rs.{avail:,}")
    print(f"  Projects :")
    for pid in f["projects"]:
        p = projects[pid]
        util = p["spent"] / p["budget"] * 100 if p["budget"] else 0
        bar  = "█" * int(util // 10)
        print(f"    [{pid}] {p['title']:<25} {util:5.1f}% spent  {bar}")

def transparency_report():
    print(f"\n{'='*56}\n  CHARITY FUND TRANSPARENCY REPORT\n{'='*56}")
    total_raised = sum(f["raised"] for f in funds.values())
    total_spent  = sum(p["spent"]  for p in projects.values())
    total_alloc  = sum(f["allocated"] for f in funds.values())
    util_pct     = total_spent / total_raised * 100 if total_raised else 0
    print(f"  Total Raised     : Rs.{total_raised:,}")
    print(f"  Total Allocated  : Rs.{total_alloc:,}")
    print(f"  Total Spent      : Rs.{total_spent:,}")
    print(f"  Utilisation Rate : {util_pct:.1f}%")
    print(f"  Admin Reserve    : Rs.{total_raised-total_spent:,}")
    top_donors = sorted(donations_log, key=lambda x: -x["amount"])[:3]
    print("\n  Top Donors:")
    for rank, d in enumerate(top_donors, 1):
        print(f"    {rank}. {d['donor']:<20} Rs.{d['amount']:,} → [{d['fund']}]")
    print(f"\n  Project Outcomes:")
    for pid, p in projects.items():
        benprice = round(p["spent"] / p["beneficiaries"], 2) if p["beneficiaries"] else 0
        print(f"  [{pid}] {p['title']:<28} {p['beneficiaries']:>6} ppl | Rs.{benprice}/person")
    print(f"{'='*56}")

def main():
    print("=== Charity Fund Management System ===")
    f1 = create_fund("Education For All",  "School supplies for underprivileged",   500000)
    f2 = create_fund("Flood Relief 2025",  "Aid for flood-affected families",       1000000)
    f3 = create_fund("Clean Water Project","Bore wells in drought areas",            750000)
    p1 = create_project("School Kits Drive",     f1, 150000, 300)
    p2 = create_project("Tuition Centers",       f1, 200000, 500)
    p3 = create_project("Emergency Food Kits",   f2, 300000, 600)
    p4 = create_project("Shelter Repair",        f2, 400000, 200)
    p5 = create_project("Bore Well Installation",f3, 500000, 1000)
    record_donation(f1,"Ratan Tata Foundation",250000,"NEFT")
    record_donation(f1,"Anonymous Donor",       80000,"Online")
    record_donation(f2,"HDFC CSR",             500000,"Cheque")
    record_donation(f2,"Google.org",           350000,"Wire Transfer")
    record_donation(f3,"Infosys Foundation",   400000,"NEFT")
    record_expenditure(p1,"Books and Stationery",  80000)
    record_expenditure(p1,"School Bags",           60000)
    record_expenditure(p3,"Food Packets",         180000)
    record_expenditure(p3,"Logistics",             40000)
    record_expenditure(p5,"Drilling Equipment",   250000)
    fund_utilization(f1)
    transparency_report()

if __name__ == "__main__":
    main()
