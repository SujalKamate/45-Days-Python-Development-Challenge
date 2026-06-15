# Multi-Branch Business Performance Analyzer with Consolidated Reporting
from datetime import date
branches = {}
monthly_data = {}
_bid = 1
EXPENSE_TYPES = ["Salaries","Rent","Utilities","Marketing","Inventory","Miscellaneous"]
def add_branch(name, city, manager, branch_type="Retail"):
    global _bid
    bid = f"BR{_bid:03d}"; _bid += 1
    branches[bid] = {"name":name,"city":city,"manager":manager,
                     "type":branch_type,"established":date.today()}
    monthly_data[bid] = []
    print(f"  [{bid}] {name} | {city} | {branch_type} | Manager:{manager}")
    return bid
def record_monthly(bid, month, year, revenue, expenses_dict, headcount):
    if bid not in branches: print("  Branch not found."); return None
    invalid = [e for e in expenses_dict if e not in EXPENSE_TYPES]
    if invalid: print(f"  Unknown expense types: {invalid}"); return None
    total_exp = sum(expenses_dict.values())
    profit    = round(revenue - total_exp, 2)
    margin    = round(profit / revenue * 100, 2) if revenue else 0
    rev_ph    = round(revenue / headcount, 2) if headcount else 0
    entry = {"month":month,"year":year,"revenue":revenue,
             "expenses":expenses_dict,"total_expenses":total_exp,
             "profit":profit,"margin":margin,"headcount":headcount,
             "revenue_per_head":rev_ph}
    monthly_data[bid].append(entry)
    status = "✔ Profit" if profit>=0 else "✗ Loss"
    print(f"  [{bid}] {branches[bid]['name']} {month}/{year} | Rev:Rs.{revenue:,} "
          f"Exp:Rs.{total_exp:,} Profit:Rs.{profit:,} ({margin}%) {status}")
    return entry

def branch_performance(bid):
    if bid not in branches: return
    logs = monthly_data[bid]
    if not logs: print(f"  No data for [{bid}]."); return
    b    = branches[bid]
    total_rev = sum(l["revenue"]         for l in logs)
    total_exp = sum(l["total_expenses"]  for l in logs)
    total_pro = sum(l["profit"]          for l in logs)
    avg_margin= round(sum(l["margin"] for l in logs)/len(logs),2)
    best  = max(logs, key=lambda x: x["profit"])
    worst = min(logs, key=lambda x: x["profit"])
    print(f"\n  Performance [{bid}] {b['name']} ({b['city']})")
    print(f"  Months Recorded: {len(logs)}")
    print(f"  Total Revenue  : Rs.{total_rev:,}")
    print(f"  Total Expenses : Rs.{total_exp:,}")
    print(f"  Total Profit   : Rs.{total_pro:,}")
    print(f"  Avg Margin     : {avg_margin}%")
    print(f"  Best Month     : {best['month']}/{best['year']} — Rs.{best['profit']:,}")
    print(f"  Worst Month    : {worst['month']}/{worst['year']} — Rs.{worst['profit']:,}")

def compare_branches(month, year):
    print(f"\n  Branch Comparison — {month}/{year}")
    print(f"  {'Branch':<20} {'City':<14} {'Revenue':>12} {'Expenses':>11} {'Profit':>10} {'Margin':>8}")
    results = []
    for bid, b in branches.items():
        entry = next((l for l in monthly_data[bid] if l["month"]==month and l["year"]==year),None)
        if entry:
            results.append((bid, b, entry))
    for bid, b, e in sorted(results, key=lambda x: -x[2]["profit"]):
        print(f"  {b['name']:<20} {b['city']:<14} Rs.{e['revenue']:>10,} "
              f"Rs.{e['total_expenses']:>9,} Rs.{e['profit']:>8,} {e['margin']:>7.1f}%")
    if results:
        top = max(results, key=lambda x: x[2]["profit"])
        print(f"\n  ★ Top Performer: {top[1]['name']} ({top[1]['city']}) — Rs.{top[2]['profit']:,}")

def expense_breakdown(bid, month, year):
    entry = next((l for l in monthly_data[bid] if l["month"]==month and l["year"]==year),None)
    if not entry: print("  No data found."); return
    b = branches[bid]
    print(f"\n  Expense Breakdown [{bid}] {b['name']} {month}/{year}:")
    for etype, amt in sorted(entry["expenses"].items(), key=lambda x:-x[1]):
        pct = round(amt/entry["total_expenses"]*100,1) if entry["total_expenses"] else 0
        bar = "█" * int(pct//5)
        print(f"  {etype:<16}: Rs.{amt:>9,} ({pct:5.1f}%) {bar}")

def consolidated_report():
    print(f"\n{'='*56}\n  CONSOLIDATED BUSINESS PERFORMANCE REPORT\n{'='*56}")
    grand_rev = grand_exp = grand_pro = 0
    for bid, b in branches.items():
        logs = monthly_data[bid]
        if not logs: continue
        rev = sum(l["revenue"] for l in logs)
        exp = sum(l["total_expenses"] for l in logs)
        pro = sum(l["profit"] for l in logs)
        grand_rev += rev; grand_exp += exp; grand_pro += pro
        margin = round(pro/rev*100,1) if rev else 0
        flag = "✔" if pro>=0 else "✗"
        print(f"  {flag} [{bid}] {b['name']:<22} {b['city']:<14} "
              f"Rev:Rs.{rev:>10,} Pro:Rs.{pro:>9,} ({margin}%)")
    grand_margin = round(grand_pro/grand_rev*100,1) if grand_rev else 0
    print(f"\n  {'TOTAL':<40} Rev:Rs.{grand_rev:>10,} Pro:Rs.{grand_pro:>9,} ({grand_margin}%)")
    print(f"  Total Expenses : Rs.{grand_exp:,}")
    profitable = sum(1 for bid in branches if sum(l["profit"] for l in monthly_data[bid])>=0)
    print(f"  Profitable Branches: {profitable}/{len(branches)}")
    print(f"{'='*56}")

def main():
    print("=== Multi-Branch Business Performance Analyzer ===")
    b1 = add_branch("Mumbai Central", "Mumbai",    "Arun Mehta",  "Retail")
    b2 = add_branch("Delhi North Hub","Delhi",     "Priya Singh", "Retail")
    b3 = add_branch("Bangalore Tech", "Bangalore", "Rahul Nair",  "Services")
    b4 = add_branch("Chennai South",  "Chennai",   "Divya Rao",   "Retail")
    months = [(4,2025),(5,2025),(6,2025)]
    data = {
        b1:[(4,1800000,{"Salaries":600000,"Rent":150000,"Utilities":40000,"Marketing":80000,"Inventory":400000,"Miscellaneous":30000},45),
            (5,2100000,{"Salaries":600000,"Rent":150000,"Utilities":42000,"Marketing":100000,"Inventory":480000,"Miscellaneous":28000},45),
            (6,1950000,{"Salaries":620000,"Rent":150000,"Utilities":45000,"Marketing":90000,"Inventory":440000,"Miscellaneous":35000},46)],
        b2:[(4,1500000,{"Salaries":500000,"Rent":120000,"Utilities":35000,"Marketing":70000,"Inventory":350000,"Miscellaneous":25000},38),
            (5,1650000,{"Salaries":500000,"Rent":120000,"Utilities":36000,"Marketing":80000,"Inventory":380000,"Miscellaneous":24000},38),
            (6,1420000,{"Salaries":510000,"Rent":120000,"Utilities":38000,"Marketing":65000,"Inventory":320000,"Miscellaneous":27000},39)],
        b3:[(4,2200000,{"Salaries":900000,"Rent":200000,"Utilities":50000,"Marketing":120000,"Inventory":100000,"Miscellaneous":40000},60),
            (5,2500000,{"Salaries":900000,"Rent":200000,"Utilities":52000,"Marketing":140000,"Inventory":110000,"Miscellaneous":38000},60),
            (6,2350000,{"Salaries":920000,"Rent":200000,"Utilities":55000,"Marketing":130000,"Inventory":105000,"Miscellaneous":42000},62)],
        b4:[(4,980000, {"Salaries":320000,"Rent":80000, "Utilities":25000,"Marketing":45000,"Inventory":220000,"Miscellaneous":18000},28),
            (5,1050000,{"Salaries":320000,"Rent":80000, "Utilities":26000,"Marketing":50000,"Inventory":240000,"Miscellaneous":17000},28),
            (6,890000, {"Salaries":330000,"Rent":80000, "Utilities":27000,"Marketing":40000,"Inventory":200000,"Miscellaneous":20000},29)],
    }
    for bid, entries in data.items():
        for m,y,rev,exp,hc in entries:
            record_monthly(bid,m,y,rev,exp,hc)
    compare_branches(6,2025)
    branch_performance(b3)
    expense_breakdown(b1,6,2025)
    consolidated_report()

if __name__ == "__main__":
    main()
